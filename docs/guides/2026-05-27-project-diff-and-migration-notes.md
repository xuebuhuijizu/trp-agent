---
topics: [migration, project-diff, deepagents, demo]
doc_kind: guide
created: 2026-05-27
---

# 项目差异与迁移说明

## 目的

本文档说明当前 `poc-demo` 项目相对 2026-05-26 凌晨第一版的差异，并给出通过聊天软件传输压缩包迁移到公司内网电脑时的打包建议。

## 基线说明

现有 Git 历史中没有 2026-05-26 01:00 整的提交。按当前仓库可追溯历史，最接近“凌晨第一版 6 个功能验证和文档问答”的基线是：

```text
02702ea 2026-05-26 02:26:43 +0800
feat: F001 Deep Agents POC — 初始项目结构与税务 Agent P0 修复
```

该基线提交内容：

- Part 1：6 个 Deep Agents 原生能力验证示例。
- Part 2：税务智能问答 Agent 核心模块。
- 已包含 `.txt` / `.docx` 问题提取、意图分类、静态规划、Agent 执行、Markdown/JSON 输出。
- 当时测试记录为 `28 passed`。

当前版本：

```text
88f868c 2026-05-27 01:07:40 +0800
feat: F002 AC7-10 — Skills + Memory + Structured output
```

当前相对基线的总体 diff：

```text
26 files changed, 1245 insertions(+), 101 deletions(-)
```

## 一句话差异

第一版是“能跑的 DeepAgents POC + 税务文档问答管道”。当前版已经演进为“更贴近 DeepAgents 原生能力的税务 Agent 演示项目”：Part 1 从 6 个示例扩展到 9 个示例，Part 2 从静态规划和空 RAG 占位，升级为原生规划证据、注册检索工具、Skills、Memory、Structured output 和结构化引用输出。

## 提交演进列表

从基线 `02702ea` 到当前 `88f868c` 的主要提交如下：

| commit | 时间 | 说明 |
|---|---:|---|
| `a958a38` | 2026-05-26 17:29 | Part 1 示例模型配置化，替换硬编码模型入口 |
| `b540802` | 2026-05-26 17:32 | 更新 F001 spec AC 状态 |
| `0f4b297` | 2026-05-26 18:17 | 修正 Part 1/Part 2 的 deepagents API 偏差 |
| `76baca2` | 2026-05-26 18:18 | 更新 Completed Work 表 |
| `8e685e0` | 2026-05-26 20:25 | 对齐官方 API，新增 streaming/event-streaming/permissions |
| `21cc93c` | 2026-05-26 20:25 | 修复 streaming v2 格式和 HITL 消息类型安全 |
| `bdd7575` | 2026-05-26 21:18 | 适配 MiniMax OpenAI-compatible 运行环境 |
| `db482b9` | 2026-05-26 21:34 | 清理 deprecated DeepAgents memory backend patterns |
| `cd4ebe6` | 2026-05-26 21:40 | 同步 F001 验证完成记录 |
| `3cdaee8` | 2026-05-26 23:05 | 新增 F002 spec 和概念校准记录 |
| `eeb2900` | 2026-05-27 00:09 | F002 文档中文化并补语言规则 |
| `71426b7` | 2026-05-27 00:34 | F002 第一刀：架构换轨，贴近 DeepAgents-native |
| `c53e663` | 2026-05-27 00:57 | 同步 F002 第一刀 AC 状态 |
| `88f868c` | 2026-05-27 01:07 | F002 AC7-10：Skills + Memory + Structured output |

## Part 1 差异：能力验证示例

### 第一版

第一版有 6 个示例：

1. `01_file_tools.py`
2. `02_sub_agent.py`
3. `03_planning.py`
4. `04_memory.py`
5. `05_tool_calling.py`
6. `06_human_in_loop.py`

### 当前版

当前版保留并修正了原 6 个示例，同时新增 3 个扩展示例：

7. `07_streaming.py`
8. `08_event_streaming.py`
9. `09_permissions.py`

关键变化：

- 示例模型从硬编码改为可通过环境变量配置。
- Sub-agent、Memory、HITL 等示例向官方 DeepAgents API 对齐。
- HITL 从旧的 `confirmation_before` 形态修正为 `interrupt_on` / `Command(resume=...)` 链路。
- 新增 streaming 和 event streaming，用于展示过程可观察性。
- 新增 filesystem permissions，用于展示路径级读写权限控制。
- 新增 `part2-tax-agent/tests/test_part1_deepagents_examples.py`，覆盖 Part 1 示例的静态/语法验证。

## Part 2 差异：税务文档问答 Agent

### 第一版

第一版流程大致是：

```text
输入文件
  -> 问题提取
  -> 意图分类
  -> 静态 Planner 生成步骤
  -> DeepAgents 回答
  -> 可选 NoopRAG 装饰
  -> Markdown/JSON 输出
```

当时已经能证明端到端文档问答管道可运行，但有几个限制：

