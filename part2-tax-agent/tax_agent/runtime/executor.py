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
from typing import Any

from pydantic import BaseModel

from tax_agent.agent.graph import build_tax_agent
from tax_agent.business.analysis.intent_classifier import ClassifiedQuestion, IntentClassifier
from tax_agent.business.analysis.tax_context import analyze_tax_context
from tax_agent.business.answers.models import TaxAnswer, TaxCitation
from tax_agent.business.references.tools import extract_citations_from_messages
from tax_agent.runtime.ag_ui import (
    AgUiRunContext,
    normalize_ag_ui_event,
    run_error_event,
    run_finished_event,
    run_started_event,
    text_message_content_event,
    text_message_end_event,
    text_message_start_event,
)
from tax_agent.runtime.checkpointing import (
    CheckpointConfig,
    build_async_checkpoint_config,
    build_checkpoint_config,
)
from tax_agent.runtime.config import AgentConfig
from tax_agent.runtime.conversation import ConversationRequest
from tax_agent.runtime.observability import build_langfuse_observability


@dataclass
class ExecutionResult:
    answer: str
    citations: list[dict] = field(default_factory=list)
    tool_events: list[dict] = field(default_factory=list)
    domain_analysis: dict = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)
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
        return build_tax_agent(config, checkpointer=checkpointer)

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
            artifact=self._tax_answer_artifact(request, answer, citations),
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
        text_started = False
        context = AgUiRunContext.from_request(request)

        yield run_started_event(context)

        async for raw_event in self._astream_events(payload, config):
            normalized_events = normalize_ag_ui_event(raw_event, context)
            if not normalized_events:
                output = raw_event.get("data", {}).get("output") if isinstance(raw_event, dict) else None
                if isinstance(output, dict) and isinstance(output.get("messages"), list):
                    final_messages = output["messages"]
                continue
            for normalized in normalized_events:
                if normalized["event"] == "TEXT_MESSAGE_CONTENT":
                    text = reasoning_filter.filter(normalized["data"]["delta"])
                    if not text:
                        continue
                    normalized["data"]["delta"] = text
                    answer_parts.append(text)
                    if not text_started:
                        yield text_message_start_event(context)
                        text_started = True
                if normalized["event"] == "TOOL_CALL_RESULT":
                    saw_tool_event = True
                    citations.extend(normalized["data"].get("citations", []))
                if normalized["event"] == "TOOL_CALL_START":
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
                **run_error_event(
                    context,
                    "ModelOutputError",
                    "模型未产生最终回答，可能只输出了 reasoning 或当前模型不支持工具调用。",
                )
            }
            return
        if not text_started:
            yield text_message_start_event(context)
            yield text_message_content_event(context, answer)
        yield text_message_end_event(context)
        yield run_finished_event(context, self._tax_answer_artifact(request, answer, citations))

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
2. 需要法规依据、政策来源或税务定义时，调用 find_tax_authorities。
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

