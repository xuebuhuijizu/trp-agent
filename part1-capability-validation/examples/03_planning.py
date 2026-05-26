"""
Deep Agents 能力验证 — 3. Planning

演示 deepagents 的任务规划能力：
- write_todos: 将复杂任务分解为可执行步骤
- 跟踪任务进度
- 逐步执行并标记完成
"""

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=r"E:\ai-project\poc-demo\.env")
from deepagents import create_deep_agent, register_provider_profile, ProviderProfile

register_provider_profile(
    "openai:Minimax-M2.7",
    ProviderProfile(init_kwargs={"use_responses_api": False}),
)

agent = create_deep_agent(
    model=os.getenv("DEEPAGENTS_MODEL", "openai:Minimax-M2.7"),
    system_prompt=(
        "你是一个税务分析助手。面对复杂问题，"
        "先用 write_todos 工具列出执行计划，"
        "然后逐项执行，每完成一项标记完成。"
    ),
)

result = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": (
                "分析一家小型科技公司（年收入 500 万元）"
                "需要缴纳哪些税？请先制定计划再执行。"
            ),
        }
    ]
})

print(result["messages"][-1].content)
"""
预期行为：
- agent 先调用 write_todos 列出计划项
- 逐项执行并在完成后标记
- 最终输出完整的分析结果

真实能力来源：deepagents 内置的 planning middleware + write_todos tool
"""
