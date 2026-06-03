---
feature_ids:
  - F004
  - F005
  - F006
topics:
  - part2-tax-agent
  - runtime
  - architecture
doc_kind: guide
created: 2026-05-30
updated: 2026-06-03
---

# Part 2 税务 Agent 当前运行时

这份文档只回答一个问题：**现在主流程到底经过哪些文件，哪些文件不是主流程。**

目标架构和设计准则见：

- [项目 4A 架构文档](../architecture/4a-architecture.md)
- [Agent Harness 设计准则](agent-harness-design-principles.md)

## 当前有效入口

### 1. CLI 批处理

```text
main.py
  -> delivery/batch.BatchProcessor.run(...)
  -> delivery/batch_io/question_extractor.extract_questions(...)
  -> business/analysis/IntentClassifier.classify_batch(...)
  -> runtime/executor.AgentExecutor.execute_turn(...)
  -> delivery/batch_io/OutputFormatter.write_all(...)
```

关键点：

- CLI batch 是交付形态，不是 Agent Harness 本体。
- 每个问题会转成一个 `ConversationRequest`。
- batch 文件输入输出只在 `delivery/batch_io/`，不进入核心 Agent 装配。

### 2. HTTP 单轮 / 多轮对话

```text
app.py
  -> delivery/http_api.create_app(...)
  -> POST /chat
  -> runtime/executor.AgentExecutor.execute_turn(...)
  -> DeepAgents ainvoke(...)
```

关键点：

- `messages` 保存当前对话上下文。
- `thread_id` 交给 LangGraph checkpoint，用于同一条对话的状态恢复。
- `/chat` 返回同步 JSON，业务产物与 AG-UI `RUN_FINISHED.result` 对齐。

### 3. HTTP SSE 流式对话

```text
app.py
  -> delivery/http_api.create_app(...)
  -> POST /chat/stream
  -> runtime/executor.AgentExecutor.stream_turn(...)
  -> runtime/ag_ui.normalize_ag_ui_event(...)
  -> runtime/sse.render_sse(...)
```

关键点：

- `/chat/stream` 不调用 `execute_turn`。
- `/chat/stream` 对外只输出 AG-UI SSE，不再维护项目私有 streaming event。
- `runtime/ag_ui.py` 负责从 DeepAgents / LangGraph raw events 投影到 AG-UI。

## 文件角色表

| 文件 | 角色 | 是否主路径 | 为什么存在 |
|---|---|---:|---|
| `main.py` | CLI thin entrypoint | 是 | 本地演示和离线批量问答入口 |
| `app.py` | ASGI thin entrypoint | 是 | 让 `uvicorn app:app --port 3004` 可直接启动 |
| `tax_agent/agent/graph.py` | Agent Harness 装配 | 是 | 调用 `create_deep_agent(...)` |
| `tax_agent/agent/instructions.py` | 模型行为约束 | 是 | system prompt / behavior constraints |
| `tax_agent/agent/tool_manifest.py` | tool exposure | 是 | 控制暴露给模型的 tool 清单 |
| `tax_agent/agent/context_policy.py` | context policy | 是 | skills / memory / filesystem 暴露策略 |
| `tax_agent/business/answers/models.py` | 业务输出契约 | 是 | `TaxAnswer` / `TaxCitation` / artifact contract |
| `tax_agent/business/references/*` | Reference Layer | 是 | 引用来源、provider、manager、tool adapter |
| `tax_agent/business/analysis/*` | 确定性分析 | 是 | 意图分类、税务上下文分析 |
| `tax_agent/runtime/executor.py` | Runtime executor | 是 | `execute_turn` / `stream_turn` 主编排 |
| `tax_agent/runtime/conversation.py` | 请求/响应 schema | 是 | 统一 HTTP、SSE、batch 的对话数据结构 |
| `tax_agent/runtime/checkpointing.py` | checkpoint 工厂 | 是 | SQLite / memory / OpenGauss 配置 |
| `tax_agent/runtime/ag_ui.py` | AG-UI 协议适配 | 是 | 管理 `runId` / `messageId` / `toolCallId` |
| `tax_agent/runtime/sse.py` | SSE 文本协议 | 是 | 保持 SSE 渲染独立、可测试 |
| `tax_agent/runtime/observability.py` | Langfuse 适配 | 可选 | Langfuse 未启用时 provider 为 `none` |
| `tax_agent/delivery/http_api.py` | FastAPI routes | 是 | 暴露 `/chat`、`/chat/stream`、`/batch`、state/history |
| `tax_agent/delivery/batch.py` | batch 编排 | 是 | 文件批处理 route / CLI 共用 |
| `tax_agent/delivery/batch_io/*` | batch 输入输出 | batch 主路径 | txt/docx 解析、Markdown/JSON 报告 |
| `tax_agent/legacy/*` | 历史实验代码 | 否 | 只保留兼容测试和对照材料 |

注意：`domain/`、`service/`、`io/` 目录已移除（提交 `aa2ef04`），其能力已全部迁至 `business/` 和 `delivery/`。

## 当前代码阅读顺序

如果只想理解主流程，按这个顺序读：

1. `tax_agent/agent/graph.py`
2. `tax_agent/agent/instructions.py`
3. `tax_agent/agent/tool_manifest.py`
4. `tax_agent/business/answers/models.py`
5. `tax_agent/business/references/tools.py`
6. `tax_agent/runtime/executor.py`
7. `tax_agent/delivery/http_api.py`
8. `tax_agent/delivery/batch.py`

暂时不要从 `legacy/` 或测试文件开始读；它们不是当前主路径。

## 后续清理原则

- 新增主路径能力时，优先放进 `agent/`、`business/`、`runtime/`、`delivery/` 四个边界。
- 旧 `InteractionMode` / `response_strategy.py` 属于清理清单，不进入新架构。
- `retrieve_tax_context` 只作为旧 tool 名兼容，不是新主路径。
- 如果一个文件无法回答“谁调用我、为什么存在”，需要补文件头或移动目录。

## Reference Layer 阅读补充

F005 之后，法规/政策等外部引用材料的主路径是 `tax_agent/business/references/`。

新人阅读顺序建议：

1. 先读 `tax_agent/business/references/models.py`，理解 `ReferenceBundle`、`ReferenceItem` 和 `Citation`。
2. 再读 `tax_agent/business/references/providers.py` 和 `manager.py`，看 provider 如何接入。
3. 再读 `tax_agent/business/references/tools.py`，看 `find_tax_authorities` 如何作为 DeepAgents tool adapter 暴露。
4. 最后读 `tax_agent/runtime/ag_ui.py`，看 tool output 如何进入 `TOOL_CALL_RESULT` 和 `RUN_FINISHED.result`。
