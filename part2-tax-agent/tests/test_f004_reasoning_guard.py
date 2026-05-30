from types import SimpleNamespace

import pytest

from tax_agent.config import AgentConfig
from tax_agent.runtime.agent_executor import AgentExecutor
from tax_agent.runtime.conversation import ConversationMessage, ConversationRequest
from tax_agent.runtime.observability import ObservabilityConfig


@pytest.mark.asyncio
async def test_stream_turn_suppresses_reasoning_only_output():
    class FakeReasoningOnlyAgent:
        async def astream_events(self, payload, config=None, version="v2"):
            yield {"event": "on_chat_model_stream", "data": {"chunk": SimpleNamespace(content="<think>用户")}}
            yield {"event": "on_chat_model_stream", "data": {"chunk": {"content": "询问增值税"}}}

    executor = AgentExecutor(AgentConfig(checkpoint_backend="memory"), agent=FakeReasoningOnlyAgent())
    request = ConversationRequest(
        session_id="sess",
        trace_id="trace",
        thread_id="thread",
        messages=[ConversationMessage(role="user", content="解释增值税")],
    )

    events = [event async for event in executor.stream_turn(request)]

    assert events == [
        {
            "event": "run.error",
            "data": {
                "error": "ModelOutputError",
                "message": "模型未产生最终回答，可能只输出了 reasoning 或当前模型不支持工具调用。",
                "thread_id": "thread",
            },
        }
    ]


@pytest.mark.asyncio
async def test_stream_turn_records_langfuse_adapter_error_for_reasoning_only_output():
    class FakeReasoningOnlyAgent:
        async def astream_events(self, payload, config=None, version="v2"):
            yield {"event": "on_chat_model_stream", "data": {"chunk": SimpleNamespace(content="<think>用户")}}
            yield {"event": "on_chat_model_stream", "data": {"chunk": {"content": "询问增值税"}}}

    recorded = []

    def record_event(**payload):
        recorded.append(payload)

    executor = AgentExecutor(AgentConfig(checkpoint_backend="memory"), agent=FakeReasoningOnlyAgent())
    executor._observability = ObservabilityConfig(
        provider="langfuse",
        callbacks=[],
        event_recorder=record_event,
    )
    request = ConversationRequest(
        session_id="sess",
        trace_id="trace",
        thread_id="thread",
        messages=[ConversationMessage(role="user", content="解释增值税")],
    )

    events = [event async for event in executor.stream_turn(request)]

    assert events[-1]["event"] == "run.error"
    assert recorded == [
        {
            "name": "stream_adapter.error",
            "input": {"messages": request.to_agent_messages()},
            "output": None,
            "metadata": {
                "error": "ModelOutputError",
                "session_id": "sess",
                "trace_id": "trace",
                "thread_id": "thread",
                "checkpoint_backend": "memory",
                "partial_answer_length": 0,
                "saw_tool_event": False,
                "saw_final_messages": False,
            },
            "level": "ERROR",
            "status_message": "Model produced no usable final answer in /chat/stream adapter.",
        }
    ]
