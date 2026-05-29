"""Legacy static planner.

F004 uses DeepAgents native planning through the multi-turn runtime. This module
is kept for compatibility tests and historical examples, not for the main path.
"""

from typing import Protocol

from intent_classifier import ClassifiedQuestion


class PlannerAdapter(Protocol):
    def create_plan(self, question: ClassifiedQuestion) -> list[str]:
        ...


class DefaultPlanner:
    def create_plan(self, question: ClassifiedQuestion) -> list[str]:
        intent_plans = {
            "definition": [
                f"解释「{question.text}」的核心含义",
                "提供相关的税法依据或背景",
                "给出一个简单的例子帮助理解",
            ],
            "rate": [
                f"确认「{question.text}」涉及的税种",
                "查找适用税率和计算方式",
                "给出计算示例",
            ],
            "compliance": [
                f"分析「{question.text}」的事实情况",
                "查找相关法规条款",
                "给出合规判断结论",
            ],
        }
        return intent_plans.get(question.intent, intent_plans["definition"])


class Planner:
    def __init__(self, adapter: PlannerAdapter | None = None):
        self._adapter = adapter or DefaultPlanner()

    def set_adapter(self, adapter: PlannerAdapter):
        self._adapter = adapter

    def plan_for_question(self, question: ClassifiedQuestion) -> list[str]:
        return self._adapter.create_plan(question)

    def plan_batch(self, questions: list[ClassifiedQuestion]) -> dict[str, list[str]]:
        return {q.text: self.plan_for_question(q) for q in questions}
