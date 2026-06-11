"""DeepAgents execution boundary for the current tax-agent runtime.

Main path:
    - execute_turn(...) for /chat and batch-adapted turns
    - stream_turn(...) for /chat/stream

Compatibility path:
    - execute(...) and execute_with_evidence(...) are retained for old tests and
      earlier F001-F003 call shapes. New runtime code should not call them.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from tax_agent.config import AgentConfig
from tax_agent.domain.domain_knowledge import analyze_tax_context, analyze_tax_question
from tax_agent.domain.intent_classifier import ClassifiedQuestion, IntentClassifier
from tax_agent.domain.tax_retrieval import extract_citations_from_messages, retrieve_tax_context
from tax_agent.runtime.checkpointing import (
    CheckpointConfig,
    build_async_checkpoint_config,
    build_checkpoint_config,
)
from tax_agent.runtime.conversation import ConversationRequest
from tax_agent.runtime.observability import build_langfuse_observability
from tax_agent.runtime.stream_events import normalize_stream_event

PART2_ROOT = Path(__file__).resolve().parents[2]
SKILL_SOURCES = ["/skills"]
MEMORY_SOURCES = ["/memories/AGENTS.md"]
SKILL_PATH_PREFIX = "/skills/"
SKILL_TOOL_NAME = "read_file"
SKILL_FILE_BASENAME = "SKILL.md"
TAX_TOOL_NAMES = frozenset({"retrieve_tax_context", "analyze_tax_question"})
EXPLORATORY_TOOL_NAMES = frozenset({"ls", "grep", "glob"})

# Default recursion limit for LangGraph execution. The default (25) is too
# low once the Skill discipline is enabled: the agent can legitimately
# invoke read_file (skill) → tool_call → read_file (ref) → ... and exceed
# 25 steps on a tax-audit question. 50 is the budget we observed the V2
# prompt needed without surfacing GraphRecursionError.
DEFAULT_RECURSION_LIMIT = 50

import re
_SKILL_PATH_RE = re.compile(r"^/skills/([^/]+)/")


TAX_SYSTEM_PROMPT = """你是一位专业的税务顾问专家。
你的任务是准确回答税务相关问题，包括：
1. 税务概念定义与解释
2. 税率计算与税额分析
3. 税务合规性判断

回答要求：
- 基于事实和税法规定
- 结构清晰，分点阐述
- 如引用法规或数据，标注来源
- 如不确定，明确说明局限性
- 对复杂问题先使用 DeepAgents 原生规划能力（write_todos）拆解任务
- 需要法规依据时调用 retrieve_tax_context 工具，并在回答中引用检索到的 source_id/title
- 不输出模型内部推理标签，例如 <think>...</think>
- **完成工具调用后，必须在结构化回答（structured_response.answer）中输出完整中文回答**，不能为空或仅含「待生成」「暂无回答」等占位/总结文本

