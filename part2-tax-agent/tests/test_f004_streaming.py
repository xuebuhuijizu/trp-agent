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
            yield {"event": "answer.started", "data": {"thread_id": request.thread_id}}
            yield {"event": "answer.delta", "data": {"text": "first "}}
            yield {"event": "answer.delta", "data": {"text": "second"}}
            yield {
                "event": "answer.finished",
                "data": {
                    "answer": "first second",
                    "citations": [],
                    "thread_id": request.thread_id,
                },
            }
            yield {
                "event": "run.finished",
                "data": {
                    "thread_id": request.thread_id,
                },
            }

    app = create_app(lambda: FakeExecutor())

    with TestClient(app) as client:
        with client.stream("POST", "/chat/stream", json=_chat_payload()) as response:
            body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "charset=utf-8" in response.headers["content-type"]
    assert "event: answer.started" in body
    assert body.count("event: answer.delta") == 2
    assert "event: answer.finished" in body
    assert "first " in body
    assert "second" in body
    assert "event: run.finished" in body


def test_chat_stream_progress_mode_filters_answer_delta():
    from fastapi.testclient import TestClient

    from tax_agent.service.service_app import create_app

    class FakeExecutor:
        async def stream_turn(self, request):
            yield {"event": "answer.started", "data": {"thread_id": request.thread_id}}
            yield {"event": "answer.delta", "data": {"text": "hidden"}}
            yield {
                "event": "answer.finished",
                "data": {
                    "answer": "final answer",
                    "citations": [],
                    "thread_id": request.thread_id,
                },
            }
            yield {"event": "run.finished", "data": {"thread_id": request.thread_id}}

    payload = {**_chat_payload(), "interaction_mode": "progress_stream"}
    app = create_app(lambda: FakeExecutor())

    with TestClient(app) as client:
        with client.stream("POST", "/chat/stream", json=payload) as response:
            body = response.read().decode("utf-8")

    assert response.status_code == 200
    assert "event: answer.started" in body
    assert "event: answer.delta" not in body
    assert "hidden" not in body
    assert "event: answer.finished" in body
    assert "final answer" in body


def test_chat_stream_rejects_structured_final_interaction_mode():
    from fastapi.testclient import TestClient

    from tax_agent.service.service_app import create_app

    class FakeExecutor:
        async def stream_turn(self, request):
            raise AssertionError("invalid interaction mode should be rejected before streaming")

    payload = {**_chat_payload(), "interaction_mode": "structured_final"}
    app = create_app(lambda: FakeExecutor())

    with TestClient(app) as client:
        response = client.post("/chat/stream", json=payload)

    assert response.status_code == 400
    assert response.json()["error"] == "InvalidInteractionMode"


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
            "event": "run.started",
            "data": {
                "session_id": "sess-stream",
                "trace_id": "trace-stream",
                "thread_id": "thread-stream",
            },
        },
        {"event": "answer.started", "data": {"thread_id": "thread-stream"}},
        {"event": "answer.delta", "data": {"text": "hello "}},
        {"event": "answer.delta", "data": {"text": "world"}},
        {
            "event": "tool.started",
            "data": {"name": "find_tax_authorities", "input": {"query": "vat"}},
        },
        {
            "event": "tool.finished",
            "data": {
                "name": "find_tax_authorities",
                "source_ids": ["vat-regulation"],
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
        {
            "event": "answer.finished",
            "data": {
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
                "thread_id": "thread-stream",
                "artifact": {
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
        {
            "event": "run.finished",
            "data": {
                "thread_id": "thread-stream",
            },
        },
    ]

