---
feature_ids: [F004]
related_features: [F001, F002, F003]
topics: [deepagents, streaming, structured-output, batch, langfuse, checkpoint, adapters]
doc_kind: discussion
created: 2026-05-30
---

# Runtime 能力审视与调整空间

## 背景

当前 PoC 已完成 `main`、`/chat`、`/chat/stream`、`/batch` 和 Langfuse 观测的基础验证。继续做迁移交付前，需要先审视当前能力到底证明了什么、哪些能力只是 demo scaffolding、哪些外部交互边界后续最可能变化。

本讨论的目标不是立即重构，而是给下一轮设计和实现建立稳定坐标系。

## 当前共识

### 1. `/chat/stream` 应是阶段式流式协议

当前 `/chat/stream` 已能把 DeepAgents/LangGraph 事件投影成 SSE，但后续对外展示不应只是裸 token streaming。更合适的形态是语义阶段流：

```text
run.started
stage.started: planning
stage.finished: planning
stage.started: tool_call
tool.started
tool.finished
stage.finished: tool_call
stage.started: answering
answer.delta
answer.finished
run.finished
```

内部仍可消费 `astream_events`，但对外协议应表达用户能理解的进展：规划、工具调用、回答生成、完成或错误。

分类：`project adapter`。DeepAgents/LangGraph 提供底层事件，项目负责把它们投影成稳定产品协议。

### 2. structured response 与 streaming 需要决策适配层

structured response 与 streaming 不是绝对冲突，但在同一输出通道里存在张力：

- streaming 适合展示过程、阶段、局部文本。
- structured response 适合作为最终 artifact。
- 难点在于：不能一边承诺 token 级连续输出，一边保证每个中间状态都是合法 JSON/schema。

因此需要引入 `ResponseStrategy` / `InteractionMode` 决策层：

```text
direct_text
structured_answer
stage_stream_then_structured_final
batch_job
diagnostic_trace
```

决策来源应同时支持：

- 自动识别：输入形态、是否有附件、问题复杂度、是否要求报告。
- 人为覆盖：UI/harness 明确指定“流式展示”“结构化报告”“批处理”。

分类：`project adapter`。`response_format=TaxAnswer` 是当前实现策略，不应成为不可替换的核心架构。

### 3. 搜索工具暂时保留 demo 能力，但要抽出边界

当前 `retrieve_tax_context` 可以继续作为 demo 检索工具，但不应与 Agent runtime、输出格式和业务报告强耦合。

建议抽象为：

```text
EvidenceProvider
  input: query / context / intent
  output: EvidenceBundle { citations, source_ids, raw_payload }
```

后续可以替换为本地 RAG、向量库、企业知识库、搜索 API 或人工审核来源，而不影响 `/chat`、`/chat/stream`、`/batch` 的主流程。

分类：当前实现是 `demo-only scaffolding`，接口边界应提升为 `project adapter`。

### 4. `/batch` 应独立成批处理 pipeline

`/batch` 不应伪装成普通 conversation turn。它有独立语义：

- 输入是文件、附件或问题列表。
- 执行时间更长。
- 输出是 Markdown/JSON/report artifact。
- 错误应按问题粒度记录。
- 用户应先确认是否进入批处理。

因此 `/batch` 保留为机器接口是合理的。未来开放交互中，harness 负责识别：

```text
用户上传附件 + 语言提示
  -> 判断是否为批处理意图
  -> 向用户确认
  -> 调用 batch pipeline
  -> 返回报告 artifact
```

分类：`project adapter`。底层可以复用 Agent、tools、checkpoint、Langfuse，但入口语义与 `/chat` 不同。

### 5. Langfuse 足以作为主调试入口

Langfuse 的能力足以支撑当前阶段调试，缺口主要在使用方法和项目层事件接入。

常用场景：

| 场景 | 使用方式 |
|---|---|
| 按一次请求查链路 | 用 `session_id` / `trace_id` / `thread_id` 搜 trace 或 metadata |
| 判断工具是否调用 | 看 observation 中是否有 `retrieve_tax_context` 等 tool span |
| 判断模型是否停在中间态 | 看 model generation output 是否只有“我来检索...”或 reasoning |
| 比较成功和失败 | 同 prompt 使用不同 `trace_id`，对比 tool span、latency、output |
| 查 adapter 错误 | 查看 `stream_adapter.error` 事件及其 metadata |
| 分析性能 | 看每个 observation 的 latency，定位慢在模型、工具还是 batch |
| 做质量回归 | 把典型 trace 沉淀为 dataset/eval 样本 |

