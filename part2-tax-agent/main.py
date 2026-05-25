"""Deep Agents POC — Part 2: 税务智能问答 Agent

用法：
    python main.py --input 税审问题.docx --output ./output
"""

import asyncio
import argparse

from config import AgentConfig
from question_extractor import extract_questions
from intent_classifier import IntentClassifier
from planner import Planner
from agent_executor import AgentExecutor
from output_formatter import OutputFormatter
from rag_decorator import RAGDecorator


async def main():
    parser = argparse.ArgumentParser(description="税务智能问答 Agent")
    parser.add_argument("--input", "-i", default="input.docx", help="输入 Word 文件路径")
    parser.add_argument("--output", "-o", default="./output", help="输出目录")
    parser.add_argument("--model", "-m", default="ollama:llama3.1", help="LLM 模型")
    args = parser.parse_args()

    config = AgentConfig(
        model=args.model,
        input_file=args.input,
        output_dir=args.output,
    )

    print(f"[1/5] 提取问题: {config.input_file}")
    questions = extract_questions(config.input_file)
    print(f"  → 提取到 {len(questions)} 个问题")

    print("[2/5] 意图分类...")
    classifier = IntentClassifier()
    classified = classifier.classify_batch(questions)
    for c in classified:
        print(f"  [{c.intent}] {c.text[:60]}...")

    print("[3/5] 任务规划...")
    planner = Planner()
    plans = planner.plan_batch(classified)

    print("[4/5] 执行 Agent 回答...")
    executor = AgentExecutor(config)
    formatter = OutputFormatter()
    rag = RAGDecorator()

    results = []
    for q in classified:
        print(f"  → 回答: {q.text[:50]}...")
        plan_steps = plans[q.text]
        answer = await executor.execute(q, plan_steps)
        enriched = await rag.enrich(q.text, answer)
        results.append(formatter.format(q, enriched))

    print("[5/5] 生成输出报告...")
    paths = formatter.write_all(results, config.output_dir)
    print(f"  → Markdown: {paths['markdown']}")
    print(f"  → JSON: {paths['json']}")
    print("完成!")


if __name__ == "__main__":
    asyncio.run(main())
