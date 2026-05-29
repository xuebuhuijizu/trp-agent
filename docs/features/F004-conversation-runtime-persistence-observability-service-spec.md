---
feature_ids: [F004]
related_features: [F002, F003]
topics: [deepagents, turns, checkpoint, opengauss, langfuse, fastapi, sse, service]
doc_kind: spec
created: 2026-05-29
---

# F004: 对话运行时、持久化、观测与服务化

> 状态: spec
> 负责人: 宪宪

## 为什么

F003 已经证明税审 Agent 可以输出本地 audit trace，并能把 LangGraph checkpoint 与 `run_id/thread_id` 关联起来。但当前形态仍偏 CLI 演示：一次输入文件，一次批量回答，一次输出报告。

下一阶段必须把它推进为可被应用系统调用的 Agent runtime：

1. 支持多个 turns 组成一个对话，下一轮调用能携带上一轮上下文继续回答。
2. checkpoint 从本地内存/SQLite 升级到本地 OpenGauss，进程重启后仍可通过 `thread_id` 恢复 state，并验证 state history/replay。
3. observability 从本地 JSON trace 切换为 Langfuse，便于查看模型调用、工具调用、latency、error chain 和 trace 详情。
4. 提供 FastAPI 服务入口，让调用方通过 `session_id`、`trace_id`、`thread_id` 调用 `/chat` 和 `/chat/stream`。

## 核心取舍

| 信息类型 | 放在哪里 | 不放在哪里 | 原因 |
|---|---|---|---|
| 当前对话里的用户补充、Agent 追问、上一轮回答 | `messages` | 不塞进 memory | 这是当前 conversation 的短期上下文，应随当前 turn 调用传入。 |
| 跨对话仍然有用的偏好、业务背景、表达风格 | memory | 不塞进每轮 messages | 避免上下文膨胀，并让偏好可复用。 |
| 运行恢复、state history、replay/time travel | checkpoint | 不放入 messages 或 memory | 这是 LangGraph execution state，不是对话文本或长期偏好。 |
| 运行观测、trace、latency、tool calls、错误链 | Langfuse | 不再以本地 JSON trace 作为主路径 | 本地 trace 保留为离线 fallback；Langfuse 是主观测系统。 |

## 讨论结论

本轮围绕多 turns 与旧批处理流程做了四轮收敛：

1. 铲屎官明确 F004 必须向多 turns 让步：用户一次输入、Agent 一次回复是一个 turn，多个 turns 组成一个对话；下一轮要借助前序 `messages`。
2. 砚砚指出当前 `execute_with_evidence(ClassifiedQuestion)` 有三个矛盾：领域分析只看单问题、prompt 不携带历史、`_last_content(messages[-1])` 在多 turn 下可能取错消息。
3. 宪宪判断主路径应改为 `execute_turn(messages, session_id, trace_id, thread_id)`；旧流程可保留，但不能继续支配主执行模型。
4. 砚砚进一步指出“把旧批处理流程包装成 skill”也有矛盾：DeepAgents skill 是 progressive disclosure 指令集，而旧流程是外部确定性管道。最终决策：旧流程保留为显式 batch mode，由 CLI/API 路由选择，不包装成 skill。

因此 F004 的最终结构是：

```text
多 turn 服务主路径:
  POST /chat 或 POST /chat/stream
  -> execute_turn(messages, session_id, trace_id, thread_id)
  -> checkpoint + Langfuse

批处理兼容路径:
  CLI --batch 或 POST /batch
  -> question_extractor -> intent_classifier -> per-question execute_turn
  -> batch report/export
```

两条路径共享底层 Agent、tools、checkpoint、Langfuse 配置，但入口语义不同：`/chat` 是对话，`/batch` 是文档/问题列表处理。

## 能力分类

| 能力 | 分类 | 说明 |
|---|---|---|
| `thread_id` 驱动 checkpoint 保存与恢复 | LangGraph-native | LangGraph checkpointer 以 `thread_id` 作为恢复和历史查询主键。 |
| `get_state` / `get_state_history` / checkpoint replay | LangGraph-native | 用于验证恢复、历史状态和 replay，不重新发明状态存储。 |
| DeepAgents/LangGraph `messages` state | DeepAgents-native | 当前对话上下文通过 messages 输入和 state reducer 累积。 |
| Langfuse callback handler | project adapter | 通过 LangChain/LangGraph callback 接入 Langfuse，把运行事件送到观测系统。 |
| OpenGauss checkpoint backend | project adapter | 基于 OpenGauss 的 PostgreSQL 兼容能力接入 `PostgresSaver`，不自建 checkpoint schema。 |
| FastAPI `/chat` 与 `/chat/stream` | project adapter | 将 Agent 包装为应用系统可调用服务。 |
| FastAPI `/batch` 与 CLI `--batch` | project adapter | 显式承载旧批处理管道，不伪装为 DeepAgents skill。 |
| SSE event projection | project adapter | 把 DeepAgents/LangGraph stream events 映射为稳定服务协议。 |
| 本地 Docker Compose 部署 Langfuse | demo-only scaffolding -> project adapter | 本地演示和低规模部署使用，生产部署不在本 feature 范围内。 |

