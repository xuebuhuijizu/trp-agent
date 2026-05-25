"""
Deep Agents 能力验证 — 4. Memory

演示 deepagents 的跨会话记忆能力：
- 跨会话持久化存储
- 在后续会话中回忆之前的上下文
- 实现连续对话
"""

from deepagents import create_deep_agent

agent = create_deep_agent(
    model="openai:gpt-4o",
    system_prompt="你是一个税务顾问。记住用户之前提到的信息并在后续回答中引用。",
    # 启用持久化存储
    store={"type": "file", "namespace": "tax_memory_demo"},
)

# 第一轮对话
result1 = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": "你好，我是一家软件公司，年收入 500 万元。请记住我的信息。",
        }
    ]
})
print("Round 1:", result1["messages"][-1]["content"][:100])

# 第二轮对话（使用同一个 agent 实例）
result2 = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": "根据我之前说的公司情况，我适合申请小微企业税收优惠吗？",
        }
    ]
})
print("Round 2:", result2["messages"][-1]["content"][:100])

"""
预期行为：
- 第一轮 agent 记住用户是软件公司、年收入 500 万
- 第二轮 agent 从记忆中检索并利用这些信息回答问题

真实能力来源：deepagents 的 store backend + memory middleware
"""
