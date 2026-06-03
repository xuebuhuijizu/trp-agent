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

    from tax_agent.delivery.http_api import create_app

    class FakeExecutor:
        async def execute_turn(self, request):
            raise AssertionError("/chat/stream must not call execute_turn")

        async def stream_turn(self, request):
            yield {"event": "TEXT_MESSAGE_START", "data": {"messageId": "msg-1", "role": "assistant"}}
            yield {"event": "TEXT_MESSAGE_CONTENT", "data": {"messageId": "msg-1", "delta": "first "}}
            yield {"event": "TEXT_MESSAGE_CONTENT", "data": {"messageId": "msg-1", "delta": "second"}}
            yield {
                "event": "TEXT_MESSAGE_END",
                "data": {"messageId": "msg-1"},
            }
            yield {
                "event": "RUN_FINISHED",
                "data": {
                    "threadId": request.thread_id,
                    "result": {"kind": "TaxAnswer", "data": {"answer": "first second", "citations": []}},
                },
            }

    app = create_app(lambda: FakeExecutor())

    with TestClient(app) as client:
        with client.stream("POST", "/chat/stream", json=_chat_payload()) as response:
            body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "charset=utf-8" in response.headers["content-type"]
    assert "event: TEXT_MESSAGE_START" in body
    assert body.count("event: TEXT_MESSAGE_CONTENT") == 2
    assert "event: TEXT_MESSAGE_END" in body
    assert "first " in body
    assert "second" in body
    assert "event: RUN_FINISHED" in body


def test_chat_stream_ignores_removed_progress_mode_field():
    from fastapi.testclient import TestClient

    from tax_agent.delivery.http_api import create_app

    class FakeExecutor:
        async def stream_turn(self, request):
            yield {"event": "TEXT_MESSAGE_START", "data": {"messageId": "msg-1", "role": "assistant"}}
            yield {"event": "TEXT_MESSAGE_CONTENT", "data": {"messageId": "msg-1", "delta": "hidden"}}
            yield {
                "event": "TEXT_MESSAGE_END",
                "data": {"messageId": "msg-1"},
            }
            yield {
                "event": "RUN_FINISHED",
                "data": {
                    "threadId": request.thread_id,
                    "result": {"kind": "TaxAnswer", "data": {"answer": "final answer", "citations": []}},
                },
            }

    payload = {**_chat_payload(), "interaction_mode": "progress_stream"}
    app = create_app(lambda: FakeExecutor())

    with TestClient(app) as client:
        with client.stream("POST", "/chat/stream", json=payload) as response:
            body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "event: TEXT_MESSAGE_START" in body
    assert "event: TEXT_MESSAGE_CONTENT" in body
    assert "hidden" in body
    assert "event: TEXT_MESSAGE_END" in body
    assert "final answer" in body


def test_chat_stream_ignores_removed_structured_final_mode_field():
    from fastapi.testclient import TestClient

    from tax_agent.delivery.http_api import create_app

    class FakeExecutor:
        async def stream_turn(self, request):
            assert not hasattr(request, "interaction_mode")
            yield {"event": "RUN_FINISHED", "data": {"threadId": request.thread_id, "result": {"answer": "ok"}}}

    payload = {**_chat_payload(), "interaction_mode": "structured_final"}
    app = create_app(lambda: FakeExecutor())

    with TestClient(app) as client:
        response = client.post("/chat/stream", json=payload)

    assert response.status_code == 200
    assert "event: RUN_FINISHED" in response.text


@pytest.mark.asyncio
async def test_execute_stream_turn_maps_astream_events_to_ag_ui_events():
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
                "name": "find_tax_authorities",
                "data": {"input": {"query": "vat"}},
            }
            yield {
                "event": "on_tool_end",
                "name": "find_tax_authorities",
                "data": {
                    "output": '{"citations":[{"citation_id":"local_tax_authorities:vat-regulation","source_id":"vat-regulation","source_type":"law","provider_id":"local_tax_authorities","title":"VAT","locator":null,"snippet":"VAT","confidence":0.9,"retrieved_at":null,"metadata":{}}]}'
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
        {
            "event": "RUN_STARTED",
            "data": {
                "runId": "trace-stream",
                "threadId": "thread-stream",
            },
        },
        {
            "event": "TEXT_MESSAGE_START",
            "data": {"messageId": "trace-stream:assistant", "role": "assistant"},
        },
        {
            "event": "TEXT_MESSAGE_CONTENT",
            "data": {"messageId": "trace-stream:assistant", "delta": "hello "},
        },
        {
            "event": "TEXT_MESSAGE_CONTENT",
            "data": {"messageId": "trace-stream:assistant", "delta": "world"},
        },
        {
            "event": "TOOL_CALL_START",
            "data": {
                "toolCallId": "trace-stream:tool:1",
                "toolName": "find_tax_authorities",
            },
        },
        {
            "event": "TOOL_CALL_ARGS",
            "data": {
                "toolCallId": "trace-stream:tool:1",
                "args": {"query": "vat"},
            },
        },
        {
            "event": "TOOL_CALL_END",
            "data": {"toolCallId": "trace-stream:tool:1"},
        },
        {
            "event": "TOOL_CALL_RESULT",
            "data": {
                "toolCallId": "trace-stream:tool:1",
                "toolName": "find_tax_authorities",
                "sourceIds": ["vat-regulation"],
                "citations": [
                    {
                        "citation_id": "local_tax_authorities:vat-regulation",
                        "source_id": "vat-regulation",
                        "source_type": "law",
                        "provider_id": "local_tax_authorities",
                        "title": "VAT",
                        "locator": None,
                        "snippet": "VAT",
                        "confidence": 0.9,
                        "retrieved_at": None,
                        "metadata": {},
                        }
                    ],
                "summary": "VAT",
            },
        },
        {
            "event": "TEXT_MESSAGE_END",
            "data": {"messageId": "trace-stream:assistant"},
        },
        {
            "event": "RUN_FINISHED",
            "data": {
                "runId": "trace-stream",
                "threadId": "thread-stream",
                "result": {
                    "kind": "TaxAnswer",
                    "data": {
                        "question": "stream this answer",
                        "intent": "definition",
                        "answer": "hello world",
                            "citations": [
                                {
                                    "citation_id": "local_tax_authorities:vat-regulation",
                                    "source_id": "vat-regulation",
                                    "source_type": "law",
                                    "provider_id": "local_tax_authorities",
                                    "title": "VAT",
                                    "locator": None,
                                    "snippet": "VAT",
                                    "confidence": 0.9,
                                    "retrieved_at": None,
                                    "metadata": {},
                                }
                            ],
                    },
                },
            },
        },
    ]

