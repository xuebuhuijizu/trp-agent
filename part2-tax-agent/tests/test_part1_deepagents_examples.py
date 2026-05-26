import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "part1-capability-validation" / "examples"


def _source(name: str) -> str:
    return (EXAMPLES / name).read_text(encoding="utf-8")


def _tree(name: str) -> ast.AST:
    return ast.parse(_source(name))


def _create_deep_agent_keywords(name: str) -> set[str]:
    keywords = set()
    for node in ast.walk(_tree(name)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "create_deep_agent":
            keywords.update(kw.arg for kw in node.keywords if kw.arg)
    return keywords


def test_subagent_example_defines_custom_subagent():
    source = _source("02_sub_agent.py")
    keywords = _create_deep_agent_keywords("02_sub_agent.py")

    assert "subagents" in keywords
    assert '"tax-policy-researcher"' in source
    assert '"tax-calculation-reviewer"' in source


def test_memory_example_uses_long_term_memory_api():
    source = _source("04_memory.py")
    keywords = _create_deep_agent_keywords("04_memory.py")

    assert "memory" in keywords
    assert "backend" in keywords
    assert "store" in keywords
    assert "checkpointer=True" not in source
    assert '"/memories/AGENTS.md"' in source
    assert "StateBackend(runtime)" not in source
    assert "StoreBackend(\n                runtime," not in source
    assert "backend=build_memory_backend" not in source
    assert "memory_backend = CompositeBackend" in source
    assert "backend=memory_backend" in source


def test_hitl_example_uses_interrupt_resume_pattern():
    source = _source("06_human_in_loop.py")
    keywords = _create_deep_agent_keywords("06_human_in_loop.py")

    assert "interrupt_on" in keywords
    assert "checkpointer" in keywords
    assert "Command(resume=" in source
    assert 'version="v2"' in source
    assert '"thread_id"' in source
    assert 'result.value["messages"]' in source


def test_streaming_examples_exist_and_use_current_apis():
    streaming = _source("07_streaming.py")
    event_streaming = _source("08_event_streaming.py")

    assert ".stream(" in streaming
    assert 'stream_mode="messages"' in streaming
    assert 'version="v2"' in streaming
    assert ".stream_events(" in event_streaming
    assert 'version="v3"' in event_streaming
    assert ".subagents" in event_streaming
    assert ".tool_calls" in event_streaming


def test_permissions_example_uses_filesystem_permission_rules():
    source = _source("09_permissions.py")
    keywords = _create_deep_agent_keywords("09_permissions.py")

    assert "permissions" in keywords
    assert "FilesystemPermission" in source
    assert 'mode="deny"' in source
    assert 'paths=["/**"]' in source


def test_docs_no_longer_claim_old_hitl_parameter():
    docs = (ROOT / "docs" / "guides" / "demo-walkthrough.md").read_text(encoding="utf-8")

    assert "confirmation_before" not in docs
    assert "interrupt_on" in docs
    assert "Command(resume=" in docs


def test_ollama_default_declares_required_provider_dependency():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    requirements = (ROOT / "part2-tax-agent" / "requirements.txt").read_text(encoding="utf-8")

    assert "langchain-ollama" in pyproject
    assert "langchain-ollama" in requirements