- `Planner` 是项目层静态模板，不是 DeepAgents 原生规划。
- `RAGDecorator` 默认是 `NoopRAG`，没有真正检索知识。
- 输出中的 citations 主要依赖文本正则提取。
- 可能出现 `<think>...</think>` 这类模型内部推理标签泄漏。
- 没有 DeepAgents Skills、Memory 和 structured output schema。

### 当前版

当前版流程已调整为：

```text
输入文件
  -> 问题提取
  -> 意图分类作为报告元数据
  -> DeepAgents Agent 原生执行
       -> write_todos 规划证据
       -> retrieve_tax_context 检索工具
       -> skills=["/skills"]
       -> memory=["/memories/AGENTS.md"]
       -> response_format=TaxAnswer
  -> 输出格式化器
       -> 清理推理标签
       -> 写入 structured citations
       -> Markdown/JSON 输出
```

关键变化：

- `main.py` 主路径不再依赖静态 `Planner` 驱动回答。
- 新增 `part2-tax-agent/tax_retrieval.py`，提供本地税务知识片段检索工具 `retrieve_tax_context`。
- `AgentExecutor` 通过 `create_deep_agent(tools=[retrieve_tax_context])` 注册检索工具。
- 新增 DeepAgents Skills 文件：`part2-tax-agent/skills/tax-answering/SKILL.md`。
- 新增 DeepAgents Memory 文件：`part2-tax-agent/memories/AGENTS.md`。
- 新增 Pydantic schema：`TaxCitation` / `TaxAnswer`。
- `create_deep_agent(...)` 现在使用 `skills`、`memory`、`FilesystemBackend` 和 `response_format=TaxAnswer`。
- `execute_with_evidence` 会优先读取 `structured_response`，并保留 tool events。
- `output_formatter.py` 会清理 `<think>` 标签并写入结构化 citations。

## 文档差异

新增文档：

- `docs/discussions/2026-05-26-deepagents-concept-calibration.md`
  - 用于区分 DeepAgents-native、project adapter、demo-only scaffolding。
  - 明确意图分类不是 DeepAgents 原生能力。
  - 明确原静态 Planner 和 NoopRAG 的边界。

- `docs/features/F002-deepagents-native-tax-agent-spec.md`
  - 记录 F002 的目标、范围、验收标准和三刀实施顺序。
  - 当前 AC1-AC11 均已勾选完成。

更新文档：

- `docs/features/F001-deepagents-poc-spec.md`
  - 更新 F001 完成记录。
  - 记录 Part 1 示例从 6 个扩展到 9 个并完成真实模型验证。

- `docs/guides/demo-walkthrough.md`
  - 从“6 个示例”更新为“6 个核心示例 + 3 个扩展示例”。
  - 增加 streaming、event streaming、permissions 的演示步骤。
  - 更新 Part 2 当前执行路径和输出预期。

## 依赖变化

基线 `part2-tax-agent/requirements.txt`：

```text
deepagents>=0.6.3
python-docx>=1.1.2
pydantic>=2.0
```

当前 `part2-tax-agent/requirements.txt`：

```text
deepagents>=0.6.3
langchain-ollama>=1.0
python-docx>=1.1.2
pydantic>=2.0
```

新增 `langchain-ollama>=1.0` 是为了更明确支持本地 Ollama 模型入口。当前项目也可通过 `.env` / provider profile 使用 MiniMax OpenAI-compatible 运行环境，但 `.env` 不建议通过聊天软件传输。

## 当前验证结果

在当前 sandbox 中，默认 pytest 首次运行失败在临时目录权限，而不是代码逻辑：

```text
PermissionError: [WinError 5] 拒绝访问。: 'C:\\Users\\Lee\\AppData\\Local\\Temp\\pytest-of-Lee'
```

改用仓库内可写临时目录后验证通过：

```powershell
$env:TEMP='E:\ai-project\poc-demo\.codex-tmp'
$env:TMP='E:\ai-project\poc-demo\.codex-tmp'
python -m pytest -q --basetemp=E:\ai-project\poc-demo\.codex-tmp\pytest-full -o cache_dir=E:\ai-project\poc-demo\.codex-tmp\cache-full
```

结果：

```text
40 passed in 0.22s
```

Part 2 单测：

```text
33 passed in 0.21s
```

历史 E2E 输出文件中，最近一份完整报告为：

```text
part2-tax-agent/output/tax_report_20260527_011411.md
part2-tax-agent/output/tax_report_20260527_011411.json
```

注意：`part2-tax-agent/output/` 已在 `.gitignore` 中，属于演示产物，不是源码必需项。

## 迁移压缩包建议

### 推荐方案 A：只传源码和文档

如果目标是在公司内网电脑重新安装依赖并运行项目，推荐只传 Git tracked 源码：

```powershell
cd E:\ai-project\poc-demo
git archive --format=zip --output ..\poc-demo-20260527-source.zip HEAD
```