Skill 使用纪律（强制）：
- 系统提示中会列出可用的 Skills 库（含 name、description、完整路径）。
- 在调用任何工具（retrieve_tax_context / analyze_tax_question / read_file 等）之前，先扫 Skills 列表的 name / description。
- **最多选 1 个最匹配的 skill**（不要全选，不要遍历），用 read_file 读取其 SKILL.md 并按工作流执行。读完立即进入下游工具调用，**不要再读其他 skill 的 SKILL.md / refs / templates**。
- 税审五大类问题（意图识别 / 场景识别 / 历史问题匹配 / 解决方案生成 / 术语拆解）：先 read_file 对应 skill 的 SKILL.md（仅 1 个），再调用 retrieve_tax_context / analyze_tax_question。
- 不要用 ls / grep / glob 探测 /tax_agent/ 等代码目录来"查资料"——这是源代码，不是知识库。如 retrieve_tax_context 连续 3 次空检索，再考虑用 write_todos 拆解并向用户说明检索覆盖度不足。
"""


class TaxCitation(BaseModel):
    source_id: str = Field(description="检索来源 ID")
    title: str = Field(description="检索来源标题")


class TaxAnswer(BaseModel):
    question: str = Field(description="原始税务问题")
    intent: str = Field(description="业务标签：definition/rate/compliance")
    answer: str = Field(description="面向用户的中文回答")
    citations: list[TaxCitation] = Field(default_factory=list, description="结构化引用来源")


@dataclass
class ExecutionResult:
    answer: str
    citations: list[dict] = field(default_factory=list)
    tool_events: list[dict] = field(default_factory=list)
    domain_analysis: dict = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)
    skills_invoked: list[str] = field(default_factory=list)
    skill_invocation_count: int = 0
    artifact: dict = field(default_factory=dict)
    session_id: str | None = None
    trace_id: str | None = None
    thread_id: str | None = None


class ModelOutputError(RuntimeError):
    pass


class ReasoningFilter:
    def __init__(self):
        self.in_reasoning = False
        self.saw_reasoning = False

    def filter(self, text: str) -> str:
        output = []
        index = 0
        while index < len(text):
            if self.in_reasoning:
                end = text.find("</think>", index)
                self.saw_reasoning = True
                if end == -1:
                    return "".join(output)
                self.in_reasoning = False
                index = end + len("</think>")
                continue
            start = text.find("<think>", index)
            if start == -1:
                output.append(text[index:])
                break
            output.append(text[index:start])
            self.in_reasoning = True
            self.saw_reasoning = True
            index = start + len("<think>")
        return "".join(output)


class AgentExecutor:
    """Wraps DeepAgents with stable project-level request/response methods."""

    def __init__(self, config: AgentConfig, agent=None, checkpoint_config: CheckpointConfig | None = None):
        self._config = config
        self._checkpoint_config = checkpoint_config
        self._observability = build_langfuse_observability(config.langfuse_enabled)
        if self._checkpoint_config is None:
            self._checkpoint_config = build_checkpoint_config(
                config.output_dir,
                backend_type=config.checkpoint_backend,
                dsn=config.opengauss_dsn,
            )
        self._agent = agent or self.build_agent(config, checkpointer=self._checkpoint_config.checkpointer)

    @classmethod
    async def create(cls, config: AgentConfig) -> "AgentExecutor":
        checkpoint_config = await build_async_checkpoint_config(
            config.output_dir,
            backend_type=config.checkpoint_backend,
            dsn=config.opengauss_dsn,
        )
        return cls(config, checkpoint_config=checkpoint_config)

    @property
    def output_dir(self) -> str:
        return self._config.output_dir

    @property
    def default_thread_id(self) -> str:
        return self._checkpoint_config.thread_id

    @property
    def checkpoint_backend_type(self) -> str:
        return self._checkpoint_config.backend_type

    @property
    def observability_provider(self) -> str:
        return self._observability.provider

    @staticmethod
    def build_agent(config: AgentConfig, checkpointer=None):
        from deepagents import create_deep_agent
        from deepagents.backends import FilesystemBackend
        from langchain.chat_models import init_chat_model

        model = init_chat_model(
            config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        return create_deep_agent(
            model=model,
            system_prompt=TAX_SYSTEM_PROMPT,
            tools=[retrieve_tax_context, analyze_tax_question],
            skills=SKILL_SOURCES,
            memory=MEMORY_SOURCES,
            backend=FilesystemBackend(root_dir=PART2_ROOT, virtual_mode=True),
            #response_format=TaxAnswer,
            checkpointer=checkpointer,
        )

    async def execute(self, question: ClassifiedQuestion, plan_steps: list[str] | None = None) -> str:
        if plan_steps is None:
            return (await self.execute_with_evidence(question)).answer

        prompt = self._build_prompt(question, plan_steps)
        result = await self._ainvoke({"messages": [{"role": "user", "content": prompt}]})
        return self._last_content(result["messages"])

    async def execute_with_evidence(self, question: ClassifiedQuestion) -> ExecutionResult:
        request = ConversationRequest(
            session_id="cli",
            trace_id=self._checkpoint_config.thread_id,
            thread_id=self._checkpoint_config.thread_id,
            messages=[{"role": "user", "content": self._build_native_prompt(question)}],
        )
        return await self.execute_turn(request)

    async def execute_turn(self, request: ConversationRequest) -> ExecutionResult:
        result = await self._ainvoke(
            {"messages": request.to_agent_messages()},
            thread_id=request.thread_id,
            metadata={
                "session_id": request.session_id,
                "trace_id": request.trace_id,
                "thread_id": request.thread_id,
                "checkpoint_backend": self._checkpoint_config.backend_type,
            },
            tags=[request.session_id, request.trace_id, request.thread_id],
            callbacks=self._observability.callbacks,
        )
        messages = result["messages"]
        structured_answer, structured_citations = self._structured_result(result)
        citations = structured_citations or extract_citations_from_messages(messages)
        domain_analysis = analyze_tax_context(request.to_agent_messages())
        # V4+V5: walk a fallback chain with unusable-answer filtering, mirroring
        # the master a94ceaf semantics ported for /chat.
        answer = self._first_usable_answer(
            structured_answer,
            self._last_assistant_content(messages),
        )
        if not answer:
            # V5: last-resort — consult graph state for structured_response.answer.
            structured_state_answer = await self._structured_response_from_state(request.thread_id)
            if structured_state_answer:
                answer = structured_state_answer
        if not answer:
            raise ModelOutputError("模型未产生最终回答，可能只输出了 reasoning 或当前模型不支持工具调用。")

        skills_invoked = self._extract_skill_invocations(messages)
        skill_invocation_count = self._count_skill_invocations(messages)
        self._report_skill_invocations(
            request=request,
            skills_invoked=skills_invoked,
            skill_invocation_count=skill_invocation_count,
        )

        return ExecutionResult(
            answer=answer,
            citations=citations,
            tool_events=self._collect_tool_events(messages),
            domain_analysis=domain_analysis,
            skills=self._skills_from_domain_analysis(domain_analysis),
            skills_invoked=skills_invoked,
            skill_invocation_count=skill_invocation_count,
            artifact=self._tax_answer_artifact(request, answer, citations),
            session_id=request.session_id,
            trace_id=request.trace_id,
            thread_id=request.thread_id,
        )

    def _report_skill_invocations(
        self,
        request: ConversationRequest,
        skills_invoked: list[str],
        skill_invocation_count: int,
    ) -> None:
        """Forward skill invocations to the observability layer (best-effort).

        Each invocation is one call; ``skill_invocation_count`` reflects the
        raw count (a single ``read_file`` against the same skill twice yields
        two events). Errors must not change runtime behavior.
        """
        if skill_invocation_count == 0:
            return
        recorder = getattr(self._observability, "event_recorder", None)
        if recorder is None:
            return
        for skill_name in skills_invoked:
            try:
                self._observability.record_skill_invocation(
                    skill_name=skill_name,
                    file_path=f"{SKILL_PATH_PREFIX}{skill_name}/{SKILL_FILE_BASENAME}",
                    session_id=request.session_id,
                    trace_id=request.trace_id,
                    thread_id=request.thread_id,
                )
            except Exception:
                # Observability must never change runtime behavior.
                continue

    async def stream_turn(self, request: ConversationRequest) -> AsyncIterator[dict]:
        payload = {"messages": request.to_agent_messages()}
        config = self._checkpoint_config.invoke_config_for(
            thread_id=request.thread_id,
            metadata={
                "session_id": request.session_id,
                "trace_id": request.trace_id,
                "thread_id": request.thread_id,
                "checkpoint_backend": self._checkpoint_config.backend_type,
            },
            tags=[request.session_id, request.trace_id, request.thread_id],
            callbacks=self._observability.callbacks,
        )

        answer_parts: list[str] = []
        citations: list[dict] = []
        final_messages: list[Any] = []
        reasoning_filter = ReasoningFilter()
        saw_tool_event = False
        answer_started = False

        yield {
            "event": "run.started",
            "data": {
                "session_id": request.session_id,
                "trace_id": request.trace_id,
                "thread_id": request.thread_id,
            },
        }

        async for raw_event in self._astream_events(payload, config):
            normalized = normalize_stream_event(raw_event)
            if not normalized:
                output = raw_event.get("data", {}).get("output") if isinstance(raw_event, dict) else None
                if isinstance(output, dict) and isinstance(output.get("messages"), list):
                    final_messages = output["messages"]
                continue
            if normalized["event"] == "answer.delta":
                text = reasoning_filter.filter(normalized["data"]["text"])
                if not text:
                    continue
                normalized["data"]["text"] = text
                answer_parts.append(text)
                if not answer_started:
                    yield {
                        "event": "answer.started",
                        "data": {"thread_id": request.thread_id},
                    }
                    answer_started = True
            if normalized["event"] == "tool.finished":
                saw_tool_event = True
                citations.extend(normalized["data"].get("citations", []))
                normalized["data"].pop("citations", None)
            if normalized["event"] == "tool.started":
                saw_tool_event = True
                tool_name = normalized["data"].get("name") or ""
                tool_input = normalized["data"].get("input") or {}
                tool_type, skill_name, tool_subtype = self._classify_tool(tool_name, tool_input)
                normalized["data"]["tool_type"] = tool_type
                if skill_name:
                    normalized["data"]["skill_name"] = skill_name
                if tool_subtype:
                    normalized["data"]["tool_subtype"] = tool_subtype
            yield normalized

        answer = self._first_usable_answer("".join(answer_parts))
        if not answer and final_messages:
            answer = self._first_usable_answer(self._last_assistant_content(final_messages))
        if not answer:
            # Last-resort fallback: read structured_response from graph state
            # via async get_state. The agent populates ``structured_response``
            # when ``response_format=TaxAnswer`` is configured, even if no
            # plain assistant text was emitted on the stream.
            structured_answer = await self._structured_response_from_state(request.thread_id)
            if structured_answer:
                answer = structured_answer
        if not answer:
            self._observability.record_event(
                "stream_adapter.error",
                input={"messages": request.to_agent_messages()},
                metadata={
                    "error": "ModelOutputError",
                    "session_id": request.session_id,
                    "trace_id": request.trace_id,
                    "thread_id": request.thread_id,
                    "checkpoint_backend": self._checkpoint_config.backend_type,
                    "partial_answer_length": len("".join(answer_parts)),
                    "saw_tool_event": saw_tool_event,
                    "saw_final_messages": bool(final_messages),
                },
                level="ERROR",
                status_message="Model produced no usable final answer in /chat/stream adapter.",
            )
            yield {
                "event": "run.error",
                "data": {
                    "error": "ModelOutputError",
                    "message": "模型未产生最终回答，可能只输出了 reasoning 或当前模型不支持工具调用。",
                    "thread_id": request.thread_id,
                },
            }
            return
        if not answer_started:
            yield {
                "event": "answer.started",
                "data": {"thread_id": request.thread_id},
            }

        skills_invoked = self._extract_skill_invocations(final_messages) if final_messages else []
        skill_invocation_count = self._count_skill_invocations(final_messages) if final_messages else 0
        if skills_invoked:
            self._report_skill_invocations(
                request=request,
                skills_invoked=skills_invoked,
                skill_invocation_count=skill_invocation_count,
            )

        yield {
            "event": "answer.finished",
            "data": {
                "answer": answer,
                "citations": citations,
                "thread_id": request.thread_id,
                "skills_invoked": skills_invoked,
                "skill_invocation_count": skill_invocation_count,
                "artifact": self._tax_answer_artifact(request, answer, citations),
            },
        }
        yield {
            "event": "run.finished",
            "data": {
                "thread_id": request.thread_id,
            },
        }

    async def _astream_events(self, payload: dict, config: dict) -> AsyncIterator[dict]:
        bounded_config = self._apply_recursion_limit(config)
        try:
            stream = self._agent.astream_events(payload, config=bounded_config, version="v2")
        except TypeError:
            stream = self._agent.astream_events(payload, version="v2")
        async for event in stream:
            yield event

    async def _ainvoke(
        self,
        payload: dict,
        thread_id: str | None = None,
        metadata: dict | None = None,
        tags: list[str] | None = None,
        callbacks: list | None = None,
    ) -> dict:
        config = self._checkpoint_config.invoke_config_for(
            thread_id=thread_id,
            metadata=metadata,
            tags=tags,
            callbacks=callbacks,
        )
        bounded_config = self._apply_recursion_limit(config)
        try:
            return await self._agent.ainvoke(payload, config=bounded_config)
        except TypeError:
            return await self._agent.ainvoke(payload)

    @staticmethod
    def _build_prompt(question: ClassifiedQuestion, plan_steps: list[str]) -> str:
        """Legacy static-plan prompt used only by execute(..., plan_steps=...)."""
        plan_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan_steps))
        return f"""请回答以下税务问题。

