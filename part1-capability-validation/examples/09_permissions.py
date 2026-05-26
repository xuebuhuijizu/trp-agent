"""
Deep Agents 能力验证 — 9. Filesystem Permissions

演示 deepagents 的文件系统权限控制：
- FilesystemPermission
- permissions=[...]
- 内置文件工具只允许读写指定 workspace
"""

import os
from dotenv import load_dotenv
load_dotenv(dotenv_path=r"E:\ai-project\poc-demo\.env")
from deepagents import FilesystemPermission, create_deep_agent, register_provider_profile, ProviderProfile

register_provider_profile(
    "openai:Minimax-M2.7",
    ProviderProfile(init_kwargs={"use_responses_api": False}),
)

agent = create_deep_agent(
    model=os.getenv("DEEPAGENTS_MODEL", "openai:Minimax-M2.7"),
    permissions=[
        FilesystemPermission(
            operations=["read", "write"],
            paths=["/workspace/**"],
            mode="allow",
        ),
        FilesystemPermission(
            operations=["read", "write"],
            paths=["/**"],
            mode="deny",
        ),
    ],
    system_prompt="你是一个文件助手。只能在 /workspace/ 下读写文件。",
)

result = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": (
                "先尝试写入 /workspace/tax-note.txt，内容为 'allowed'；"
                "再尝试写入 /secret.txt，观察权限拒绝。"
            ),
        }
    ]
})

print(result["messages"][-1].content)

"""
预期行为：
- /workspace/tax-note.txt 写入被允许
- /secret.txt 写入被 permissions 规则拒绝

真实能力来源：deepagents 原生 FilesystemPermission + permissions=[...] 配置
"""
