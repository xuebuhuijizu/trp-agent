---
feature_ids: [F006]
related_features: [F004, F005]
topics: [ag-ui, interaction-protocol, streaming, tax-agent]
doc_kind: spec
created: 2026-06-03
---

# F006: AG-UI Interaction Protocol

> Status: review | Owner: 宪宪

## Why

F004 已经证明税务 Agent 可以通过 `/chat` 和 `/chat/stream` 对外服务，F005 已经把法规/政策等外部引用材料纳入 Reference Layer。但当前产品形态仍是“后端输出文本”，没有真正的前端交互协议。继续讨论 `TaxAnswer artifact` 或报告渲染前，必须先确定 Agent 与前端如何通信。

铲屎官在讨论中指出：当前产品仅文本输出且无前端交互，脱离输出形式讨论结构化产物意义不足。因此 F006 将 AG-UI 确认为下一阶段对外 streaming 协议，让 Agent 的文本、工具调用、引用来源、最终结果都能被前端实时消费。

## What

F006 建立 AG-UI 作为税务 Agent 的唯一对外 streaming 协议：

- 不再维护项目私有 streaming event 作为长期对外协议。
- 将 DeepAgents / LangChain raw events 直接归一化为 AG-UI 标准事件。
- `/chat/stream` 输出 AG-UI SSE。
- `/chat` 非流式 JSON 保留为同步 API，但最终结构应与 AG-UI `RUN_FINISHED.result` 对齐。
- `find_tax_authorities` 的工具调用和 citation 通过 AG-UI tool events 暴露。
- 未来 `TaxAnswerArtifact` 放入 `RUN_FINISHED.result`，不单独创建另一套最终输出协议。

## Architecture Decisions

### AG-UI 是对外协议，不是中间适配层

F006 不采用“两套事件定义”：

```text
DeepAgents raw events -> project private events -> AG-UI events -> SSE
```

改为：

```text
DeepAgents raw events -> AG-UI events -> SSE
```

原因是当前没有前端消费者，也没有外部 client 依赖旧的 `run.started` / `answer.delta` / `tool.finished` 私有事件。维护两套事件定义只会增加测试、文档和语义漂移成本。

### 保留 `/chat`，AG-UI 负责 streaming interaction

`/chat` 是同步 API，继续返回 JSON；AG-UI 负责流式交互协议。两者都应指向同一类最终业务产物：

```text
/chat.artifact == RUN_FINISHED.result
```

第一版可以只保证字段方向一致，不强行实现完整 `TaxAnswerArtifact` 扩展。

### 事件 ID 必须稳定

AG-UI 事件需要稳定关联：

```text
runId
threadId
messageId
toolCallId
```

当前项目已有 `session_id`、`trace_id`、`thread_id`，但缺少 `runId`、`messageId` 和 `toolCallId`。F006 第一版必须定义生成规则，确保前端能把文本片段、工具调用和最终结果拼回同一次 run。

### Tool result 暴露 citation，不暴露调试 dump

`find_tax_authorities` 的 `TOOL_CALL_RESULT` 应包含前端可消费的信息：

```text
toolName
sourceIds
citations
summary
```

不把完整 `ReferenceBundle` 原样塞给前端。`ReferenceBundle` 是检索过程产物，前端第一版需要的是引用来源和可展示摘要。

### 第一版不上完整共享状态

AG-UI 支持 state snapshot / delta，但 F006 第一版只建立 protocol baseline。暂缓：

- `STATE_SNAPSHOT`
- `STATE_DELTA`
- frontend tool calls
- human-in-the-loop
- cancel API
- tool args delta

这些能力等有前端界面和明确交互需求后再引入。

## Event Mapping

F006 第一版目标事件：

```text
RUN_STARTED
TEXT_MESSAGE_START
TEXT_MESSAGE_CONTENT
TEXT_MESSAGE_END
TOOL_CALL_START
TOOL_CALL_ARGS
TOOL_CALL_END
TOOL_CALL_RESULT
RUN_FINISHED
RUN_ERROR
```

当前内部语义到 AG-UI 的等价关系：

| 当前语义 | AG-UI event | 说明 |
|---|---|---|
| run start | `RUN_STARTED` | 包含 `runId`、`threadId` |
| assistant text start | `TEXT_MESSAGE_START` | 创建 assistant `messageId` |
| assistant text delta | `TEXT_MESSAGE_CONTENT` | 按 `messageId` 追加内容 |
| assistant text end | `TEXT_MESSAGE_END` | 结束该 assistant message |
| tool start | `TOOL_CALL_START` | 创建 `toolCallId` |
| tool input | `TOOL_CALL_ARGS` | 第一版可一次性发完整 args |
| tool end | `TOOL_CALL_END` | 标记工具调用结束 |
| tool output | `TOOL_CALL_RESULT` | 带 citations / sourceIds |
| final artifact | `RUN_FINISHED.result` | 放置最终 TaxAnswer 方向产物 |
| error | `RUN_ERROR` | 不泄漏内部堆栈 |

## Acceptance Criteria

