---
feature_ids: [F001]
topics: [deepagents, poc, tax-agent]
doc_kind: spec
created: 2026-05-26
---

# F001: Deep Agents POC — 税务智能问答 Agent

## Goal

基于 Deep Agents (langchain-ai/deepagents) 框架，构建一个 POC 项目，验证框架核心能力，并实现一个本地部署的税务专业问答 Agent。

## 项目结构双部曲

### Part 1 — 能力验证 & 演示文档

**受众**：Java 技术团队（需补充 Python 前置知识）
**产出形式**：文档 + 可运行示例
**验证能力清单**（全部基于 Deep Agents 原生实现，非 mock）：

| # | 能力 | 说明 |
|---|------|------|
| 1 | File Tools | read/write/edit/glob/grep |
| 2 | Sub-agent | 子 Agent 孵化与隔离上下文 |
| 3 | Planning | write_todos 任务规划 |
| 4 | Memory | 跨会话持久化记忆 |
| 5 | Tool Calling | 自定义工具注册与调用 |
| 6 | Human-in-the-Loop | 工具调用前审批 |
| 7 | Streaming | message streaming |
| 8 | Event streaming | subagents / messages / tool_calls 事件投影 |
| 9 | Filesystem permissions | 内置文件工具路径权限控制 |

### Part 2 — 税务 Agent

**LLM**：本地模型（Ollama/vLLM），本地起服务，可调外网
**输入**：Word (.docx) 单文件，MB 级
**税务范围**：不限税种，知识来源为模型内置（预留 RAG 装饰器接口）
**意图识别**：三类 — 定义查询 / 税率计算 / 合规判断
**任务规划**：先拆分问题集合，每个问题独立规划；使用默认规划器，预留适配器接口
**输出结构**：Markdown 分节 + JSON 结构化，带引用标注

## Acceptance Criteria

1. [x] Part 1: 6 个核心示例 + 3 个扩展示例已对齐官方 API；语法/静态测试通过；9/9 示例已在 MiniMax OpenAI-compatible 运行环境完成真实模型验证
2. [x] Part 1: Java 开发者可独立阅读前置知识指南后理解示例
3. [x] Part 2: 可接受一份 Word 文档并自动提取问题
4. [x] Part 2: 问题意图分类准确（定义/税率/合规）
5. [x] Part 2: 每个问题独立规划并执行回答
6. [x] Part 2: 输出同时包含 Markdown 分节和 JSON 结构化结果
7. [x] Part 2: 输出含引用标注
8. [x] Part 2: RAG 装饰器已预留，后期可接入
9. [x] Part 2: 规划器适配器已预留，后期可替换
10. [ ] POC 验收：专家认可度 ≥ 80%

## Architecture

```
Word Document (.docx)
    ↓
[question_extractor] → list[str]
    ↓
[intent_classifier] → [{question, intent}]
    ↓
[planner (adapter)] → [{question, intent, plan_steps}]
    ↓
[agent_executor (deepagents)]
    ├── Tax Skills / Tools
    ├── Memory (cross-question)
    └── HITL (optional)
    ↓
[output_formatter] → {markdown, json, citations}
```

## Tech Stack

| Layer | Choice |
|-------|--------|
| Framework | deepagents ≥ 0.6.3 |
| LLM | Configurable via `DEEPAGENTS_MODEL`; MiniMax OpenAI-compatible runtime validated, Ollama local runtime remains supported |
| Providers | OpenAI-compatible (`langchain-openai`) + Ollama (`langchain-ollama`) |
| File parsing | python-docx |
| Output | Markdown + JSON |
| Runtime | Python ≥ 3.11 |

## Completed Work

| Round | Item | Commit |
|-------|------|--------|
| P0 | 问号字符统一（全角/半角） | `02702ea` |
| P0 | 大文本 fallback 上限 2000 字符截断 | `02702ea` |
| P0 | LLM 异常回落规则分类（try/except → _rule_based） | `02702ea` |
| P0 | citation 结构化正则抽取（`[来源:]/[依据:]/[参考:]` 格式） | `02702ea` |
| P0 | agent_executor 可注入测试路径 + mock 覆盖 | `02702ea` |
| P0 | build_agent 改为 @staticmethod 归入 AgentExecutor | `02702ea` |
| P1 | Part 1 示例模型配置化（`DEEPAGENTS_MODEL` 环境变量） | `a958a38` |
| P1 | deepagents 0.6.3 安装，测试 28 passed | `a958a38` |
| P1 | Part 1 示例 API 偏差修正（HITL `confirmation_before`→`interrupt_on`，但仍需补全官方 interrupt/resume 链路） | `0f4b297` |
| P1 | Part 2 `agent_executor` API 偏差修正（`init_chat_model` 设置温度/令牌、返回值 defensive accessor） | `0f4b297` |
| P1 | Part 1 官方 API 对齐：自定义 subagents、长期 memory、完整 HITL、streaming、event streaming、permissions | `8e685e0`, `21cc93c` |
| P1 | MiniMax OpenAI-compatible 运行环境适配：显式 dotenv、provider profile、消息访问兼容、Windows UTF-8 运行约束 | `bdd7575` |
| P1 | DeepAgents memory backend deprecation 清理：移除 `runtime` 参数和 callable backend factory | `db482b9` |

## Open Questions (回滚成本低的猫猫自决)

- 若最终交付目标仍要求“本地模型”，需补跑 Ollama/vLLM 路径；当前真实运行证据来自 MiniMax OpenAI-compatible runtime
- deepagents `create_deep_agent` vs `DeepAgent` class 的选择
- 意图分类：prompt-based vs 独立 classifier
- `.pytest_tmp` 目录 Windows 权限清理问题（.gitignore 已排除，不影响运行）
