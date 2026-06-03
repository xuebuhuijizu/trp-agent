import json
from pathlib import Path

from tax_agent.business.analysis.tax_context import (
    analyze_tax_question,
    load_audit_scenarios,
    load_historical_questions,
    load_tax_terms,
    match_audit_scenarios,
    match_historical_questions,
    match_tax_terms,
)
from tax_agent.runtime.audit_trace import AuditTraceRecorder
from tax_agent.runtime.checkpointing import build_checkpoint_config


ROOT = Path(__file__).resolve().parents[1]


def test_audit_trace_writes_jsonl_and_summary(tmp_path):
    recorder = AuditTraceRecorder.start(
        output_dir=tmp_path,
        input_file="sample_input.txt",
        input_file_hash="abc123",
        model="openai:gpt-4o",
        checkpoint_backend="memory",
        checkpoint_thread_id="thread-1",
    )

    recorder.record_question_started("q1", "什么是增值税？", "definition")
    recorder.record_skill_selected("q1", "tax-finance-logic-decomposition")
    recorder.record_tool_call(
        "q1",
        tool_name="retrieve_tax_context",
        args_summary={"query": "增值税"},
        source_ids=["vat-regulation"],
        latency_ms=12,
    )
    recorder.record_answer(
        "q1",
        citations=[{"source_id": "vat-regulation", "title": "增值税暂行条例"}],
        latency_ms=34,
    )
    paths = recorder.finish({"markdown": "report.md", "json": "report.json"})

    trace_events = [
        json.loads(line)
        for line in Path(paths["trace"]).read_text(encoding="utf-8").splitlines()
    ]
    summary = json.loads(Path(paths["summary"]).read_text(encoding="utf-8"))

    assert trace_events[0]["event_type"] == "run_started"
    assert trace_events[-1]["event_type"] == "run_finished"
    assert summary["run_id"] == recorder.run_id
    assert summary["checkpoint"]["thread_id"] == "thread-1"
    assert summary["totals"]["questions"] == 1
    assert summary["totals"]["tool_calls"] == 1
    assert summary["output_paths"]["markdown"] == "report.md"


def test_checkpoint_config_provides_thread_id_and_backend(tmp_path):
    config = build_checkpoint_config(output_dir=tmp_path, run_id="run-123")

    assert config.thread_id == "run-123"
    assert config.backend_type in {"sqlite", "memory"}
    assert config.invoke_config["configurable"]["thread_id"] == "run-123"
    assert config.checkpointer is not None


def test_domain_seed_data_loads_and_matches_terms_scenarios_and_history():
    terms = load_tax_terms(ROOT)
    scenarios = load_audit_scenarios(ROOT)
    history = load_historical_questions(ROOT)
    question = "公司取得发票后能否抵扣增值税进项税额？"

    term_matches = match_tax_terms(question, terms)
    scenario_matches = match_audit_scenarios(question, scenarios)
    historical_matches = match_historical_questions(question, history)

    assert any(match["term"] == "增值税" for match in term_matches)
    assert any(match["term"] == "进项税额" for match in term_matches)
    assert scenario_matches[0]["scenario_id"] == "invoice-input-vat-deduction"
    assert historical_matches[0]["case_id"] == "case-input-vat-001"


def test_domain_analysis_includes_solution_outline():
    analysis = analyze_tax_question("公司取得发票后能否抵扣增值税进项税额？")

    assert analysis["solution"]["applicable_scenarios"][0] == "invoice-input-vat-deduction"
    assert analysis["solution"]["historical_reference_ids"][0] == "case-input-vat-001"
    assert analysis["solution"]["materials_needed"]
    assert "solution-generation" in {
        "solution-generation"
        for _ in analysis["solution"]["recommendations"]
    }


def test_five_domain_skills_replace_sample_tax_answering_skill():
    skill_dirs = {
        path.name
        for path in (ROOT / "skills").iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    }

    assert "tax-answering" not in skill_dirs
    assert skill_dirs == {
        "tax-finance-logic-decomposition",
        "audit-scenario-recognition",
        "historical-question-matching",
        "solution-generation",
        "audit-intent-inference",
    }

    for skill_name in skill_dirs:
        skill_text = (ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
        assert "description:" in skill_text
        assert "demo seed" in skill_text or "demo_seed" in skill_text
