import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tax_agent.config import AgentConfig
from tax_agent.business.analysis.tax_context import analyze_tax_context
from tax_agent.runtime.agent_executor import AgentExecutor
from tax_agent.runtime.checkpointing import build_async_checkpoint_config, build_checkpoint_config
from tax_agent.runtime.conversation import ConversationMessage, ConversationRequest


class FakeAgent:
    def __init__(self, result):
        self.result = result
        self.payload = None
        self.config = None

    async def ainvoke(self, payload, config=None):
        self.payload = payload
        self.config = config
        return self.result


def test_conversation_request_converts_messages_for_agent():
    request = ConversationRequest(
        session_id="sess-1",
        trace_id="trace-1",
        thread_id="thread-1",
        messages=[
            ConversationMessage(role="user", content="解释增值税"),
            ConversationMessage(role="assistant", content="需要看业务类型"),
        ],
    )

    assert request.to_agent_messages() == [
        {"role": "user", "content": "解释增值税"},
        {"role": "assistant", "content": "需要看业务类型"},
    ]


def test_analyze_tax_context_uses_previous_turns():
    analysis = analyze_tax_context(
        [
            {"role": "user", "content": "我们先讨论增值税。"},
            {"role": "assistant", "content": "可以。"},
            {"role": "user", "content": "那进项税额呢？"},
        ]
    )

    terms = {match["term"] for match in analysis["terms"]}
    assert {"增值税", "进项税额"}.issubset(terms)


def test_execute_turn_passes_messages_and_thread_id_to_agent():
    agent = FakeAgent(
        {
            "messages": [
                {"role": "assistant", "content": "fallback"},
                {"role": "user", "content": "not the answer"},
            ],
            "structured_response": {
                "question": "那进项税额呢？",
                "intent": "compliance",
                "answer": "structured answer",
                "citations": [{"source_id": "vat-regulation", "title": "增值税暂行条例"}],
            },
        }
    )
    executor = AgentExecutor(AgentConfig(), agent=agent)
    request = ConversationRequest(
        session_id="sess-1",
        trace_id="trace-1",
        thread_id="thread-abc",
        messages=[
            ConversationMessage(role="user", content="我们先讨论增值税。"),
            ConversationMessage(role="assistant", content="可以。"),
            ConversationMessage(role="user", content="那进项税额呢？"),
        ],
    )

    result = asyncio.run(executor.execute_turn(request))

    assert agent.payload == {"messages": request.to_agent_messages()}
    assert agent.config["configurable"]["thread_id"] == "thread-abc"
    assert agent.config["metadata"]["session_id"] == "sess-1"
    assert agent.config["metadata"]["trace_id"] == "trace-1"
    assert result.answer == "structured answer"
    assert result.thread_id == "thread-abc"
    assert {"增值税", "进项税额"}.issubset({match["term"] for match in result.domain_analysis["terms"]})


def test_checkpoint_config_uses_stable_service_sqlite_path_by_default(tmp_path):
    config = build_checkpoint_config(output_dir=tmp_path, backend_type="memory")

    assert config.thread_id == "service"
    assert config.invoke_config["configurable"]["thread_id"] == "service"


def test_checkpoint_config_uses_run_id_for_explicit_run_scoped_path(tmp_path):
    config = build_checkpoint_config(output_dir=tmp_path, run_id="run-123", backend_type="memory")

    assert config.thread_id == "run-123"
    assert config.invoke_config["configurable"]["thread_id"] == "run-123"


@pytest.mark.asyncio
async def test_async_checkpoint_config_uses_stable_service_sqlite_path_by_default(tmp_path):
    config = await build_async_checkpoint_config(output_dir=tmp_path, backend_type="sqlite")

    assert config.thread_id == "service"
    assert config.backend_type == "sqlite"
    assert config.path == str(tmp_path / "checkpoints" / "service.sqlite")


