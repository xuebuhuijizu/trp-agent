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

### Part 2 — 税务 Agent

**LLM**：本地模型（Ollama/vLLM），本地起服务，可调外网
**输入**：Word (.docx) 单文件，MB 级
**税务范围**：不限税种，知识来源为模型内置（预留 RAG 装饰器接口）
**意图识别**：三类 — 定义查询 / 税率计算 / 合规判断
**任务规划**：先拆分问题集合，每个问题独立规划；使用默认规划器，预留适配器接口
**输出结构**：Markdown 分节 + JSON 结构化，带引用标注

## Acceptance Criteria

1. [ ] Part 1: 6 个示例脚本全部可运行，验证对应 Deep Agents 原生能力
2. [ ] Part 1: Java 开发者可独立阅读前置知识指南后理解示例
3. [ ] Part 2: 可接受一份 Word 文档并自动提取问题
4. [ ] Part 2: 问题意图分类准确（定义/税率/合规）
5. [ ] Part 2: 每个问题独立规划并执行回答
6. [ ] Part 2: 输出同时包含 Markdown 分节和 JSON 结构化结果
7. [ ] Part 2: 输出含引用标注
8. [ ] Part 2: RAG 装饰器已预留，后期可接入
9. [ ] Part 2: 规划器适配器已预留，后期可替换
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
| LLM | Ollama (local) |
| File parsing | python-docx |
| Output | Markdown + JSON |
| Runtime | Python ≥ 3.11 |

## Open Questions (回滚成本低的猫猫自决)

- 本地模型具体选型（Ollama 拉取的模型名）
- deepagents `create_deep_agent` vs `DeepAgent` class 的选择
- 意图分类：prompt-based vs 独立 classifier
