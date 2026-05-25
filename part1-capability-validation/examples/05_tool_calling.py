"""
Deep Agents 能力验证 — 5. Tool Calling

演示 deepagents 的自定义工具注册与调用：
- 注册自定义函数作为工具
- Agent 自动选择并调用合适的工具
- 工具结果参与回答生成
"""

from deepagents import create_deep_agent


def calculate_tax(income: float, rate: float) -> dict:
    """计算应缴税额"""
    tax = income * rate
    return {
        "income": income,
        "rate": rate,
        "tax": round(tax, 2),
        "after_tax": round(income - tax, 2),
    }


def get_tax_rate(tax_type: str, income: float) -> float:
    """根据税种和收入获取适用税率"""
    rates = {
        "增值税": 0.06 if income < 500 else 0.13,
        "企业所得税": 0.025 if income < 300 else 0.25,
        "个人所得税": 0.03 if income < 36 else 0.45,
    }
    return rates.get(tax_type, 0.0)


agent = create_deep_agent(
    model="openai:gpt-4o",
    tools=[calculate_tax, get_tax_rate],
    system_prompt="你是一个税务计算助手。使用提供的工具进行精确计算。",
)

result = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": "一家公司年收入 500 万元，请计算应缴增值税和企业所得税各是多少？",
        }
    ]
})

print(result["messages"][-1]["content"])
"""
预期行为：
- agent 识别需要调用 get_tax_rate 获取税率
- 然后调用 calculate_tax 计算税额
- 最终呈现计算结果

真实能力来源：deepagents 的 tool calling middleware
"""