## 范围内

### 1. Turns 与对话上下文

新增服务层请求模型：

```json
{
  "session_id": "sess-001",
  "trace_id": "trace-001",
  "thread_id": "tax-thread-001",
  "messages": [
    {"role": "user", "content": "请解释视同销售毛利率差异"},
    {"role": "assistant", "content": "需要补充视同销售收入和成本口径。"},
    {"role": "user", "content": "2024 年视同销售收入 50000000，成本 50000001。"}
  ]
}
```

要求：

- `messages` 是当前 conversation 的 turn 历史，服务不把所有知识强行塞入 messages。
- `thread_id` 是 checkpoint 恢复主键，同一个对话继续调用必须稳定传入。
- `session_id` 是应用会话标识，可与 `thread_id` 一对一或一对多，由调用方决定。
- `trace_id` 是外部链路追踪标识，必须传入 Langfuse metadata/tags。
- CLI 仍可保留，但服务路径是 F004 的主路径。
- `execute_with_evidence(ClassifiedQuestion)` 降级为兼容 adapter；新核心接口命名为 `execute_turn(...)`。
- `analyze_tax_question(question.text)` 不再在主路径强制按单问题运行；改为上下文感知的 `analyze_tax_context(messages)` 或等价工具。
- 不再用 `messages[-1]` 判断最终回答；`/chat` 使用 structured response，本轮 assistant output，或 stream adapter 聚合结果。

### 2. OpenGauss checkpoint

将当前 `build_checkpoint_config` 从 `sqlite -> memory fallback` 升级为：

```text
CHECKPOINT_BACKEND=opengauss|sqlite|memory
OPENGAUSS_DSN=postgresql://user:password@localhost:5432/dbname
```

实现要求：

- `opengauss` 使用 `langgraph-checkpoint-postgres` 的 `PostgresSaver` 或 `AsyncPostgresSaver`。
- 启动时执行 checkpointer setup/migration，不在业务请求中临时建表。
- 当 `CHECKPOINT_BACKEND=opengauss` 但连接失败时，服务启动失败；不要静默 fallback 到 memory。
- `sqlite` 和 `memory` 仅用于本地快速测试，不能冒充持久化验收。
- 新增验证脚本或测试：第一次运行写入 checkpoint，重启进程后用同一 `thread_id` 读取最新 state/history，并从指定 checkpoint replay。

### 3. Langfuse observability

F004 将 Langfuse 设为主观测路径：

- 新增 `langfuse` 依赖。
- 通过 `langfuse.langchain.CallbackHandler` 注入 Agent invoke/stream config。
- 每次 `/chat` 和 `/chat/stream` 都把 `session_id`、`trace_id`、`thread_id`、模型名、checkpoint backend 写入 Langfuse metadata/tags。
- 本地 `AuditTraceRecorder` 不再作为主路径；保留为 `LOCAL_AUDIT_TRACE_ENABLED=1` 的离线 fallback。
- 短生命周期 CLI 运行结束时 flush Langfuse client；服务进程由 shutdown hook flush。

本地 Langfuse 部署要求：

- 使用 Docker Compose 本地部署 Langfuse。
- 不把真实 secret 写入 git；只提交 `.env.example` 或部署说明。
- 默认访问地址为 `http://localhost:3000`，与本项目 API 服务端口错开。
- 本地部署命令由铲屎官或明确授权的 runtime 操作者执行；本 feature 代码只提供可复现脚本/说明和健康检查。

### 4. FastAPI 服务化

新增服务入口：

默认端口：**3004**（Cat Cafe public local defaults）。启动命令：`uvicorn app:app --host 0.0.0.0 --port 3004`。

```text
POST /chat
POST /chat/stream
POST /batch
GET  /health
GET  /threads/{thread_id}/state
GET  /threads/{thread_id}/history
```

