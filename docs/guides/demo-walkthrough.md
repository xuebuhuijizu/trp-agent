---
topics: [demo, walkthrough, poc, deepagents]
doc_kind: guide
created: 2026-05-26
---

# Deep Agents POC 演示步骤

## 概述

本文档为两部分演示的完整操作步骤。预计总时长：30–45 分钟。

- **Part 1**（15 min）：6 个 Deep Agents 原生能力验证示例
- **Part 2**（20 min）：税务智能问答 Agent 端到端演示

---

## 前置准备

### 环境要求

| 项目 | 要求 |
|------|------|
| Python | ≥ 3.11 |
| 包管理 | pip 或 uv |
| Ollama（可选） | 如演示 Part 2 需要本地模型 |

### 安装步骤

```bash
# 1. 进入项目目录
cd poc-demo

# 2. 创建虚拟环境（推荐）
python -m venv .venv
.venv\Scripts\activate    # Windows
# source .venv/bin/activate  # Mac/Linux

# 3. 安装依赖
pip install deepagents langchain-ollama pydantic
pip install python-docx    # 仅当演示 .docx 输入时
```

### 验证安装

```bash
python -c "from deepagents import create_deep_agent; print('deepagents OK')"
python -c "from pydantic import BaseModel; print('pydantic OK')"
```

---

## Part 1：Deep Agents 能力验证（6 个核心示例 + 3 个扩展示例）

每个示例是一个独立的 Python 脚本，演示 Deep Agents 的一项原生能力。示例 1-6 对应原始 POC 范围，示例 7-9 补充官方文档中同属核心路径的流式输出、事件流和权限控制。

> **演示技巧**：逐个运行，每运行一个先问观众"猜猜 agent 会调用哪些工具？"，然后运行验证。

### 示例 1：File Tools

**演示目标**：展示 agent 自动调用文件读写、搜索工具

```bash
cd part1-capability-validation/examples
python 01_file_tools.py
```

**预期行为**：
1. Agent 先调用 `write_file` 写入 `hello.txt`
2. 调用 `read_file` 读取内容确认
3. 调用 `grep` 搜索关键词
4. 调用 `edit_file` 修改内容
5. 再次 `read_file` 验证修改

**证据**：控制台输出显示每一步的调用结果，最终文件内容从 "Hello Deep Agents" 变为 "Hello World"

---

### 示例 2：Sub-agent

**演示目标**：展示主 Agent 使用自定义 subagents 处理独立子任务

```bash
python 02_sub_agent.py
```

**预期行为**：
1. Agent 识别两个需要独立处理的子问题
2. 通过 `subagents=[...]` 定义的 `tax-policy-researcher` / `tax-calculation-reviewer` 执行委托
3. 子 Agent 在隔离上下文中完成研究或计算复核
4. 主 Agent 汇总两个子 Agent 的发现

**证据**：输出中能看到两次独立的子任务调用，最终是汇总后的完整回答

---

### 示例 3：Planning

**演示目标**：展示 agent 用 `write_todos` 分解复杂任务

```bash
python 03_planning.py
```

**预期行为**：
1. Agent 收到复杂税务分析请求
2. 调用 `write_todos` 列出分析步骤（如：确定税种、查找税率、计算税额、汇总）
3. 逐项执行并标记为完成
4. 输出完整分析

**证据**：输出中包含 "To-Do" 列表和执行进度标记

---

### 示例 4：Memory

**演示目标**：展示 `memory=[...]` + backend/store 的长期记忆

```bash
python 04_memory.py
```

**预期行为**：
1. 示例先在 `InMemoryStore` 中写入 `/memories/AGENTS.md`
2. Agent 通过 `memory=["/memories/AGENTS.md"]` 加载长期记忆
3. 两个不同 `thread_id` 的调用共享同一 memory backend
4. Agent 回答时引用记忆中的回答偏好与税务背景

**证据**：不同 thread 的回答仍体现 `/memories/AGENTS.md` 中的长期记忆内容

---

### 示例 5：Tool Calling

**演示目标**：展示自定义工具注册与调用

```bash
python 05_tool_calling.py
```

**预期行为**：
1. Agent 收到税务计算请求
2. 自动选择并调用 `get_tax_rate` 获取税率
3. 调用 `calculate_tax` 计算税额
4. 呈现计算结果

**证据**：输出中包含精确的数字计算结果，而非 LLM 估算

---

### 示例 6：Human-in-the-Loop

**演示目标**：展示敏感操作前的用户审批流程

```bash
python 06_human_in_loop.py
```

**预期行为**：
1. Agent 分析税务情况后决定写入文件
2. 触发 `interrupt_on` 机制，返回 interrupt
3. 同一 `thread_id` 使用 `Command(resume=...)` 恢复
4. 用户批准后文件写入，拒绝后 Agent 调整回答

**证据**：控制台显示 action_requests，用户确认后通过 resume 继续执行

> **注意**：HITL 示例依赖交互式终端；非交互环境建议只阅读代码或用 mock 验证 API 形状。

---

### 示例 7：Streaming

**演示目标**：展示 `agent.stream(..., stream_mode="messages", version="v2")` 的消息流式输出。

```bash
python 07_streaming.py
```

**预期行为**：
1. Agent 开始回答税务问题
2. 控制台逐步打印生成的消息片段
3. 可通过 metadata 观察当前运行节点/上下文

**证据**：回答不是一次性完整输出，而是随模型生成逐步出现。

---

### 示例 8：Event Streaming

**演示目标**：展示 `agent.stream_events(..., version="v3")` 的事件投影，包括 messages、tool_calls、subagents。

```bash
python 08_event_streaming.py
```

