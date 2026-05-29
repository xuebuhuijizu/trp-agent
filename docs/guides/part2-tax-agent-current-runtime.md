---
feature_ids:
  - F004
topics:
  - part2-tax-agent
  - runtime
  - architecture
doc_kind: guide
created: 2026-05-30
---

# Part 2 税务 Agent 当前运行时

这份文档只回答一个问题：**现在主流程到底经过哪些文件，哪些文件不是主流程。**

## 当前有效入口

### 1. CLI 批处理

用途：从 `sample_input.txt` 或指定文件读取多个问题，生成 Markdown / JSON 报告。

```text
main.py
  -> AgentExecutor.create(...)
  -> BatchProcessor.run(...)
  -> question_extractor.extract_questions(...)
  -> IntentClassifier.classify_batch(...)
  -> AgentExecutor.execute_turn(...)
  -> OutputFormatter.write_all(...)
```

关键点：

- CLI batch 是兼容入口，不是对话主入口。
- 每个问题会转成一个 `ConversationRequest`。
- batch 路由显式存在，避免把旧的一问一答流程伪装成 DeepAgents skill。

### 2. HTTP 单轮 / 多轮对话

用途：应用系统调用 Agent，传入 `session_id` / `trace_id` / `thread_id` 和消息历史。

```text
app.py
  -> service_app.create_app(...)
  -> POST /chat
  -> AgentExecutor.execute_turn(...)
  -> DeepAgents ainvoke(...)
```

关键点：

- `messages` 保存当前对话上下文。
- `thread_id` 交给 checkpoint，用于同一条对话的状态恢复。
- 跨对话偏好不塞进 `messages`，应进入 memory。

### 3. HTTP SSE 流式对话

用途：把 DeepAgents 内部事件转换为稳定 SSE 协议。

```text
app.py
  -> service_app.create_app(...)
  -> POST /chat/stream
  -> AgentExecutor.stream_turn(...)
  -> stream_events.normalize_stream_event(...)
  -> sse_protocol.render_sse(...)
```

关键点：

- `/chat/stream` 不调用 `execute_turn`。
- `stream_events.py` 是 DeepAgents 原始事件到服务协议的适配层。
- `sse_protocol.py` 只负责序列化 SSE 文本。

## 文件角色表

| 文件 | 角色 | 是否主路径 | 为什么存在 |
|---|---|---:|---|
| `main.py` | CLI batch 入口 | 是 | 本地演示和离线批量问答入口 |
| `app.py` | ASGI 入口 | 是 | 让 `uvicorn app:app --port 3004` 可直接启动 |
| `tax_agent/service/service_app.py` | FastAPI 路由 | 是 | 暴露 `/chat`、`/chat/stream`、`/batch`、state/history |
| `tax_agent/service/batch_runtime.py` | batch 适配层 | 是 | 把旧批处理流程显式隔离在 `/batch` / CLI |
| `tax_agent/runtime/agent_executor.py` | DeepAgents 执行器 | 是 | 当前唯一的 Agent 调用封装 |
| `tax_agent/runtime/conversation.py` | 请求/响应 schema | 是 | 统一 CLI、HTTP、SSE 的对话数据结构 |
| `tax_agent/runtime/checkpointing.py` | checkpoint 工厂 | 是 | SQLite 优先，memory fallback，OpenGauss 兼容路径保留 |
| `tax_agent/runtime/stream_events.py` | DeepAgents 事件适配 | 是 | 把框架事件归一化为稳定服务事件 |
| `tax_agent/runtime/sse_protocol.py` | SSE 文本协议 | 是 | 保持服务输出协议独立、可测试 |
| `tax_agent/runtime/observability.py` | Langfuse 适配 | 可选 | Langfuse 未启用时 provider 为 `none` |
| `tax_agent/domain/*` | 税务领域匹配和检索 | 是 | 为 tool、batch 分类和上下文分析提供确定性支持 |
| `tax_agent/io/*` | 文件输入和报告输出 | batch 主路径 | 只服务 CLI / `/batch` |
| `tax_agent/runtime/audit_trace.py` | 旧本地 trace recorder | 兼容 | F003 产物，Langfuse 替换前保留，不参与当前主调用 |
| `tax_agent/legacy/*` | 历史实验代码 | 否 | 只保留对比和兼容测试，不应被新主流程引用 |
| `check_sqlite_checkpoint_persistence.py` | 运维验证脚本 | 否 | 验证 SQLite checkpoint 跨进程恢复 |
| `check_opengauss_compat.py` | 运维验证脚本 | 否 | 记录 OpenGauss 与 LangGraph checkpoint 兼容性 |

## 当前代码阅读顺序

如果只想理解主流程，按这个顺序读：

1. `tax_agent/runtime/conversation.py`
2. `tax_agent/runtime/agent_executor.py`
3. `tax_agent/service/service_app.py`
4. `tax_agent/service/batch_runtime.py`
5. `tax_agent/runtime/checkpointing.py`
6. `tax_agent/runtime/stream_events.py`

暂时不要从 `legacy/`、`audit_trace.py` 或测试文件开始读；它们不是当前主路径。

## 后续清理原则

- 新增主路径能力时，优先放进 `runtime/`、`service/`、`domain/`、`io/` 中已有边界。
- 兼容旧流程时，必须明确写在 `batch_runtime.py` 或 `legacy/`，不能混入主对话入口。
- OpenGauss 和 Langfuse 是增强项；SQLite checkpoint 和 `observability=none` 是当前可运行基线。
- 如果一个文件无法回答“谁调用我、为什么存在”，需要补文件头或移动目录。