`POST /chat` 返回最终回复：

```json
{
  "session_id": "sess-001",
  "trace_id": "trace-001",
  "thread_id": "tax-thread-001",
  "answer": "...",
  "citations": [],
  "checkpoint": {
    "backend_type": "opengauss",
    "thread_id": "tax-thread-001"
  },
  "observability": {
    "provider": "langfuse"
  }
}
```

`POST /chat/stream` 返回 SSE：

```text
event: run.started
data: {"session_id":"sess-001","trace_id":"trace-001","thread_id":"tax-thread-001"}

event: agent.message.delta
data: {"text":"..."}

event: tool.started
data: {"name":"retrieve_tax_context"}

event: tool.finished
data: {"name":"retrieve_tax_context","source_ids":["vat-regulation"]}

event: run.finished
data: {"answer":"...","citations":[]}
```

SSE 映射要求：

- 不直接泄露不稳定的内部 Python 对象结构。
- 对外事件名稳定，内部 DeepAgents/LangGraph event schema 变化时只改 adapter。
- stream 结束必须发 `run.finished`；异常必须发 `run.error` 并结束连接。

`POST /batch` 为旧批处理流程的显式服务入口：

```json
{
  "session_id": "sess-batch-001",
  "trace_id": "trace-batch-001",
  "input_file": "sample_input.txt",
  "thread_strategy": "per_question"
}
```

要求：

- `/batch` 使用 `question_extractor`、`intent_classifier`、`output_formatter` 等确定性项目代码。
- 每个问题调用 `execute_turn(...)`，而不是继续调用单问题主路径。
- `thread_strategy` 至少支持 `per_question`；是否支持整份文档共用一个 `thread_id` 后续按演示需要决定。
- `/batch` 可以生成 Markdown/JSON 报告，但不是 `/chat` 的替代品。
- 不新增 `tax-audit-batch-intake` skill；批处理由 API/CLI 路由显式选择。

## 范围外

- 不实现生产级认证、权限、多租户隔离。
- 不把 Langfuse 生产部署、备份、高可用纳入本 feature。
- 不把 OpenGauss 作为业务数据库，只用于 checkpoint。
- 不把所有长期知识塞进 messages。
- 不自建替代 LangGraph checkpoint 的状态表。
- 不自建替代 Langfuse 的观测 UI。
- 不把确定性 batch pipeline 包装成 DeepAgents skill。

## 实施顺序

### Phase 1: 对话契约与 Agent 调用模型

- 新增 request/response schema。
- `AgentExecutor` 支持 `messages` 和外部传入 `thread_id`。
- 新增 `execute_turn(...)` 作为主执行接口。
- 将 `execute_with_evidence(ClassifiedQuestion)` 标记为兼容 adapter 或迁移到 batch 路径。
- 将领域分析改为上下文感知工具，避免只分析当前短句。
- 移除主路径对 `_last_content(messages[-1])` 的依赖。
- CLI 路径复用同一 executor，不再复制 prompt 拼装逻辑。
- 测试覆盖多 turn messages 传入、同一 `thread_id` 稳定使用。

### Phase 2: OpenGauss checkpoint

- 新增 checkpoint backend 配置。
- 接入 `PostgresSaver` / `AsyncPostgresSaver`。
- 新增 setup/health check。
- 验证进程重启后通过 `thread_id` 读取 state/history。
- 验证从历史 checkpoint replay。

### Phase 3: Langfuse observability

- 新增 Langfuse 配置与 callback 注入。
- 将本地 `AuditTraceRecorder` 降级为可选 fallback。
- 新增 Langfuse 本地部署说明和 health check。
- 测试 callback config、metadata/tags、flush 行为。

### Phase 4: FastAPI 服务化与 SSE

- 新增 FastAPI app。
- 实现 `/chat`、`/chat/stream`、`/batch`、`/health`、state/history 查询接口。
- 将 DeepAgents/LangGraph stream events 投影为 SSE 协议。
- 增加接口测试和流式协议测试。
- 增加 batch 路由测试，确保旧批处理流程由路由显式选择，而不是由 skill 触发。

### Phase 5: E2E 验证与演示文档

- 更新 `docs/guides/demo-walkthrough.md`。
- 产出 E2E 验证脚本：
  1. 启动 OpenGauss 与 Langfuse。
  2. 启动 FastAPI 服务。
  3. 第一次 `/chat` 写入 checkpoint。
  4. 重启服务。
  5. 第二次用同一 `thread_id` 继续对话。
  6. 查询 state/history。
  7. 在 Langfuse UI 中看到对应 `trace_id/thread_id`。

