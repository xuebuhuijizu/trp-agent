import asyncio
import importlib
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tax_agent.config import AgentConfig
from tax_agent.business.analysis.intent_classifier import ClassifiedQuestion, IntentClassifier
from tax_agent.delivery.batch_io.output_formatter import OutputFormatter
from tax_agent.delivery.batch_io.question_extractor import _split_questions, extract_questions
from tax_agent.legacy.planner import DefaultPlanner, Planner
from tax_agent.legacy.rag_decorator import NoopRAG, RAGDecorator


class TestQuestionExtractor:
    def test_split_questions_with_question_marks(self):
        text = "什么是增值税？\n企业所得税税率是多少？\n这种情况需要申报吗？"
        result = _split_questions(text)
        assert len(result) == 3
        assert all(q.endswith("？") for q in result)

    def test_split_questions_prefers_full_width_question_marks_over_fallback(self):
        text = "背景说明这一行不是问题\n什么是增值税？\n备注说明这一行也不是问题"
        result = _split_questions(text)
        assert result == ["什么是增值税？"]

    def test_split_questions_caps_large_fallback_text(self):
        result = _split_questions("a" * 5000)
        assert len(result) == 1
        assert len(result[0]) <= 2003

    def test_split_questions_fallback(self):
        text = "解释增值税\n计算企业所得税\n合规分析"
        result = _split_questions(text)
        assert len(result) >= 1

    def test_extract_txt(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write("什么是增值税？\n税率是多少？")
            path = f.name
        try:
            result = extract_questions(path)
            assert len(result) == 2
        finally:
            Path(path).unlink()

    def test_extract_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            extract_questions("nonexistent.docx")

    def test_extract_unsupported_format(self, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_text("dummy", encoding="utf-8")
        with pytest.raises(ValueError, match="Unsupported file format"):
            extract_questions(str(pdf_file))


class TestIntentClassifier:
    def test_rule_based_definition(self):
        result = IntentClassifier._rule_based("什么是增值税")
        assert result == "definition"

    def test_rule_based_rate(self):
        result = IntentClassifier._rule_based("企业所得税税率是多少")
        assert result == "rate"

    def test_rule_based_compliance(self):
        result = IntentClassifier._rule_based("这种情况需要申报吗")
        assert result == "compliance"

    def test_classify_batch(self):
        classifier = IntentClassifier()
        questions = ["什么是增值税", "税率是多少", "需要申报吗"]
        results = classifier.classify_batch(questions)
        assert len(results) == 3
        assert results[0].intent == "definition"
        assert results[1].intent == "rate"
        assert results[2].intent == "compliance"

    def test_classify_output_type(self):
        classifier = IntentClassifier()
        result = classifier.classify("什么是增值税")
        assert isinstance(result, ClassifiedQuestion)
        assert result.text == "什么是增值税"
        assert result.intent == "definition"

    def test_classify_falls_back_to_rules_when_llm_raises(self):
        def failing_llm(_prompt):
            raise TimeoutError("llm timeout")

        classifier = IntentClassifier(failing_llm)
        result = classifier.classify("企业所得税税率是多少")
        assert result.intent == "rate"


class TestPlanner:
    def test_default_planner_definition(self):
        planner = Planner()
        q = ClassifiedQuestion(text="什么是增值税", intent="definition")
        plan = planner.plan_for_question(q)
        assert len(plan) > 0
        assert all(isinstance(s, str) for s in plan)

    def test_default_planner_rate(self):
        planner = Planner()
        q = ClassifiedQuestion(text="企业所得税税率", intent="rate")
        plan = planner.plan_for_question(q)
        assert len(plan) > 0

    def test_default_planner_compliance(self):
        planner = Planner()
        q = ClassifiedQuestion(text="需要申报吗", intent="compliance")
        plan = planner.plan_for_question(q)
        assert len(plan) > 0

    def test_plan_batch(self):
        planner = Planner()
        questions = [
            ClassifiedQuestion(text="什么是增值税", intent="definition"),
            ClassifiedQuestion(text="税率多少", intent="rate"),
        ]
        plans = planner.plan_batch(questions)
        assert len(plans) == 2
        assert "什么是增值税" in plans
        assert "税率多少" in plans


class TestOutputFormatter:
    def test_format_includes_both_outputs(self):
        formatter = OutputFormatter()
        q = ClassifiedQuestion(text="什么是增值税", intent="definition")
        result = formatter.format(q, "增值税是一种流转税")
        assert "answer_markdown" in result
        assert "answer_json" in result
        assert result["question"] == "什么是增值税"

    def test_markdown_section_structure(self):
        formatter = OutputFormatter()
        q = ClassifiedQuestion(text="什么是增值税", intent="definition")
        md = formatter._to_markdown(q, "增值税是一种流转税")
        assert "###" in md
        assert "**问题**" in md
        assert "**回答**" in md

    def test_json_structure(self):
        formatter = OutputFormatter()
        q = ClassifiedQuestion(text="什么是增值税", intent="definition")
        js = formatter._to_json(q, "增值税是一种流转税\n[来源: 税法第1条]")
        assert js["question"] == "什么是增值税"
        assert js["intent"] == "definition"
        assert "citations" in js

    def test_format_strips_reasoning_tags_and_uses_structured_citations(self):
        formatter = OutputFormatter()
        q = ClassifiedQuestion(text="什么是增值税", intent="definition")
        citations = [{"source_id": "vat-regulation", "title": "增值税暂行条例"}]

        result = formatter.format(q, "<think>内部推理</think>\n增值税是一种流转税", citations=citations)

        answer = result["answer_json"]["answer"]
        assert "<think>" not in answer
        assert "内部推理" not in answer
        assert result["answer_json"]["citations"] == citations

    def test_extract_citations(self):
        text = "根据税法规定\n[来源: 增值税暂行条例]\n参考相关法规"
        citations = OutputFormatter._extract_citations(text)
        assert citations == ["[来源: 增值税暂行条例]"]

    def test_extract_citations_ignores_unstructured_keywords(self):
        text = "请参考以下分析\n依据具体事实判断\n[依据: 企业所得税法]"
        citations = OutputFormatter._extract_citations(text)
        assert citations == ["[依据: 企业所得税法]"]

    def test_write_all_creates_files(self, tmp_path):
        formatter = OutputFormatter()
        q = ClassifiedQuestion(text="什么是增值税", intent="definition")
        result = formatter.format(q, "增值税是一种流转税")
        paths = formatter.write_all([result], tmp_path)
        assert Path(paths["markdown"]).exists()
        assert Path(paths["json"]).exists()


class TestRAGDecorator:
    def test_noop_rag_returns_empty(self):
        rag = NoopRAG()
        result = asyncio.run(rag.retrieve("test"))
        assert result == []

    def test_decorator_enrich_without_rag(self):
        decorator = RAGDecorator()
        result = asyncio.run(decorator.enrich("test", "context"))
        assert result == "context"

    def test_decorator_custom_adapter(self):
        class FakeRAG:
            async def retrieve(self, query, top_k=5):
                return ["doc1", "doc2"]

        decorator = RAGDecorator(FakeRAG())
        result = asyncio.run(decorator.enrich("test", "ctx"))
        assert "doc1" in result


class TestAgentExecutor:
    def test_build_agent_uses_config(self, monkeypatch):
        deepagents_calls = []
        model_kwargs = {}

        def fake_init_chat_model(model, **kwargs):
            model_kwargs.update({"model": model, **kwargs})
            return SimpleNamespace(model=model, temperature=kwargs.get("temperature"))

        def fake_create_deep_agent(**kwargs):
            deepagents_calls.append(kwargs)
            return SimpleNamespace()

        class FilesystemBackend:
            def __init__(self, root_dir, virtual_mode=None):
                self.root_dir = root_dir
                self.virtual_mode = virtual_mode

        monkeypatch.setattr("langchain.chat_models.init_chat_model", fake_init_chat_model)
        monkeypatch.setitem(
            sys.modules,
            "deepagents",
            SimpleNamespace(create_deep_agent=fake_create_deep_agent),
        )
        monkeypatch.setitem(
            sys.modules,
            "deepagents.backends",
            SimpleNamespace(FilesystemBackend=FilesystemBackend),
        )
        agent_executor = importlib.import_module("tax_agent.runtime.agent_executor")

        config = AgentConfig(model="ollama:test", temperature=0.2, max_tokens=1234)
        executor = agent_executor.AgentExecutor(config)

        assert executor._agent is not None
        assert model_kwargs["model"] == "ollama:test"
        assert model_kwargs["temperature"] == 0.2
        assert model_kwargs["max_tokens"] == 1234
        assert deepagents_calls[0]["model"].model == "ollama:test"
        assert "税务顾问专家" in deepagents_calls[0]["system_prompt"]
        assert "tools" in deepagents_calls[0]
        assert {tool.__name__ for tool in deepagents_calls[0]["tools"]} == {
            "find_tax_authorities",
            "analyze_tax_question",
        }
        assert deepagents_calls[0]["skills"] == ["/skills"]
        assert deepagents_calls[0]["memory"] == ["/memories/AGENTS.md"]
        assert deepagents_calls[0]["backend"].__class__.__name__ == "FilesystemBackend"
        assert deepagents_calls[0]["backend"].virtual_mode is True
        assert deepagents_calls[0]["response_format"].__name__ == "TaxAnswer"
        assert "checkpointer" in deepagents_calls[0]

    def test_execute_builds_prompt_and_returns_last_message(self):
        class FakeAgent:
            def __init__(self):
                self.payload = None

            async def ainvoke(self, payload):
                self.payload = payload
                return {"messages": [{"content": "first"}, {"content": "final answer"}]}

        fake_agent = FakeAgent()
        agent_executor = importlib.import_module("tax_agent.runtime.agent_executor")
        executor = agent_executor.AgentExecutor(AgentConfig(), agent=fake_agent)
        question = ClassifiedQuestion(text="什么是增值税", intent="definition")

        answer = asyncio.run(executor.execute(question, ["确认概念", "给出依据"]))

        assert answer == "final answer"
        prompt = fake_agent.payload["messages"][0]["content"]
        assert "什么是增值税" in prompt
        assert "definition" in prompt
        assert "1. 确认概念" in prompt
        assert "2. 给出依据" in prompt

    def test_execute_with_evidence_uses_native_prompt_and_extracts_tool_citations(self):
        class FakeAgent:
            def __init__(self):
                self.payload = None

            async def ainvoke(self, payload):
                self.payload = payload
                return {
                    "messages": [
                        {
                            "name": "find_tax_authorities",
                            "content": '{"citations": [{"citation_id": "local_tax_authorities:vat-regulation", "source_id": "vat-regulation", "source_type": "law", "provider_id": "local_tax_authorities", "title": "增值税暂行条例", "locator": null, "snippet": "VAT", "confidence": 0.9, "retrieved_at": null, "metadata": {}}]}',
                        },
                        {"content": "final answer"},
                    ]
                }

        fake_agent = FakeAgent()
        agent_executor = importlib.import_module("tax_agent.runtime.agent_executor")
        executor = agent_executor.AgentExecutor(AgentConfig(), agent=fake_agent)
        question = ClassifiedQuestion(text="什么是增值税", intent="definition")

        result = asyncio.run(executor.execute_with_evidence(question))

        assert result.answer == "final answer"
        assert result.citations == [
            {
                "citation_id": "local_tax_authorities:vat-regulation",
                "source_id": "vat-regulation",
                "source_type": "law",
                "provider_id": "local_tax_authorities",
                "title": "增值税暂行条例",
                "locator": None,
                "snippet": "VAT",
                "confidence": 0.9,
                "retrieved_at": None,
                "metadata": {},
            }
        ]
        assert result.tool_events[0]["name"] == "find_tax_authorities"
        prompt = fake_agent.payload["messages"][0]["content"]
        assert "write_todos" in prompt
        assert "find_tax_authorities" in prompt
        assert "执行计划：" not in prompt

    def test_execute_with_evidence_prefers_structured_response(self):
        class FakeAgent:
            async def ainvoke(self, payload):
                return {
                    "messages": [{"content": "fallback answer"}],
                    "structured_response": {
                        "question": "什么是增值税",
                        "intent": "definition",
                        "answer": "structured answer",
                        "citations": [{"source_id": "vat-regulation", "title": "增值税暂行条例"}],
                    },
                }

        agent_executor = importlib.import_module("tax_agent.runtime.agent_executor")
        executor = agent_executor.AgentExecutor(AgentConfig(), agent=FakeAgent())
        question = ClassifiedQuestion(text="什么是增值税", intent="definition")

        result = asyncio.run(executor.execute_with_evidence(question))

        assert result.answer == "structured answer"
        assert result.citations == [{"source_id": "vat-regulation", "title": "增值税暂行条例"}]


def test_deepagents_skill_and_memory_files_exist():
    root = Path(__file__).resolve().parents[1]
    skill = root / "skills" / "solution-generation" / "SKILL.md"
    memory = root / "memories" / "AGENTS.md"

    assert skill.exists()
    assert memory.exists()
    assert "解决方案生成" in skill.read_text(encoding="utf-8")
    assert "中国税务场景" in memory.read_text(encoding="utf-8")