分类：Langfuse callback 是 `project adapter`；Langfuse 本地部署仍是 `demo-only scaffolding`，后续可升级为正式运维路径。

### 6. SQLite checkpoint 需要先做跨重启确认

SQLite 本身是文件数据库。只要 DB 文件路径稳定，服务进程停止和重启不会丢失 checkpoint。

但当前实现存在一个重要边界：

```text
build_async_checkpoint_config(...)
  -> output/checkpoints/<tax-run-random-uuid>.sqlite
```

如果服务启动时没有传入稳定 `run_id`，每次进程启动可能创建新的 SQLite 文件。请求里的 `thread_id` 是 LangGraph configurable key，但不决定 SQLite DB 文件名。

因此当前结论是：

```text
SQLite 能支持跨进程恢复；
但当前服务默认配置未必能跨服务重启恢复同一 thread_id，
因为 checkpoint DB 文件路径可能随服务启动变化。
```

建议下一步先把本地 SQLite checkpoint DB 路径稳定为：

```text
output/checkpoints/service.sqlite
```

再验证：

```text
第一次 /chat 写入 thread_id=A
停止服务
重启服务
第二次 /chat 使用同一 thread_id=A
能读取 state/history，并继续对话
```

分类：LangGraph checkpoint 是 `DeepAgents/LangGraph-native`；SQLite/OpenGauss 接入方式是 `project adapter`。

## 外部交互边界

当前最容易变化的部分都在外部交互边界：

- `OutputFormatter`
- `extract_questions`
- `response_format=TaxAnswer`
- FastAPI response shape
- SSE event shape
- batch input/output
- harness attachment handling
- Langfuse project/event 接入

这些不应进入核心业务模型。建议使用 ports/adapters 分层：

```text
核心层：
  ConversationRequest
  ExecutionResult
  EvidenceBundle
  BatchJob / BatchResult
  StageEvent

适配层：
  OutputFormatter
  extract_questions
  TaxAnswer response_format
  FastAPI routes
  SSE projector
  Langfuse recorder
  harness intent detector
```

子代理、middleware、response_format 都可以使用，但应作为可替换策略，而不是项目核心坐标。

## 建议的调整顺序

### Step 1: 固化能力边界文档

本文件作为当前能力审视入口。后续如进入实现，应从这里拆出具体 feature spec。

### Step 2: 先验证 SQLite checkpoint 跨重启

这是最值得优先闭环的能力点。它能回答“当前 state persistence 是否真实可用”，并为 OpenGauss 下一阶段提供基线。

最小实现方向：

- 稳定服务级 SQLite DB 文件路径。
- 用同一 `thread_id` 做服务重启前后 state/history 验证。
- 保留 `CHECKPOINT_BACKEND=memory` 作为测试路径。

### Step 3: 设计 `InteractionMode` / `ResponseStrategy`

先设计，不急于实现完整自动识别。建议从显式参数或 harness 决策开始：

```text
mode=direct_text
mode=stage_stream
mode=structured_final
mode=batch
```

自动识别只作为后续增强，避免过早把不稳定启发式写进核心 runtime。

### Step 4: 抽出 EvidenceProvider 边界

先不升级搜索能力，只把输入输出契约抽出来，降低 `retrieve_tax_context` 对当前 demo 数据的耦合。

### Step 5: 批处理 pipeline 与 harness 确认机制

保留 `/batch`，但未来用户入口应由 harness 识别附件和语言意图，并在长任务开始前确认。

## 暂不建议做的事

- 不建议立刻大重构目录结构。
- 不建议马上把所有能力都做成自动识别。
- 不建议把 batch 包装成 DeepAgents skill。
- 不建议直接跳到 OpenGauss，而不先验证 SQLite 跨重启。
- 不建议把 `TaxAnswer`、`OutputFormatter`、`extract_questions` 当成长期稳定核心。

## 收敛检查

1. 否决理由 -> ADR：暂无正式 ADR；本讨论只形成方向判断。
2. 踩坑教训 -> lessons：SQLite checkpoint 文件路径随机化可能导致跨重启恢复误判，后续验证时应记录为工程教训。
3. 操作规则 -> 指引文件：暂无新增强制规则；后续若实现 `InteractionMode`，再更新运行指南。

