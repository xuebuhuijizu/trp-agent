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
from tax_agent.domain.intent_classifier import ClassifiedQuestion
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
            response_format=TaxAnswer,
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
        answer = self._clean_answer(structured_answer or self._last_assistant_content(messages))
        if not answer:
            raise ModelOutputError("模型未产生最终回答，可能只输出了 reasoning 或当前模型不支持工具调用。")
        return ExecutionResult(
            answer=answer,
            citations=citations,
            tool_events=self._collect_tool_events(messages),
            domain_analysis=domain_analysis,
            skills=self._skills_from_domain_analysis(domain_analysis),
            session_id=request.session_id,
            trace_id=request.trace_id,
            thread_id=request.thread_id,
        )

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
            yield normalized

        answer = self._clean_answer("".join(answer_parts))
        if not answer and final_messages:
            answer = self._clean_answer(self._last_assistant_content(final_messages))
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
        yield {
            "event": "answer.finished",
            "data": {
                "answer": answer,
                "citations": citations,
                "thread_id": request.thread_id,
            },
        }
        yield {
            "event": "run.finished",
            "data": {
                "thread_id": request.thread_id,
            },
        }

    async def _astream_events(self, payload: dict, config: dict) -> AsyncIterator[dict]:
        try:
            stream = self._agent.astream_events(payload, config=config, version="v2")
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
        try:
            return await self._agent.ainvoke(payload, config=config)
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
    def _collect_tool_events(messages: list[Any]) -> list[dict]:
        events = []
        for message in messages:
            name = message.get("name") if isinstance(message, dict) else getattr(message, "name", None)
            if not name:
                continue
            events.append({"name": name})
        return events

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

    @staticmethod
    def _jsonable_state(value: Any) -> dict:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, dict):
            return value
        return {"repr": repr(value)}
