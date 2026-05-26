"""
Deep Agents 能力验证 — 4. Memory

演示 deepagents 的跨会话记忆能力：
- 跨会话持久化存储
- 在后续会话中回忆之前的上下文
- 实现连续对话
"""

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=r"E:\ai-project\poc-demo\.env")
from deepagents import create_deep_agent, register_provider_profile, ProviderProfile
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from deepagents.backends.utils import create_file_data
from langgraph.store.memory import InMemoryStore



register_provider_profile(
    "openai:Minimax-M2.7",
    ProviderProfile(init_kwargs={"use_responses_api": False}),
)


store = InMemoryStore()
store.put(
    ("tax-memory-demo",),
    "/memories/AGENTS.md",
    create_file_data(
        """## 用户偏好与背景
- 用户关注中国企业税务合规。
- 回答时先说明适用前提，再给结论。
"""
    ),
)


def build_memory_backend(runtime):
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={
            "/memories/": StoreBackend(
                runtime,
                namespace=lambda _runtime: ("tax-memory-demo",),
            ),
        },
    )


agent = create_deep_agent(
    model=os.getenv("DEEPAGENTS_MODEL", "openai:Minimax-M2.7"),
    system_prompt="你是一个税务顾问。读取长期记忆后回答用户问题。",
    memory=["/memories/AGENTS.md"],
    backend=build_memory_backend,
    store=store,
)

# Thread 1：agent 可读取种子记忆并回答
result1 = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": "请说明你回答中国企业税务问题时会遵循什么偏好。",
        }
    ]
}, config={"configurable": {"thread_id": "tax-memory-demo-1"}})
print("Round 1:", result1["messages"][-1].content[:100])

# Thread 2：不同 thread 仍可通过同一 memory backend 读取长期记忆
result2 = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": "我是一家年收入 500 万的软件公司，适合申请小微企业优惠吗？",
        }
    ]
}, config={"configurable": {"thread_id": "tax-memory-demo-2"}})
print("Round 2:", result2["messages"][-1].content[:100])

"""
预期行为：
- agent 从 /memories/AGENTS.md 读取长期记忆
- 不同 thread 的调用仍可共享同一 memory backend 中的持久信息

真实能力来源：deepagents 原生 memory=[...] + StoreBackend 长期记忆机制
"""
