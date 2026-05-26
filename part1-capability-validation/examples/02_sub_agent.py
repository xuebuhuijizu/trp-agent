"""
Deep Agents 能力验证 — 2. Sub-agent

演示 deepagents 的子 Agent 孵化能力：
- 主 Agent 可以将子任务委托给子 Agent
- 子 Agent 拥有隔离的上下文窗口
- 子 Agent 的结果返回给主 Agent
"""

import os
from deepagents import create_deep_agent

agent = create_deep_agent(
    model=os.getenv("DEEPAGENTS_MODEL", "ollama:llama3.1"),
    system_prompt=(
        "你是一个研究助手。对于需要深入研究的子问题，"
        "使用 task 工具创建子 Agent 来处理，"
        "然后汇总子 Agent 的结果。"
    ),
)

result = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": (
                "请同时研究两个问题，分别交给子 Agent 处理：\n"
                "1. 什么是增值税？\n"
                "2. 增值税和企业所得税的区别是什么？\n"
                "然后汇总两个子 Agent 的发现。"
            ),
        }
    ]
})

print(result["messages"][-1]["content"])
"""
预期行为：
- agent 会调用 task 工具创建子 agent
- 子 agent 分别研究各自的问题
- 主 agent 汇总两个子 agent 的结果

真实能力来源：deepagents 内置的 task tool + sub-agent middleware
"""
