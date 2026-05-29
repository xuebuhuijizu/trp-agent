from pydantic import BaseModel


class ClassifiedQuestion(BaseModel):
    text: str
    intent: str  # "definition" | "rate" | "compliance"


INTENT_LABELS = {
    "definition": "定义查询 — 询问某个税务概念、术语的含义",
    "rate": "税率计算 — 询问税率、税额计算",
    "compliance": "合规判断 — 询问是否符合规定、是否需要申报",
}

INTENT_CLASSIFICATION_PROMPT = """你是一个税务问题意图分类器。
请判断以下问题的意图类别，只返回类别名称。

类别：
- definition：定义查询（概念解释、术语含义）
- rate：税率计算（税率、税额、计算方式）
- compliance：合规判断（是否符合规定、是否需要申报、合规性分析）

问题：{question}

类别："""


class IntentClassifier:
    def __init__(self, llm_callable=None):
        self._llm = llm_callable

    def set_llm(self, llm_callable):
        self._llm = llm_callable

    def classify(self, question: str) -> ClassifiedQuestion:
        if self._llm:
            try:
                intent = str(self._llm(INTENT_CLASSIFICATION_PROMPT.format(question=question))).strip().lower()
            except Exception:
                intent = ""
            else:
                if intent in INTENT_LABELS:
                    return ClassifiedQuestion(text=question, intent=intent)

        return ClassifiedQuestion(text=question, intent=self._rule_based(question))

    def classify_batch(self, questions: list[str]) -> list[ClassifiedQuestion]:
        return [self.classify(q) for q in questions]

    @staticmethod
    def _rule_based(question: str) -> str:
        q = question.lower()
        if any(w in q for w in ["什么是", "定义", "含义", "概念", "解释", "什么叫", "何为", "区别"]):
            return "definition"
        if any(w in q for w in ["税率", "计算", "税额", "多少税", "交多少", "怎么算", "比例", "怎么收", "收多少"]):
            return "rate"
        if any(w in q for w in ["是否", "合规", "需要申报", "能不能", "可以吗", "违反", "符合", "需要缴纳哪些税", "需要交哪些税"]):
            return "compliance"
        if q.endswith("哪些税") or q.endswith("哪些税收"):
            return "rate"
        return "definition"