def test_opengauss_checkpoint_does_not_fallback_when_dependency_missing(tmp_path, monkeypatch):
    import builtins
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if "langgraph.checkpoint.postgres" in name:
            raise ImportError("Mocked: langgraph-checkpoint-postgres not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    with pytest.raises(RuntimeError, match="langgraph-checkpoint-postgres"):
        build_checkpoint_config(
            output_dir=tmp_path,
            backend_type="opengauss",
            dsn="postgresql://user:password@localhost:5432/postgres",
        )


def test_sse_event_renderer_outputs_stable_protocol():
    from tax_agent.runtime.sse_protocol import render_sse

    assert render_sse("RUN_STARTED", {"threadId": "thread-1"}) == (
        'event: RUN_STARTED\n'
        'data: {"threadId":"thread-1"}\n\n'
    )


def test_service_default_port_is_3004():
    from tax_agent.delivery.http_api import DEFAULT_API_PORT

    assert DEFAULT_API_PORT == 3004


def test_service_app_reports_missing_fastapi_dependency(monkeypatch):
    from tax_agent.delivery.http_api import create_app

    monkeypatch.setitem(sys.modules, "fastapi", None)
    with pytest.raises(RuntimeError, match="fastapi and uvicorn"):
        create_app()


def test_agent_config_reads_environment_at_instantiation(monkeypatch):
    monkeypatch.setenv("DEEPAGENTS_MODEL", "openai:MiniMax-M2.7")
    monkeypatch.setenv("CHECKPOINT_BACKEND", "opengauss")
    monkeypatch.setenv("OPENGAUSS_DSN", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("LANGFUSE_ENABLED", "1")
    monkeypatch.setenv("TAX_AGENT_SERVICE_PORT", "3004")

    config = AgentConfig()

    assert config.model == "openai:MiniMax-M2.7"
    assert config.checkpoint_backend == "opengauss"
    assert config.opengauss_dsn == "postgresql://u:p@localhost:5432/db"
    assert config.langfuse_enabled is True
    assert config.service_port == 3004


def test_langfuse_observability_disabled_by_default():
    from tax_agent.runtime.observability import build_langfuse_observability

    observability = build_langfuse_observability(enabled=False)

    assert observability.provider == "none"
    assert observability.callbacks == []


def test_langfuse_observability_fails_clearly_when_dependency_missing(monkeypatch):
    from tax_agent.runtime.observability import build_langfuse_observability

    monkeypatch.setitem(sys.modules, "langfuse", None)
    with pytest.raises(RuntimeError, match="langfuse package"):
        build_langfuse_observability(enabled=True)


def test_langfuse_check_script_masks_secret_values(monkeypatch):
    import check_langfuse_observability as langfuse_check

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-1234567890")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-abcdefghij")
    monkeypatch.setenv("LANGFUSE_BASE_URL", "http://localhost:3000")

    results = langfuse_check._check_required_env()

    assert all(result.ok for result in results)
    assert "abcdefghij" not in results[1].detail
    assert results[2].detail == "http://localhost:3000"


def test_runtime_entrypoints_load_dotenv_with_utf8_sig():
    root = Path(__file__).resolve().parents[1]

    main_source = (root / "main.py").read_text(encoding="utf-8")
    app_source = (root / "app.py").read_text(encoding="utf-8")
    langfuse_check_source = (root / "check_langfuse_observability.py").read_text(encoding="utf-8")

    assert 'encoding="utf-8-sig"' in main_source
    assert 'encoding="utf-8-sig"' in app_source
    assert 'encoding="utf-8-sig"' in langfuse_check_source


def test_batch_processor_uses_explicit_batch_route(tmp_path):
    from tax_agent.delivery.batch import BatchProcessor, BatchRequest

    input_file = tmp_path / "questions.txt"
    input_file.write_text("什么是增值税？\n那进项税额呢？", encoding="utf-8")

    class FakeExecutor:
        def __init__(self):
            self.requests = []

        async def execute_turn(self, request):
            self.requests.append(request)
            return SimpleNamespace(
                answer=f"answer {len(self.requests)}",
                citations=[],
                tool_events=[],
                domain_analysis={},
                skills=[],
            )

    fake_executor = FakeExecutor()
    processor = BatchProcessor(fake_executor)
    response = asyncio.run(
        processor.run(
            BatchRequest(
                session_id="sess-batch",
                trace_id="trace-batch",
                input_file=str(input_file),
                thread_strategy="per_question",
            ),
            output_dir=tmp_path / "output",
        )
    )

    assert len(fake_executor.requests) == 2
    assert fake_executor.requests[0].thread_id == "sess-batch-q1"
    assert fake_executor.requests[1].thread_id == "sess-batch-q2"
    assert Path(response.output_paths["markdown"]).exists()
    assert Path(response.output_paths["json"]).exists()


def test_cli_main_uses_batch_processor_instead_of_execute_with_evidence():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")

    assert "BatchProcessor" in source
    assert "execute_with_evidence" not in source
