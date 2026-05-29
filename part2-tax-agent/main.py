"""Deep Agents POC — Part 2: 税务智能问答 Agent

用法：
    python main.py --input 税审问题.docx --output ./output
"""

import asyncio
import argparse
import hashlib
import os
import time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from deepagents import register_provider_profile, ProviderProfile

register_provider_profile("openai",
    ProviderProfile(init_kwargs={"use_responses_api": False}),
)

from config import AgentConfig
from question_extractor import extract_questions
from intent_classifier import IntentClassifier
from agent_executor import AgentExecutor
from audit_trace import AuditTraceRecorder
from output_formatter import OutputFormatter


def _file_hash(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists():
        return ""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


async def main():
    parser = argparse.ArgumentParser(description="税务智能问答 Agent")
    parser.add_argument("--input", "-i", default="sample_input.txt", help="输入文件路径（支持 .txt / .docx）")
    parser.add_argument("--output", "-o", default="./output", help="输出目录")
    parser.add_argument("--model", "-m", default=os.getenv("DEEPAGENTS_MODEL", "openai:gpt-4o"), help="LLM 模型")
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

    print("[3/5] DeepAgents 原生规划将在 Agent 执行中完成...")

    print("[4/5] 执行 Agent 回答...")
    executor = AgentExecutor(config)
    formatter = OutputFormatter()
    trace = AuditTraceRecorder.start(
        output_dir=config.output_dir,
        input_file=config.input_file,
        input_file_hash=_file_hash(config.input_file),
        model=config.model,
        checkpoint_backend=executor._checkpoint_config.backend_type,
        checkpoint_thread_id=executor._checkpoint_config.thread_id,
        checkpoint_path=executor._checkpoint_config.path,
        run_id=executor._checkpoint_config.thread_id,
    )

    results = []
    for index, q in enumerate(classified, start=1):
        question_id = f"q{index}"
        print(f"  → 回答: {q.text[:50]}...")
        trace.record_question_started(question_id, q.text, q.intent)
        started = time.perf_counter()
        try:
            execution = await executor.execute_with_evidence(q)
        except Exception as exc:
            trace.record_error(question_id, exc)
            raise
        latency_ms = int((time.perf_counter() - started) * 1000)
        for skill in execution.skills:
            trace.record_skill_selected(question_id, skill)
        for event in execution.tool_events:
            trace.record_tool_call(
                question_id,
                tool_name=event.get("name", "unknown"),
                source_ids=[citation.get("source_id") for citation in execution.citations if isinstance(citation, dict)],
            )
        trace.record_answer(question_id, execution.citations, latency_ms=latency_ms)
        print(f"    工具事件: {len(execution.tool_events)}，引用: {len(execution.citations)}")
        results.append(
            formatter.format(
                q,
                execution.answer,
                citations=execution.citations,
                tool_events=execution.tool_events,
                domain_analysis=execution.domain_analysis,
                skills=execution.skills,
            )
        )

    print("[5/5] 生成输出报告...")
    paths = formatter.write_all(results, config.output_dir, run_id=trace.run_id)
    trace_paths = trace.finish(paths)
    print(f"  → Markdown: {paths['markdown']}")
    print(f"  → JSON: {paths['json']}")
    print(f"  → Trace: {trace_paths['trace']}")
    print(f"  → Trace summary: {trace_paths['summary']}")
    print("完成!")


if __name__ == "__main__":
    asyncio.run(main())
