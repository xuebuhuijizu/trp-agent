from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from tax_agent.service.service_app import create_app


def _chat_payload() -> dict:
    return {
        "session_id": "sess-route",
        "trace_id": "trace-route",
        "thread_id": "thread-route",
        "messages": [{"role": "user", "content": "hello"}],
    }


def test_chat_route_returns_final_response_with_checkpoint_metadata():
    class FakeExecutor:
        checkpoint_backend_type = "memory"
        observability_provider = "none"

        async def execute_turn(self, request):
            return SimpleNamespace(
                answer="route answer",
                citations=[{"source_id": "demo", "title": "Demo"}],
            )

    app = create_app(lambda: FakeExecutor())

    with TestClient(app) as client:
        response = client.post("/chat", json=_chat_payload())

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "sess-route",
        "trace_id": "trace-route",
        "thread_id": "thread-route",
        "answer": "route answer",
        "citations": [{"source_id": "demo", "title": "Demo"}],
        "checkpoint": {"backend_type": "memory", "thread_id": "thread-route"},
        "observability": {"provider": "none"},
    }


def test_chat_route_accepts_async_executor_factory():
    class FakeExecutor:
        checkpoint_backend_type = "sqlite"
        observability_provider = "none"

        async def execute_turn(self, request):
            return SimpleNamespace(answer="async factory answer", citations=[])

    async def build_executor():
        return FakeExecutor()

    app = create_app(build_executor)

    with TestClient(app) as client:
        response = client.post("/chat", json=_chat_payload())

    assert response.status_code == 200
    assert response.json()["answer"] == "async factory answer"
    assert response.json()["checkpoint"]["backend_type"] == "sqlite"


def test_state_and_history_routes_use_executor_state_accessors():
    class FakeExecutor:
        def get_state(self, thread_id):
            return {"thread_id": thread_id, "messages": ["latest"]}

        def get_state_history(self, thread_id):
            return [{"checkpoint_id": "cp-1", "thread_id": thread_id}]

    app = create_app(lambda: FakeExecutor())

    with TestClient(app) as client:
        state_response = client.get("/threads/thread-route/state")
        history_response = client.get("/threads/thread-route/history")

    assert state_response.status_code == 200
    assert state_response.json()["state"]["messages"] == ["latest"]
    assert history_response.status_code == 200
    assert history_response.json()["history"][0]["checkpoint_id"] == "cp-1"


def test_batch_route_writes_outputs_from_uploaded_input_path(tmp_path):
    input_file = tmp_path / "questions.txt"
    input_file.write_text("What is VAT?", encoding="utf-8")

    class FakeExecutor:
        output_dir = str(tmp_path / "output")

        async def execute_turn(self, request):
            return SimpleNamespace(
                answer="batch answer",
                citations=[],
                tool_events=[],
                domain_analysis={},
                skills=[],
            )

    app = create_app(lambda: FakeExecutor())

    with TestClient(app) as client:
        response = client.post(
            "/batch",
            json={
                "session_id": "sess-batch-route",
                "trace_id": "trace-batch-route",
                "input_file": str(input_file),
                "thread_strategy": "per_question",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["total_questions"] == 1
    assert Path(payload["output_paths"]["markdown"]).exists()
    assert Path(payload["output_paths"]["json"]).exists()


def test_sqlite_checkpoint_script_reports_missing_dependency_when_not_installed(tmp_path):
    import importlib.util

    if importlib.util.find_spec("langgraph.checkpoint.sqlite") is not None:
        return

    import check_sqlite_checkpoint_persistence as sqlite_check

    result = sqlite_check.main(["--output", str(tmp_path), "--thread-id", "thread-sqlite"])

    assert result == 2