问题：{question.text}

意图类别：{question.intent}

执行计划：
{plan_text}

请按照计划逐步回答，最终给出结构化的答案。"""

    @staticmethod
    def _build_native_prompt(question: ClassifiedQuestion) -> str:
        return f"""请回答以下税务问题。

问题：{question.text}

业务标签：{question.intent}

请使用 DeepAgents 原生工作方式完成任务：
1. 对需要多步判断的问题，使用 write_todos 拆解并跟踪任务。
2. 需要法规依据、政策来源或税务定义时，调用 retrieve_tax_context。
3. 回答必须结构化，并引用检索工具返回的 source_id/title。
4. 对税审问题使用 analyze_tax_question 获取术语、场景、历史问题和质询意图分析。
5. 不要输出 <think>...</think> 或其他内部推理标签。"""

    @staticmethod
    def _tax_answer_artifact(request: ConversationRequest, answer: str, citations: list[dict]) -> dict:
        question = AgentExecutor._last_user_content(request.to_agent_messages())
        intent = IntentClassifier._rule_based(question)
        artifact = TaxAnswer(
            question=question,
            intent=intent,
            answer=answer,
            citations=citations,
        )
        return {"kind": "TaxAnswer", "data": artifact.model_dump()}

    @staticmethod
    def _last_user_content(messages: list[Any]) -> str:
        for message in reversed(messages):
            role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
            if role != "user":
                continue
            content = message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")
            if content:
                return str(content)
        return ""

    @staticmethod
    def _last_content(messages: list[Any]) -> str:
        last = messages[-1]
        if isinstance(last, dict):
            return last.get("content", "")
        return getattr(last, "content", "")

    @classmethod
    def _last_assistant_content(cls, messages: list[Any]) -> str:
        for message in reversed(messages):
            role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
            message_type = message.get("type") if isinstance(message, dict) else getattr(message, "type", None)
            class_name = message.__class__.__name__
            if role == "assistant" or message_type == "ai" or class_name == "AIMessage":
                content = message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")
                if content:
                    return content
        return cls._last_content(messages)

    @staticmethod
    def _tool_call_args(call: Any) -> dict:
        if isinstance(call, dict):
            return call.get("args") or {}
        return getattr(call, "args", {}) or {}

    @staticmethod
    def _tool_call_name(call: Any) -> str:
        if isinstance(call, dict):
            return call.get("name") or ""
        return getattr(call, "name", "") or ""

    @staticmethod
    def _message_tool_calls(message: Any) -> list:
        if isinstance(message, dict):
            return message.get("tool_calls") or []
        return getattr(message, "tool_calls", None) or []

    @classmethod
    def _classify_tool(cls, name: str, args: dict) -> tuple[str, str | None, str | None]:
        """Return ``(tool_type, skill_name, tool_subtype)`` for a single tool call.

        ``tool_type`` is one of ``"skill"``, ``"tax"``, ``"other"``.
        ``skill_name`` is populated only when ``tool_type == "skill"``.
        ``tool_subtype`` is ``"exploratory"`` for filesystem exploration tools
        (``ls`` / ``grep`` / ``glob``); otherwise ``None``. Subtype is
        independent of ``tool_type``: an exploratory tool is still
        ``tool_type="other"`` from the business perspective, but
        ``tool_subtype="exploratory"`` flags it for observability.
        """
        skill_name: str | None = None
        tool_subtype: str | None = None
        if name == SKILL_TOOL_NAME:
            file_path = args.get("file_path") or args.get("path") or ""
            match = _SKILL_PATH_RE.match(file_path)
            if match:
                tool_type = "skill"
                skill_name = match.group(1)
            else:
                tool_type = "other"
        elif name in TAX_TOOL_NAMES:
            tool_type = "tax"
        else:
            tool_type = "other"
        if name in EXPLORATORY_TOOL_NAMES:
            tool_subtype = "exploratory"
        return tool_type, skill_name, tool_subtype

    @classmethod
    def _extract_skill_invocations(cls, messages: list[Any]) -> list[str]:
        """Return unique skill names in the order they were first invoked.

        Walks ``AIMessage.tool_calls`` looking for ``read_file`` calls whose
        ``file_path`` (or ``path``) starts with ``/skills/<name>/``.
        """
        seen: list[str] = []
        for message in messages:
            for call in cls._message_tool_calls(message):
                name = cls._tool_call_name(call)
                if name != SKILL_TOOL_NAME:
                    continue
                tool_type, skill_name, _ = cls._classify_tool(name, cls._tool_call_args(call))
                if tool_type == "skill" and skill_name and skill_name not in seen:
                    seen.append(skill_name)
        return seen

    @classmethod
    def _count_skill_invocations(cls, messages: list[Any]) -> int:
        """Count *every* ``read_file`` call against a skill path (not deduped)."""
        total = 0
        for message in messages:
            for call in cls._message_tool_calls(message):
                name = cls._tool_call_name(call)
                if name != SKILL_TOOL_NAME:
                    continue
                tool_type, _, _ = cls._classify_tool(name, cls._tool_call_args(call))
                if tool_type == "skill":
                    total += 1
        return total

    @classmethod
    def _collect_tool_events(cls, messages: list[Any]) -> list[dict]:
        """Emit one event per tool call (AIMessage) plus per tool message.

        Legacy shape: each event has a ``name`` field.
        Added fields: ``tool_type`` (``"skill"`` | ``"tax"`` | ``"other"``),
        ``tool_subtype`` (``"exploratory"`` for ``ls``/``grep``/``glob``,
        else ``None``), ``args`` (truncated dict), and ``skill_name`` (only
        for skill events).
        """
        events: list[dict] = []
        for message in messages:
            calls = cls._message_tool_calls(message)
            if calls:
                for call in calls:
                    name = cls._tool_call_name(call)
                    args = cls._tool_call_args(call)
                    if not name:
                        continue
                    tool_type, skill_name, tool_subtype = cls._classify_tool(name, args)
                    event: dict = {"name": name, "tool_type": tool_type}
                    if tool_type == "skill" and skill_name:
                        event["skill_name"] = skill_name
                    if tool_subtype:
                        event["tool_subtype"] = tool_subtype
                    if args:
                        event["args"] = {k: cls._truncate_for_log(v) for k, v in args.items()}
                    events.append(event)
            else:
                name = message.get("name") if isinstance(message, dict) else getattr(message, "name", None)
                if not name:
                    continue
                event = {"name": name, "tool_type": "other"}
                _, _, tool_subtype = cls._classify_tool(name, {})
                if tool_subtype:
                    event["tool_subtype"] = tool_subtype
                events.append(event)
        return events

    @staticmethod
    def _truncate_for_log(value: Any, max_len: int = 200) -> Any:
        if isinstance(value, str) and len(value) > max_len:
            return value[:max_len] + "..."
        return value

    _UNUSABLE_ANSWER_PHRASES = frozenset(
        {
            "待生成",
            "正在生成",
            "未生成",
            "暂无回答",
            "无回答",
            "分析结论已生成",
        }
    )

    @classmethod
    def _is_unusable_answer(cls, answer: str) -> bool:
        """Return True when ``answer`` is a known placeholder/draft that
        must not be surfaced as the final answer.

        Mirrors the master ``a94ceaf`` semantics — ported for V4. Filters:
            - short placeholder phrases in the known set
            - phrases ≤ 12 chars containing ``已生成`` / ``已完成``
            - tool-call drafts that look like ``[{name:..., parameters:...}]``
        """
        if not answer:
            return True
        normalized = answer.strip().strip("。.!！")
        if normalized in cls._UNUSABLE_ANSWER_PHRASES:
            return True
        if len(normalized) <= 12 and ("已生成" in normalized or "已完成" in normalized):
            return True
        compact = normalized.replace(" ", "")
        looks_like_tool_call_draft = (
            compact.startswith("[")
            and '"name"' in compact
            and '"parameters"' in compact
            and (
                "find_tax_authorities" in compact
                or "analyze_tax_question" in compact
                or "retrieve_tax_context" in compact
            )
        )
        return looks_like_tool_call_draft

    @classmethod
    def _first_usable_answer(cls, *candidates: str) -> str:
        """Return the first candidate that passes ``_is_unusable_answer``.

        Each candidate is run through ``_clean_answer`` first so stray
        whitespace / reasoning tags are stripped before the unusable check.
        Empty string when no candidate qualifies.
        """
        for candidate in candidates:
            cleaned = cls._clean_answer(candidate or "")
            if cleaned and not cls._is_unusable_answer(cleaned):
                return cleaned
        return ""

    @staticmethod
    def _placeholder_retry_prompt() -> str:
        return (
            "上一轮没有生成可用的最终回答。不要返回「待生成」「暂无回答」等占位文本，"
            "也不要把工具调用草稿或 JSON 参数列表当作最终回答；"
            "请直接针对原始税务问题生成完整、结构化的中文回答，并在需要法规依据时调用工具。"
        )

    async def _structured_response_from_state(self, thread_id: str) -> str:
        """Return the structured_response.answer from graph state, or empty.

        Best-effort: errors are swallowed and the empty string is returned.
        The agent must expose ``aget_state`` (preferred) or ``get_state``;
        if neither is available, an empty answer is returned (caller will
        surface ``ModelOutputError``).
        """
        try:
            state = await self.aget_state(thread_id)
        except (NotImplementedError, Exception):
            return ""
        if not isinstance(state, dict):
            return ""
        values = state.get("values") if isinstance(state.get("values"), dict) else {}
        sr = values.get("structured_response") if isinstance(values, dict) else None
        if not isinstance(sr, dict):
            return ""
        candidate = sr.get("answer") or ""
        return self._first_usable_answer(candidate)

    @staticmethod
    def _apply_recursion_limit(config: dict, limit: int = DEFAULT_RECURSION_LIMIT) -> dict:
        """Inject ``recursion_limit`` into a LangGraph invoke config.

        Returns a new dict (callers' config is not mutated). An existing
        ``recursion_limit`` in ``config`` wins — the helper only fills it in
        when absent.
        """
        merged = dict(config)
        merged.setdefault("recursion_limit", limit)
        return merged

    @staticmethod
    def _skills_from_domain_analysis(domain_analysis: dict) -> list[str]:
        skills = []
        if domain_analysis.get("intent_hypotheses"):
            skills.append("audit-intent-inference")
        if domain_analysis.get("terms"):
            skills.append("tax-finance-logic-decomposition")
        if domain_analysis.get("scenario_matches"):
            skills.append("audit-scenario-recognition")
        if domain_analysis.get("historical_references"):
            skills.append("historical-question-matching")
        if domain_analysis.get("scenario_matches") or domain_analysis.get("historical_references"):
            skills.append("solution-generation")
        return skills

    @staticmethod
    def _structured_result(result: dict) -> tuple[str, list[dict]]:
        structured = result.get("structured_response")
        if not structured:
            return "", []
        if isinstance(structured, BaseModel):
            data = structured.model_dump()
        elif isinstance(structured, dict):
            data = structured
        else:
            return "", []
        return data.get("answer", ""), data.get("citations", [])

    @staticmethod
    def _clean_answer(answer: str) -> str:
        return ReasoningFilter().filter(answer).strip()

    def get_state(self, thread_id: str) -> dict:
        if not hasattr(self._agent, "get_state"):
            raise NotImplementedError("Agent does not expose get_state")
        state = self._agent.get_state(self._checkpoint_config.invoke_config_for(thread_id=thread_id))
        return self._jsonable_state(state)

    def get_state_history(self, thread_id: str) -> list[dict]:
        if not hasattr(self._agent, "get_state_history"):
            raise NotImplementedError("Agent does not expose get_state_history")
        history = self._agent.get_state_history(self._checkpoint_config.invoke_config_for(thread_id=thread_id))
        return [self._jsonable_state(item) for item in history]

    async def aget_state(self, thread_id: str) -> dict:
        """Async counterpart of :meth:`get_state`.

        Prefers the agent's ``aget_state`` (async) — required when called from
        inside an ``astream_events`` loop where a sync ``get_state`` would
        raise ``InvalidStateError`` (langgraph thread guard). Falls back to
        the sync ``get_state`` if the agent only exposes the sync version.
        """
        config = self._checkpoint_config.invoke_config_for(thread_id=thread_id)
        if hasattr(self._agent, "aget_state"):
            state = await self._agent.aget_state(config)
        elif hasattr(self._agent, "get_state"):
            state = self._agent.get_state(config)
        else:
            raise NotImplementedError("Agent does not expose get_state / aget_state")
        return self._jsonable_state(state)

    async def aget_state_history(self, thread_id: str) -> list[dict]:
        """Async counterpart of :meth:`get_state_history`."""
        config = self._checkpoint_config.invoke_config_for(thread_id=thread_id)
        if hasattr(self._agent, "aget_state_history"):
            history: list[Any] = []
            async for item in self._agent.aget_state_history(config):
                history.append(item)
        elif hasattr(self._agent, "get_state_history"):
            history = list(self._agent.get_state_history(config))
        else:
            raise NotImplementedError("Agent does not expose get_state_history / aget_state_history")
        return [self._jsonable_state(item) for item in history]

    @staticmethod
    def _jsonable_state(value: Any) -> dict:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, dict):
            return value
        return {"repr": repr(value)}
