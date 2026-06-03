import json
from pathlib import Path
from typing import Any


PART2_ROOT = Path(__file__).resolve().parents[3]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_tax_terms(root: str | Path = PART2_ROOT) -> list[dict]:
    return _load_json(Path(root) / "skills" / "tax-finance-logic-decomposition" / "refs" / "terms.json")


def load_audit_scenarios(root: str | Path = PART2_ROOT) -> list[dict]:
    return _load_json(Path(root) / "skills" / "audit-scenario-recognition" / "refs" / "scenarios.json")


def load_historical_questions(root: str | Path = PART2_ROOT) -> list[dict]:
    return _load_json(Path(root) / "skills" / "historical-question-matching" / "refs" / "history_cases.json")


def load_intent_taxonomy(root: str | Path = PART2_ROOT) -> list[dict]:
    return _load_json(Path(root) / "skills" / "audit-intent-inference" / "refs" / "intent-taxonomy.json")


def match_tax_terms(question: str, terms: list[dict] | None = None) -> list[dict]:
    terms = terms or load_tax_terms()
    matches = []
    for item in terms:
        names = [item["term"], *item.get("aliases", [])]
        hit = next((name for name in names if name and name in question), None)
        if not hit:
            continue
        matches.append(
            {
                "term": item["term"],
                "matched_text": hit,
                "category": item.get("category"),
                "logic_hint": item.get("logic_hint"),
            }
        )
    return matches


def match_audit_scenarios(question: str, scenarios: list[dict] | None = None) -> list[dict]:
    scenarios = scenarios or load_audit_scenarios()
    scored = []
    for scenario in scenarios:
        keywords = scenario.get("keywords", [])
        hits = [keyword for keyword in keywords if keyword in question]
        if not hits:
            continue
        scored.append(
            {
                "scenario_id": scenario["scenario_id"],
                "title": scenario["title"],
                "matched_keywords": hits,
                "confidence": min(0.95, 0.45 + len(hits) * 0.2),
                "reason": scenario.get("audit_focus"),
            }
        )
    return sorted(scored, key=lambda item: item["confidence"], reverse=True)


def match_historical_questions(question: str, history: list[dict] | None = None) -> list[dict]:
    history = history or load_historical_questions()
    scored = []
    for case in history:
        keywords = case.get("keywords", [])
        hits = [keyword for keyword in keywords if keyword in question]
        if not hits:
            continue
        scored.append(
            {
                "case_id": case["case_id"],
                "title": case["title"],
                "scenario_id": case["scenario_id"],
                "matched_keywords": hits,
                "reuse_boundary": case.get("reuse_boundary"),
                "reference": case.get("reference"),
                "confidence": min(0.9, 0.4 + len(hits) * 0.2),
            }
        )
    return sorted(scored, key=lambda item: item["confidence"], reverse=True)


def infer_audit_intents(question: str, taxonomy: list[dict] | None = None) -> list[dict]:
    taxonomy = taxonomy or load_intent_taxonomy()
    hypotheses = []
    for intent in taxonomy:
        triggers = [trigger for trigger in intent.get("triggers", []) if trigger in question]
        if not triggers:
            continue
        hypotheses.append(
            {
                "intent_id": intent["intent_id"],
                "title": intent["title"],
                "triggers": triggers,
                "hypothesis": intent["hypothesis"],
                "confidence": min(0.9, 0.5 + len(triggers) * 0.15),
                "alternative": intent.get("alternative"),
            }
        )
    return sorted(hypotheses, key=lambda item: item["confidence"], reverse=True)


def generate_solution_outline(
    question: str,
    terms: list[dict],
    scenarios: list[dict],
    historical_references: list[dict],
    intent_hypotheses: list[dict],
) -> dict:
    return {
        "facts": [question],
        "applicable_scenarios": [item["scenario_id"] for item in scenarios[:3]],
        "historical_reference_ids": [item["case_id"] for item in historical_references[:3]],
        "tax_logic": [item["logic_hint"] for item in terms if item.get("logic_hint")],
        "recommendations": [
            "核对业务合同、发票、付款和入账资料是否一致。",
            "结合命中的税审场景逐项确认适用条件和不得适用情形。",
            "将历史问题作为检查框架参考，不直接复用结论。",
        ],
        "risk_notes": [item["hypothesis"] for item in intent_hypotheses[:3]],
        "materials_needed": [
            "合同或业务协议",
            "发票及认证抵扣记录",
            "会计凭证和入账明细",
            "交易背景和业务实质说明",
        ],
    }


def analyze_tax_question(question: str) -> dict:
    """Analyze a tax audit question against local demo seed knowledge."""
    terms = match_tax_terms(question)
    scenarios = match_audit_scenarios(question)
    historical_references = match_historical_questions(question)
    intent_hypotheses = infer_audit_intents(question)
    return {
        "terms": terms,
        "scenario_matches": scenarios,
        "historical_references": historical_references,
        "intent_hypotheses": intent_hypotheses,
        "solution": generate_solution_outline(question, terms, scenarios, historical_references, intent_hypotheses),
    }


def analyze_tax_context(messages: list[dict] | list[Any]) -> dict:
    """Analyze recent conversation turns against local demo seed knowledge."""
    chunks = []
    for message in messages[-8:]:
        if isinstance(message, dict):
            role = message.get("role")
            content = message.get("content", "")
        else:
            role = getattr(message, "role", None)
            content = getattr(message, "content", "")
        if role in {"user", "assistant"} and content:
            chunks.append(str(content))
    return analyze_tax_question("\n".join(chunks))