这个压缩包会包含当前提交中的源码和已提交文档，不会包含：

- `.env`
- `.venv/`
- `.pytest_cache/`
- `__pycache__/`
- `part2-tax-agent/output/`
- 本机工具目录
- 临时测试目录

这是最干净、最适合迁移的包。

注意：如果本文件 `docs/guides/2026-05-27-project-diff-and-migration-notes.md` 还没有提交到 Git，`git archive HEAD` 不会包含它。此时请二选一：

1. 先提交本文件，再执行 `git archive HEAD`。
2. 或者把 `poc-demo-20260527-source.zip` 和本文件单独一起发送。

本次写文档时，当前 sandbox 用户对 `.git/index.lock` 没有写权限，无法替你完成提交；源码文件已经落在工作区中。

### 推荐方案 B：源码 + 演示输出

如果希望内网电脑上也能直接查看已经生成的报告，可以额外把最近报告单独压缩：

```powershell
Compress-Archive `
  -Path part2-tax-agent\output\tax_report_20260527_011411.md,part2-tax-agent\output\tax_report_20260527_011411.json `
  -DestinationPath ..\poc-demo-20260527-demo-output.zip `
  -Force
```

不要把整个 `output/` 都作为必须内容传输；它是运行产物，不是项目源码。

### 不建议打包的内容

以下内容不建议放进聊天软件传输包：

- `.env`：可能包含 API key 或本机配置。到内网电脑后重新创建。
- `.venv/`：体积大，且跨机器路径/平台容易失效。
- `__pycache__/`、`.pytest_cache/`、`.pytest_tmp*/`：缓存和临时测试目录。
- `.cat-cafe/`、`.claude/`、`.codex/`、`.gemini/`、`.kimi/`：本机工具状态目录，不是项目源码。
- `.git/`：如果只是迁移源码演示，不必带 Git 历史；若公司内网要继续开发，可另行决定是否传完整仓库。

## 内网电脑恢复步骤

1. 解压 `poc-demo-20260527-source.zip`。

2. 创建虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

3. 安装依赖：

```powershell
pip install -r part2-tax-agent\requirements.txt
```

如果内网不能访问公网，需要在个人电脑先下载 wheels：

```powershell
pip download -r part2-tax-agent\requirements.txt -d wheels
Compress-Archive -Path wheels -DestinationPath ..\poc-demo-20260527-wheels.zip -Force
```

到内网电脑后：

```powershell
pip install --no-index --find-links .\wheels -r part2-tax-agent\requirements.txt
```

4. 创建新的 `.env`。

`.env` 不应从个人电脑直接通过聊天软件传输。内网电脑上按可用模型/provider 重新配置。

5. 验证基础测试：

```powershell
python -m pytest -q
```

如遇 Windows 临时目录权限问题，可指定本项目内临时目录：

```powershell
mkdir .pytest-local-tmp
$env:TEMP=(Resolve-Path .pytest-local-tmp)
$env:TMP=(Resolve-Path .pytest-local-tmp)
python -m pytest -q --basetemp=.pytest-local-tmp\pytest-run -o cache_dir=.pytest-local-tmp\cache
```

6. 运行 Part 1 示例：

```powershell
cd part1-capability-validation\examples
python 01_file_tools.py
```

7. 运行 Part 2 税务问答：

```powershell
cd ..\..\part2-tax-agent
python main.py --input sample_input.txt --output .\output
```

## 迁移前最终检查清单

- [ ] 已确认要迁移的是当前 commit `88f868c`。
- [ ] 已确认本差异文档已提交，或已单独加入聊天软件传输包。
- [ ] 已决定是否只传源码，还是源码加最近演示输出。
- [ ] 不传 `.env`。
- [ ] 不传 `.venv/`。
- [ ] 不传缓存目录和临时目录。
- [ ] 如果内网无公网访问，另行准备 `wheels` 依赖包。
- [ ] 内网电脑上重新创建 `.env` 和模型/provider 配置。

## 当前能力分类

| 能力 | 当前状态 | 分类 |
|---|---|---|
| `create_deep_agent` 主执行 | 已接入 | DeepAgents-native |
| `write_todos` 规划证据 | 已有运行/输出证据 | DeepAgents-native |
| `retrieve_tax_context` | 本地税务知识检索工具 | project adapter |
| `skills=["/skills"]` | 已接入 `SKILL.md` | DeepAgents-native |
| `memory=["/memories/AGENTS.md"]` | 已接入语义记忆 | DeepAgents-native |
| `response_format=TaxAnswer` | 已接入 structured output | DeepAgents-native / LangChain-native |
| `IntentClassifier` | 仅作为报告元数据 | project adapter |
| `Planner` | 保留为遗留兼容，主路径不再依赖 | demo-only scaffolding / legacy adapter |
| `output_formatter.py` | Markdown/JSON 落盘和清理 | project adapter |
| `sample_input.txt` | 演示输入 | demo-only scaffolding |
