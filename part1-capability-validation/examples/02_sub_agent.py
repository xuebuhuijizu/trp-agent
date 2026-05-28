"""
Deep Agents 能力验证 — 2. Sub-agent

演示 deepagents 的子 Agent 孵化能力：
- 主 Agent 可以将子任务委托给子 Agent
- 子 Agent 拥有隔离的上下文窗口
- 子 Agent 的结果返回给主 Agent
"""

import os
from dotenv import load_dotenv
load_dotenv()
from deepagents import create_deep_agent, register_provider_profile, ProviderProfile

register_provider_profile("openai",
    ProviderProfile(init_kwargs={"use_responses_api": False}),
)

agent = create_deep_agent(
    model=os.getenv("DEEPAGENTS_MODEL", "openai:gpt-4o"),
    subagents=[
        {
            "name": "tax-policy-researcher",
            "description": "Researches tax policy definitions, compliance rules, and legal context.",
            "system_prompt": (
                "你是税务政策研究子 Agent。只处理法规、定义、合规判断相关问题，"
                "输出要简洁列出依据和不确定性。"
            ),
        },
        {
            "name": "tax-calculation-reviewer",
            "description": "Reviews tax-rate and calculation questions for arithmetic and assumptions.",
            "system_prompt": (
                "你是税务计算复核子 Agent。只处理税率、税额、计算口径相关问题，"
                "输出计算步骤、假设和复核结论。"
            ),
        },
    ],
    system_prompt=(
        "你是一个研究助手。对于需要深入研究的子问题，"
        "使用 task 工具委托给 tax-policy-researcher 或 tax-calculation-reviewer，"
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
                "2. 年收入 500 万的企业，企业所得税如何估算？\n"
                "然后汇总两个子 Agent 的发现。"
            ),
        }
    ]
})

print(result["messages"][-1].content)
"""
预期行为：
- agent 会调用 task 工具委托给自定义 subagents
- tax-policy-researcher 研究税务定义/法规问题
- tax-calculation-reviewer 复核税率/计算问题
- 主 agent 汇总两个子 agent 的结果

真实能力来源：deepagents 原生 task tool + subagents=[...] 自定义子 Agent 配置
"""
