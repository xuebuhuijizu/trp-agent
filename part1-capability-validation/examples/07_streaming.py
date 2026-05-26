"""
Deep Agents 能力验证 — 7. Streaming

演示 deepagents 的流式输出能力：
- agent.stream(...)
- stream_mode="messages"
- version="v2"
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
    system_prompt="你是一个税务分析助手。回答时分步骤说明。",
)

for chunk in agent.stream(
    {
        "messages": [
            {
                "role": "user",
                "content": "请用三点说明小规模纳税人与一般纳税人的区别。",
            }
        ]
    },
    stream_mode="messages",
    version="v2",
):
    if chunk["type"] == "messages":
        token, metadata = chunk["data"]
        text = getattr(token, "content", "")
        if text:
            print(text, end="", flush=True)

"""
预期行为：
- 控制台逐步打印模型生成的消息片段
- metadata 可用于观察当前运行节点/上下文

真实能力来源：deepagents/LangGraph 原生 agent.stream(..., stream_mode="messages")
"""