## 验收标准

1. [ ] `/chat` 支持 `session_id`、`trace_id`、`thread_id`、`messages` 输入，并返回最终 answer/citations/checkpoint/observability。
2. [ ] `/chat/stream` 能把内部事件转换为稳定 SSE：`run.started`、`agent.message.delta`、`tool.started`、`tool.finished`、`run.finished`、`run.error`。
3. [ ] 多 turn 调用能携带前序 `messages`，下一轮回答能使用当前对话上下文。
4. [ ] 同一 `thread_id` 在 OpenGauss checkpoint 中可恢复最新 state。
5. [ ] 服务重启后，用同一 `thread_id` 能继续对话，而不是重新开始。
6. [ ] 可通过接口或脚本读取 `get_state` 和 `get_state_history` 结果。
7. [ ] 可从历史 checkpoint replay，并记录 replay 触发点。
8. [ ] `CHECKPOINT_BACKEND=opengauss` 连接失败时服务启动失败，不静默 fallback。
9. [ ] Langfuse 本地部署说明可执行，健康检查能确认 UI/API 可达。
10. [ ] 每次 `/chat` 和 `/chat/stream` 都在 Langfuse 中记录 trace，并包含 `session_id`、`trace_id`、`thread_id` metadata/tags。
11. [ ] 本地 JSON trace 不再是默认主路径；只有 `LOCAL_AUDIT_TRACE_ENABLED=1` 时才写入。
12. [ ] `/batch` 保留旧文档/问题列表处理能力，并由 CLI/API 路由显式选择，不包装成 DeepAgents skill。
13. [ ] FastAPI 接口测试、checkpoint 持久化测试、Langfuse callback 配置测试、SSE 协议测试、batch 路由测试全部通过。
14. [ ] 演示文档能指导铲屎官完成本地 OpenGauss + Langfuse + FastAPI E2E 验证。

## 依赖

- `fastapi`
- `uvicorn`
- `langfuse`
- `langgraph-checkpoint-postgres`
- `psycopg` 或 OpenGauss 官方建议的 Python driver
- 本地 OpenGauss 实例
- 本地 Docker 与 Docker Compose（Langfuse）

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| OpenGauss 与 PostgreSQL saver 兼容性不足 | 先做 Spike：用 `PostgresSaver.setup()`、一次 invoke、`get_state_history` 验证；不通过则记录兼容差异，而不是自建 checkpoint。 |
| Langfuse 本地部署依赖较重 | 本地部署作为 demo/低规模路径，提供 health check；生产 HA 不纳入 F004。 |
| messages 被误用成长期知识库 | request schema 和文档明确 messages/memory/checkpoint 边界，测试覆盖多 turn 但不灌入长期偏好。 |
| SSE 暴露内部不稳定事件 | 使用 adapter 投影稳定事件名，不把内部 event 原样透出。 |
| 本地 trace 与 Langfuse 双写造成混乱 | Langfuse 为默认主路径，本地 trace 只在显式开关下启用。 |
| 旧批处理流程被误包装成 skill | batch pipeline 由 CLI/API 路由显式选择；skill 只保留为 Agent 可读指令，不承载外部确定性管道。 |
| runtime 启停影响铲屎官环境 | 启动 OpenGauss/Langfuse/FastAPI 属于 runtime 操作，本 feature 提供脚本和说明，实际启动需铲屎官执行或授权。 |

## 参考资料

- LangGraph Persistence: <https://docs.langchain.com/oss/python/langgraph/persistence>
- LangGraph PostgresSaver: <https://reference.langchain.com/python/langgraph.checkpoint.postgres/PostgresSaver>
- Langfuse Self-hosting: <https://langfuse.com/self-hosting>
- Langfuse Docker Compose: <https://langfuse.com/self-hosting/deployment/docker-compose>
- Langfuse LangChain/LangGraph integration: <https://docs.langchain.com/oss/python/integrations/providers/langfuse>
- OpenGauss Psycopg Based Development: <https://docs.opengauss.org/en/docs/latest/docs/DeveloperGuide/psycopg-based-development.html>

## 开放问题

1. 本机是否已有可用 OpenGauss，还是需要新增本地 Docker/OpenGauss 部署说明？
2. FastAPI 默认端口使用 `3004`（已定，贴合 Cat Cafe public local defaults）。
3. Langfuse project/API key 是手动在 UI 创建，还是需要后续补 headless initialization？
