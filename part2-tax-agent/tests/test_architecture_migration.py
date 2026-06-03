from pathlib import Path


def test_target_architecture_modules_are_importable():
    from tax_agent.agent.graph import build_tax_agent
    from tax_agent.agent.instructions import TAX_SYSTEM_PROMPT
    from tax_agent.agent.tool_manifest import TAX_AGENT_TOOLS
    from tax_agent.business.answers.models import TaxAnswer, TaxCitation
    from tax_agent.business.analysis.intent_classifier import IntentClassifier
    from tax_agent.business.analysis.tax_context import analyze_tax_question
    from tax_agent.business.references.tools import find_tax_authorities
    from tax_agent.delivery.batch import BatchProcessor, BatchRequest
    from tax_agent.delivery.http_api import create_app
    from tax_agent.runtime.config import AgentConfig
    from tax_agent.runtime.executor import AgentExecutor, ExecutionResult

    assert build_tax_agent
    assert "税务顾问专家" in TAX_SYSTEM_PROMPT
    assert find_tax_authorities in TAX_AGENT_TOOLS
    assert TaxAnswer.model_fields["citations"].annotation == list[TaxCitation]
    assert IntentClassifier
    assert analyze_tax_question
    assert BatchProcessor
    assert BatchRequest
    assert create_app
    assert AgentConfig
    assert AgentExecutor
    assert ExecutionResult


def test_conversation_request_no_longer_exposes_interaction_mode():
    from tax_agent.runtime.conversation import ConversationRequest

    assert "interaction_mode" not in ConversationRequest.model_fields


def test_architecture_docs_do_not_show_removed_runtime_concepts():
    root = Path(__file__).resolve().parents[2]
    architecture = (root / "docs" / "architecture" / "4a-architecture.md").read_text(encoding="utf-8")

    assert "InteractionMode 策略" not in architecture
    assert "answer_stream" not in architecture
    assert "progress_stream" not in architecture
    assert "structured_final" not in architecture
    assert "Audit Trace" not in architecture
    assert "JSONL" not in architecture
