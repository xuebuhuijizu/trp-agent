from types import SimpleNamespace

import pytest

from tax_agent.config import AgentConfig
from tax_agent.runtime.agent_executor import AgentExecutor
from tax_agent.runtime.conversation import ConversationMessage, ConversationRequest


def _chat_payload() -> dict:
    return {
        "session_id": "sess-stream",
        "trace_id": "trace-stream",
        "thread_id": "thread-stream",
        "messages": [{"role": "user", "content": "stream this answer"}],
    }


def test_chat_stream_uses_executor_stream_turn_instead_of_execute_turn():
    from fastapi.testclient import TestClient

    from tax_agent.service.service_app import create_app

    class FakeExecutor:
        async def execute_turn(self, request):
            raise AssertionError("/chat/stream must not call execute_turn")

        async def stream_turn(self, request):
            yield {"event": "agent.message.delta", "data": {"text": "first "}}
            yield {"event": "agent.message.delta", "data": {"text": "second"}}
            yield {
                "event": "run.finished",
                "data": {
                    "answer": "first second",
                    "citations": [],
                    "thread_id": request.thread_id,
                },
            }

    app = create_app(lambda: FakeExecutor())

    with TestClient(app) as client:
        with client.stream("POST", "/chat/stream", json=_chat_payload()) as response:
            body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert body.count("event: agent.message.delta") == 2
    assert "first " in body
    assert "second" in body
    assert "event: run.finished" in body


@pytest.mark.asyncio
async def test_execute_stream_turn_maps_astream_events_to_stable_events():
    class FakeStreamAgent:
        def __init__(self):
            self.payload = None
            self.config = None
            self.version = None

        async def astream_events(self, payload, config=None, version="v2"):
            self.payload = payload
            self.config = config
            self.version = version
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": SimpleNamespace(content="hello ")},
            }
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": {"content": "world"}},
            }
            yield {
                "event": "on_tool_start",
                "name": "retrieve_tax_context",
                "data": {"input": {"query": "vat"}},
            }
            yield {
                "event": "on_tool_end",
                "name": "retrieve_tax_context",
                "data": {
                    "output": '{"sources":[{"source_id":"vat-regulation","title":"VAT"}]}'
                },
            }

    fake_agent = FakeStreamAgent()
    executor = AgentExecutor(AgentConfig(), agent=fake_agent)
    request = ConversationRequest(
        session_id="sess-stream",
        trace_id="trace-stream",
        thread_id="thread-stream",
        messages=[ConversationMessage(role="user", content="stream this answer")],
    )

    events = [event async for event in executor.stream_turn(request)]

    assert fake_agent.payload == {"messages": request.to_agent_messages()}
    assert fake_agent.config["configurable"]["thread_id"] == "thread-stream"
    assert fake_agent.config["metadata"]["trace_id"] == "trace-stream"
    assert fake_agent.version == "v2"
    assert events == [
        {"event": "agent.message.delta", "data": {"text": "hello "}},
        {"event": "agent.message.delta", "data": {"text": "world"}},
        {
            "event": "tool.started",
            "data": {"name": "retrieve_tax_context", "input": {"query": "vat"}},
        },
        {
            "event": "tool.finished",
            "data": {
                "name": "retrieve_tax_context",
                "source_ids": ["vat-regulation"],
            },
        },
        {
            "event": "run.finished",
            "data": {
                "answer": "hello world",
                "citations": [{"source_id": "vat-regulation", "title": "VAT"}],
                "thread_id": "thread-stream",
            },
        },
    ]

