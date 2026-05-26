"""
Deep Agents 能力验证 — 1. File Tools

演示 deepagents 内置的文件系统工具：
- read_file: 读取文件
- write_file: 写入文件
- edit_file: 编辑文件
- glob: 查找文件
- grep: 搜索文件内容
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
    model=os.getenv("DEEPAGENTS_MODEL", "openai:Minimax-M2.7"),  # 可通过环境变量 DEEPAGENTS_MODEL 覆盖
    system_prompt="你是一个文件操作助手。使用文件工具完成需求。",
)

result = agent.invoke({
    "messages": [
        {
            "role": "user",
            "content": (
                "1. 在当前目录写入一个文件 hello.txt，内容为 'Hello Deep Agents!'\n"
                "2. 读取该文件内容\n"
                "3. 用 grep 搜索包含 'Agents' 的文件\n"
                "4. 编辑文件，将 'Agents' 替换为 'World'\n"
                "5. 读取修改后的文件确认"
            ),
        }
    ]
})

print(result["messages"][-1].content)
"""
预期行为：
- agent 会依次调用 write_file → read_file → grep → edit_file → read_file
- 每一步的结果会在回答中展示

真实能力来源：deepagents 内置的 file_tools middleware
"""
