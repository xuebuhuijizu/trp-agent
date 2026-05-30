"""Deep Agents POC — Part 2: 税务智能问答 Agent

用法：
    python main.py --input 税审问题.docx --output ./output
"""

import asyncio
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", encoding="utf-8-sig")
from deepagents import register_provider_profile, ProviderProfile

register_provider_profile("openai",
    ProviderProfile(init_kwargs={"use_responses_api": False}),
)

from tax_agent.config import AgentConfig
from tax_agent.runtime.agent_executor import AgentExecutor
from tax_agent.service.batch_runtime import BatchProcessor, BatchRequest


async def main():
    parser = argparse.ArgumentParser(description="税务智能问答 Agent")
    parser.add_argument("--input", "-i", default=str(Path(__file__).resolve().parent / "sample_input.txt"), help="输入文件路径（支持 .txt / .docx）")
    parser.add_argument("--output", "-o", default="./output", help="输出目录")
    parser.add_argument("--model", "-m", default=os.getenv("DEEPAGENTS_MODEL", "openai:gpt-4o"), help="LLM 模型")
    parser.add_argument("--session-id", default="cli-batch", help="批处理 session_id")
    parser.add_argument("--trace-id", default=None, help="批处理 trace_id，默认使用 checkpoint thread_id")
    args = parser.parse_args()

    config = AgentConfig(
        model=args.model,
        input_file=args.input,
        output_dir=args.output,
    )

    print("[1/3] 初始化 Agent runtime...")
    executor = await AgentExecutor.create(config)
    processor = BatchProcessor(executor)
    request = BatchRequest(
        session_id=args.session_id,
        trace_id=args.trace_id or executor.default_thread_id,
        input_file=config.input_file,
        thread_strategy="per_question",
    )

    print(f"[2/3] 执行 batch: {config.input_file}")
    response = await processor.run(request, output_dir=config.output_dir)

    print("[3/3] 生成输出报告...")
    print(f"  → 问题总数: {response.total_questions}")
    print(f"  → Markdown: {response.output_paths['markdown']}")
    print(f"  → JSON: {response.output_paths['json']}")
    print("完成!")


if __name__ == "__main__":
    asyncio.run(main())
