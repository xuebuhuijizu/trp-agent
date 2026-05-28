"""
Deep Agents 能力验证 — 8. Event Streaming

演示 deepagents 的事件流投影：
- agent.stream_events(..., version="v3")
- stream.messages
- stream.subagents
- stream.tool_calls
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
            "description": "Researches tax policy context and returns concise findings.",
            "system_prompt": "你是税务政策研究子 Agent。输出简洁研究结论。",
        }
    ],
    system_prompt="你是协调 Agent。需要研究时使用 task 工具委托给 tax-policy-researcher。",
)

stream = agent.stream_events(
    {
        "messages": [
            {
                "role": "user",
                "content": "委托子 Agent 研究：什么是进项税额？然后汇总回答。",
            }
        ]
    },
    version="v3",
)

for message in stream.messages:
    print("[coordinator]", message.text)

for call in stream.tool_calls:
    print("[coordinator tool]", call.tool_name, call.input)

for subagent in stream.subagents:
    print(f"[subagent] {subagent.name} {subagent.status}")
    for message in subagent.messages:
        print(f"[{subagent.name}]", message.text)
    for call in subagent.tool_calls:
        print(f"[{subagent.name} tool]", call.tool_name, call.input)

"""
预期行为：
- stream.messages 展示协调 Agent 消息
- stream.tool_calls 展示顶层工具调用
- stream.subagents 展示子 Agent 生命周期与子 Agent 内部消息/工具调用

真实能力来源：deepagents 原生 agent.stream_events(..., version="v3") 事件投影
"""
