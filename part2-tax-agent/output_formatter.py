import json
import re
from pathlib import Path
from datetime import datetime

from intent_classifier import ClassifiedQuestion


CITATION_PATTERN = re.compile(r"^[\[【](来源|依据|参考)\s*[:：].+[\]】]$")


class OutputFormatter:
    def format(
        self,
        question: ClassifiedQuestion,
        answer: str,
        citations: list[dict] | None = None,
        tool_events: list[dict] | None = None,
        domain_analysis: dict | None = None,
        skills: list[str] | None = None,
    ) -> dict:
        clean_answer = self._strip_reasoning_tags(answer)
        return {
            "question": question.text,
            "intent": question.intent,
            "answer_markdown": self._to_markdown(question, clean_answer),
            "answer_json": self._to_json(
                question,
                clean_answer,
                citations=citations,
                tool_events=tool_events,
                domain_analysis=domain_analysis,
                skills=skills,
            ),
        }

    def write_all(self, results: list[dict], output_dir: str | Path, run_id: str | None = None):
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        md_path = out_dir / f"tax_report_{timestamp}.md"
        json_path = out_dir / f"tax_report_{timestamp}.json"

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._render_markdown_report(results))

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self._render_json_report(results, run_id=run_id), f, ensure_ascii=False, indent=2)

        return {"markdown": str(md_path), "json": str(json_path)}

    def _to_markdown(self, question: ClassifiedQuestion, answer: str) -> str:
        intent_labels = {
            "definition": "📖 定义查询",
            "rate": "💰 税率计算",
            "compliance": "⚖️ 合规判断",
        }
        label = intent_labels.get(question.intent, "📋 其他")
        return f"""### {label}

**问题**：{question.text}

**回答**：
{answer}

---

"""

    def _to_json(
        self,
        question: ClassifiedQuestion,
        answer: str,
        citations: list[dict] | None = None,
        tool_events: list[dict] | None = None,
        domain_analysis: dict | None = None,
        skills: list[str] | None = None,
    ) -> dict:
        return {
            "question": question.text,
            "intent": question.intent,
            "answer": answer,
            "citations": citations if citations is not None else self._extract_citations(answer),
            "tool_events": tool_events or [],
            "skills": skills or [],
            "domain_analysis": domain_analysis or {},
        }

    @staticmethod
    def _render_markdown_report(results: list[dict]) -> str:
        lines = [
            f"# 税务智能问答报告",
            f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"问题总数：{len(results)}",
            "",
            "---",
            "",
        ]
        for r in results:
            lines.append(r["answer_markdown"])
        return "\n".join(lines)

    @staticmethod
    def _render_json_report(results: list[dict], run_id: str | None = None) -> dict:
        return {
            "report_meta": {
                "generated_at": datetime.now().isoformat(),
                "total_questions": len(results),
                "run_id": run_id,
            },
            "answers": [r["answer_json"] for r in results],
        }

    @staticmethod
    def _extract_citations(text: str) -> list[str]:
        citations = []
        for line in text.split("\n"):
            line = line.strip()
            if CITATION_PATTERN.match(line):
                citations.append(line)
        return citations

    @staticmethod
    def _strip_reasoning_tags(text: str) -> str:
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
