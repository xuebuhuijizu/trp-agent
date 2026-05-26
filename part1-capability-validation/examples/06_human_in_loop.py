"""
Deep Agents 能力验证 — 6. Human-in-the-Loop

演示 deepagents 的人机交互能力：
- 敏感操作前请求人类审批
- 审批通过后继续执行
- 审批被拒后调整方案
"""

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=r"E:\ai-project\poc-demo\.env")
from deepagents import create_deep_agent, register_provider_profile, ProviderProfile
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

register_provider_profile(
    "openai:Minimax-M2.7",
    ProviderProfile(init_kwargs={"use_responses_api": False}),
)


checkpointer = MemorySaver()

agent = create_deep_agent(
    model=os.getenv("DEEPAGENTS_MODEL", "openai:Minimax-M2.7"),
    system_prompt="你是一个税务助手。对于可能影响重大的操作，先请求用户确认。",
    # 启用 HITL：写/编辑文件前暂停等待用户确认
    interrupt_on={"write_file": True, "edit_file": True},
    checkpointer=checkpointer,
)

config = {"configurable": {"thread_id": "tax-hitl-demo"}}
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
}, config=config, version="v2")

if result.interrupts:
    interrupt_value = result.interrupts[0].value
    action_requests = interrupt_value["action_requests"]
    print("需要人工确认以下工具调用：")
    for action in action_requests:
        print(f"- {action['name']}: {action.get('args', {})}")

    approved = input("批准执行这些工具调用吗？输入 y 批准，其它输入拒绝：").strip().lower() == "y"
    decisions = [{"type": "approve" if approved else "reject"} for _ in action_requests]
    result = agent.invoke(
        Command(resume={"decisions": decisions}),
        config=config,
        version="v2",
    )

messages = result.value["messages"] if hasattr(result, "value") else result["messages"]
last = messages[-1]
if isinstance(last, dict):
    text = last.get("content", "")
else:
    text = last.content
print(text)
"""
预期行为：
- agent 进行分析后准备写入文件
- interrupt_on 捕获 write_file/edit_file 工具调用
- checkpointer 保存暂停状态，同一个 thread_id 用 Command(resume=...) 恢复
- 用户批准后文件写入，拒绝后 agent 调整回答

真实能力来源：deepagents 原生 interrupt_on + checkpointer + LangGraph Command(resume=...)

运行说明：
- 交互式环境下会暂停等待输入
- 非交互环境建议只阅读代码，不直接运行
"""