- [x] AC-1: `/chat/stream` 输出 AG-UI 标准事件，不再输出项目私有 `run.started` / `answer.delta` 等事件名。
- [x] AC-2: AG-UI 事件包含稳定的 `runId`、`threadId`、`messageId`、`toolCallId` 关联字段。
- [x] AC-3: assistant 文本通过 `TEXT_MESSAGE_START` / `TEXT_MESSAGE_CONTENT` / `TEXT_MESSAGE_END` 输出，前端可按 `messageId` 拼装完整回答。
- [x] AC-4: `find_tax_authorities` 工具调用通过 `TOOL_CALL_START` / `TOOL_CALL_ARGS` / `TOOL_CALL_END` / `TOOL_CALL_RESULT` 输出。
- [x] AC-5: `TOOL_CALL_RESULT` 能暴露 `sourceIds` 和标准 `citations`，不依赖旧私有 payload。
- [x] AC-6: `RUN_FINISHED.result` 存在，并能承载当前轻量 `TaxAnswer` artifact。
- [x] AC-7: `RUN_ERROR` 对模型无输出、工具失败、协议适配失败给出可区分错误类型，不泄漏内部堆栈。
- [x] AC-8: `/chat` 非流式 API 保持可用，不因 AG-UI streaming 改造破坏现有调用。
- [x] AC-9: 测试覆盖事件顺序、ID 关联、tool citation、final result 和 error event。

## Dependencies

- **Evolved from**: F004。F004 提供 conversation runtime、`/chat`、`/chat/stream`、SSE 基线和 `InteractionMode`。
- **Related**: F005。F005 提供 Reference Layer 和 citation 稳定字段，F006 负责把这些引用结果以交互协议暴露。
- **Related**: F002。F002 的 `TaxAnswer` structured output 是 `RUN_FINISHED.result` 的第一版业务产物来源。

## Risk

| 风险 | 缓解 |
|---|---|
| 把 AG-UI 当成前端实现，而不是协议 | F006 只做后端协议和测试，不做 UI。 |
| 一次性引入 state、cancel、human-in-the-loop 导致范围失控 | 第一版只做文本、工具、结果、错误四类核心事件。 |
| 旧 F004 测试仍绑定项目私有事件名 | TDD 更新测试，让旧事件名退出对外契约。 |
| `TOOL_CALL_RESULT` 暴露过多内部数据 | 只暴露 `sourceIds`、`citations` 和摘要，不输出完整 `ReferenceBundle` dump。 |
| `/chat` 与 streaming final result 分叉 | 约定 `/chat.artifact` 与 `RUN_FINISHED.result` 指向同一类业务产物。 |

## Open Questions

| # | 问题 | 状态 |
|---|---|---|
| OQ-1 | `/chat/stream` 直接切换 AG-UI，还是新增 `/chat/agui/stream` 过渡？ | 已决策：直接切换 `/chat/stream` |
| OQ-2 | 第一版 `runId` 是否直接复用 `trace_id`，还是每次请求生成独立 ID？ | 已决策：第一版复用 `trace_id` |
| OQ-3 | `TOOL_CALL_ARGS` 是否需要脱敏策略第一版即落地？ | 已决策：第一版不做通用脱敏，仅暴露当前安全的 `find_tax_authorities` query |

## Key Decisions

| # | 决策 | 理由 | 日期 |
|---|---|---|---|
| KD-1 | AG-UI 作为唯一对外 streaming 协议 | 当前没有前端或外部 client 依赖旧私有事件，双协议维护收益不足。 | 2026-06-03 |
| KD-2 | 不保留项目私有 event 作为长期中间层 | 避免 `DeepAgents raw -> private -> AG-UI` 的语义漂移和测试负担。 | 2026-06-03 |
| KD-3 | 第一版不上完整 AG-UI state 能力 | 先建立文本、工具、结果、错误的协议基座，等前端需求明确后再扩展。 | 2026-06-03 |

## Timeline

| 日期 | 事件 |
|---|---|
| 2026-06-03 | 铲屎官确认下一阶段先讨论并落地 AG-UI 交互协议。 |
| 2026-06-03 | 第一版实现完成，`/chat/stream` 切换为 AG-UI SSE，主项目测试 `84 passed`。 |

## Review Gate

- Phase A: 实现前请跨猫 review 事件 schema、ID 规则和测试 AC，避免把 AG-UI 做成又一层项目私有协议。

## Links

| 类型 | 路径 | 说明 |
|---|---|---|
| Feature | `docs/features/F004-conversation-runtime-persistence-observability-service-spec.md` | 当前 conversation runtime 和 streaming 基线 |
| Feature | `docs/features/F005-reference-layer-spec.md` | Reference Layer 和 citation 字段来源 |
| Official | `https://docs.ag-ui.com/introduction` | AG-UI 官方介绍 |
| Official | `https://docs.ag-ui.com/concepts/architecture` | AG-UI 架构与 transport |
| Official | `https://docs.ag-ui.com/sdk/js/core/events` | AG-UI event 类型 |
