"""
Deep Agents 能力验证 — 6. Human-in-the-Loop

演示 deepagents 的人机交互能力：
- 敏感操作前请求人类审批
- 审批通过后继续执行
- 审批被拒后调整方案
"""

from deepagents import create_deep_agent

agent = create_deep_agent(
    model="openai:gpt-4o",
    system_prompt="你是一个税务助手。对于可能影响重大的操作，先请求用户确认。",
    # 启用 HITL：写文件前需要用户确认
    confirmation_before=["write_file", "edit_file", "execute"],
)

result = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": (
                "我有一家年收入 500 万的公司，"
                "请分析税务情况并写入 tax_analysis.txt 文件。"
            ),
        }
    ]
})

print(result["messages"][-1]["content"])
"""
预期行为：
- agent 进行分析后准备写入文件
- 系统暂停执行，等待用户确认 write_file 操作
- 用户确认后文件写入完成

真实能力来源：deepagents 的 confirmation_before 配置 + HITL middleware

运行说明：
- 交互式环境下会暂停等待输入
- 非交互环境下可能自动跳过确认
"""
