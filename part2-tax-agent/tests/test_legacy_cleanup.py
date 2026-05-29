from pathlib import Path


def test_main_no_longer_uses_static_planner():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")

    assert "from planner import Planner" not in source
    assert "Planner()" not in source


def test_checkpointing_is_not_mixed_into_local_audit_trace():
    root = Path(__file__).resolve().parents[1]
    audit_trace = (root / "tax_agent" / "runtime" / "audit_trace.py").read_text(encoding="utf-8")
    agent_executor = (root / "tax_agent" / "runtime" / "agent_executor.py").read_text(encoding="utf-8")

    assert "class CheckpointConfig" not in audit_trace
    assert "def build_checkpoint_config" not in audit_trace
    assert "def build_async_checkpoint_config" not in audit_trace
    assert "from tax_agent.runtime.checkpointing import" in agent_executor


def test_current_runtime_guide_names_main_paths_and_file_roles():
    guide = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "guides"
        / "part2-tax-agent-current-runtime.md"
    ).read_text(encoding="utf-8")

    assert "CLI 批处理" in guide
    assert "HTTP 单轮 / 多轮对话" in guide
    assert "HTTP SSE 流式对话" in guide
    assert "`tax_agent/runtime/checkpointing.py`" in guide
    assert "`tax_agent/runtime/audit_trace.py`" in guide
    assert "`tax_agent/legacy/*`" in guide