**预期行为**：
1. `stream.messages` 输出协调 Agent 消息
2. `stream.tool_calls` 输出顶层工具调用
3. `stream.subagents` 输出子 Agent 生命周期、消息和工具调用

**证据**：控制台能区分 `[coordinator]` 与 `[subagent]` 事件来源。

---

### 示例 9：Filesystem Permissions

**演示目标**：展示 `FilesystemPermission` 与 `permissions=[...]` 对内置文件工具的路径权限控制。

```bash
python 09_permissions.py
```

**预期行为**：
1. `/workspace/tax-note.txt` 写入被允许
2. `/secret.txt` 写入被拒绝
3. Agent 在回答中说明权限拒绝结果

**证据**：输出中出现允许写入和权限拒绝两个结果。

---

## Part 2：税务智能问答 Agent 端到端演示

### 整体流程

```
输入文件 (.txt/.docx) → 问题提取 → 意图分类 → 任务规划 → Agent 执行 → 双格式输出
```

### 准备工作

确保已安装 `deepagents` 和 `pydantic`。

确认本地有运行中的 Ollama 实例（或修改 `part2-tax-agent/main.py` 中的模型名指向可用的 LLM）。

```bash
# 检查 Ollama 状态
ollama list
# 如无模型，拉取一个（推荐 qwen2.5 或 llama3.1）
ollama pull qwen2.5
```

### 步骤 1：使用默认示例运行

```bash
cd part2-tax-agent
python main.py --input sample_input.txt --output ./output
```

**预期输出**：
```
[1/5] 提取问题: sample_input.txt
  → 提取到 10 个问题
[2/5] 意图分类...
  [definition] 什么是增值税？...
  [rate] 企业所得税的税率是多少？...
  [compliance] 我的公司年收入300万，需要缴纳哪些税？...
  ...
[3/5] 任务规划...
[4/5] 执行 Agent 回答...
  → 回答: 什么是增值税？...
  → 回答: 企业所得税的税率是多少？...
  ...
[5/5] 生成输出报告...
  → Markdown: output/tax_report_20260526_XXXXXX.md
  → JSON: output/tax_report_20260526_XXXXXX.json
完成!
```

### 步骤 2：查看输出文件

**Markdown 报告** (`output/tax_report_*.md`)：

```markdown
# 税务智能问答报告
生成时间：2026-05-26 17:30:00
问题总数：10

---

### 📖 定义查询

**问题**：什么是增值税？
**回答**：增值税是一种流转税...
---

### 💰 税率计算

**问题**：企业所得税的税率是多少？
**回答**：企业所得税基本税率为 25%...
---
```

**JSON 报告** (`output/tax_report_*.json`)：

```json
{
  "report_meta": {
    "generated_at": "2026-05-26T17:30:00",
    "total_questions": 10
  },
  "answers": [
    {
      "question": "什么是增值税？",
      "intent": "definition",
      "answer": "增值税是一种流转税...",
      "citations": ["来源: 增值税暂行条例"]
    }
  ]
}
```

### 步骤 3：使用自己的文件

准备一份 Word 文档（.docx）或文本文件，每行或每段一个税务问题：

```bash
python main.py --input 我的税审问题.docx --output ./my_report
```

**支持的文件格式**：
| 格式 | 说明 |
|------|------|
| `.txt` | UTF-8 编码，按 `?` 或 `？` 拆分问题 |
| `.docx` | 解析所有段落文本，同样按问号拆分 |

### 步骤 4：切换模型

```bash
python main.py --input sample_input.txt --model ollama:qwen2.5
```

可选的模型格式：
- `ollama:qwen2.5` — 本地 Ollama
- `openai:gpt-4o` — OpenAI API
- `anthropic:claude-sonnet-4` — Anthropic API
- 任何 LangChain 支持的 ChatModel

---

## 验收检查清单

演示完成后，对照以下清单逐条确认：

### Part 1 能力验证

- [ ] 示例 1：File Tools — 文件读写搜索全链路跑通
- [ ] 示例 2：Sub-agent — 子 Agent 创建并返回结果
- [ ] 示例 3：Planning — write_todos 分解并执行
- [ ] 示例 4：Memory — 跨轮对话记忆生效
- [ ] 示例 5：Tool Calling — 自定义工具被正确调用
- [ ] 示例 6：Human-in-the-Loop — interrupt/resume 审批链路生效
- [ ] 示例 7：Streaming — messages 流式输出可观察
- [ ] 示例 8：Event Streaming — subagents/messages/tool_calls 投影可观察
- [ ] 示例 9：Filesystem Permissions — allow/deny 路径规则生效

### Part 2 税务 Agent

- [ ] 问题提取：从文件正确提取所有问题
- [ ] 意图分类：定义/税率/合规三类区分合理
- [ ] 任务规划：每个问题有独立的执行计划
- [ ] Agent 执行：deepagents 回答了每个问题
- [ ] 输出格式：Markdown 分节 + JSON 结构化均生成
- [ ] 引用标注：输出中包含来源标注
- [ ] 适配器预留：PlannerAdapter 和 RAGAdapter 接口可用

---

## 常见问题

**Q: 运行时提示 `ModuleNotFoundError: No module named 'deepagents'`**
A: 未安装 deepagents。执行 `pip install deepagents`。

**Q: Part 2 长时间无响应**
A: 确认 Ollama 服务正常运行，且模型已下载。首次加载模型可能需要 10–30 秒。

**Q: 提示 `Model not found`**
A: 运行 `ollama pull <模型名>` 先拉取模型，或修改 main.py 中的 `model` 参数指向可用模型。

**Q: 中文显示乱码**
A: 确认终端支持 UTF-8。Windows 终端执行 `chcp 65001` 切换到 UTF-8。
