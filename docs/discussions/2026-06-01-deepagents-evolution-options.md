---
feature_ids: [F004]
related_features: [F001, F002, F003]
topics: [deepagents, evolution, architecture, streaming, checkpoint, langfuse, batch, adapters]
doc_kind: discussion
created: 2026-06-01
---

# DeepAgents PoC 演进方向整理

## 目的

本文把两份材料合并成一份讨论入口：

- `docs/references/deepagents-official-examples-reference.md`：官方 examples 的模式与可借鉴特性。
- `docs/discussions/2026-05-30-runtime-capability-review.md`：当前 runtime 能力审视与调整空间。

目标不是立即确定实现计划，而是把“可以吸纳什么”“当前项目该先稳什么”“哪些能力暂时不要碰”放到同一个坐标系里。

## 当前基线

当前 PoC 已验证：

- `main` 可以运行并输出。
- `/chat` 可以正常返回。
- `/chat/stream` 可以通过 SSE 返回，并已补 `stream_adapter.error` 到 Langfuse。
- `/batch` 已独立为接口并跑通。
- Langfuse 可按 `session_id` / `trace_id` / `thread_id` 查看模型和工具链路。

当前还未完全闭环：

- SQLite checkpoint 已稳定服务级 DB 路径为 `output/checkpoints/service.sqlite`，并通过脚本验证 SQLite checkpointer 关闭后重开仍能读取 state/history；真实 `/chat` 服务重启 E2E 尚待 runtime 启停授权。
- `/chat/stream` 还只是稳定 SSE 映射，尚未升级为清晰的阶段式流式协议。
- `OutputFormatter`、`extract_questions`、`response_format=TaxAnswer` 等外部交互边界还没有显式 adapter 分层。
- OpenGauss checkpoint 是下一阶段可选项，不应跳过 SQLite 基线直接进入。

## 能力分类

| 能力/模式 | 来源 | 分类 | 当前判断 |
|---|---|---|---|
| `messages` state / `thread_id` checkpoint | DeepAgents / LangGraph | DeepAgents/LangGraph-native | 保留为核心能力 |
| `astream_events` / stream events | DeepAgents / LangGraph | DeepAgents/LangGraph-native | 作为内部事件源，不直接暴露给产品协议 |
| Langfuse callback | LangChain / Langfuse | project adapter | 保留为主观测入口 |
| `/chat` / `/chat/stream` / `/batch` | 当前项目 | project adapter | 保留，但需要更清晰的入口语义 |
| SSE 阶段式协议 | 当前项目规划 | project adapter | 建议下一阶段设计 |
| `retrieve_tax_context` 本地税务检索 | 当前项目 | demo-only scaffolding -> project adapter | 先抽 EvidenceProvider 边界，不急着升级检索能力 |
| `TaxAnswer` structured response | 当前项目 | project adapter | 保留为一种策略，不作为唯一输出形态 |
| `OutputFormatter` / `extract_questions` | 当前项目 | project adapter | 明确为可替换外部交互边界 |
| Langfuse 本地部署 | 当前项目 | demo-only scaffolding | 可继续用于 demo，不纳入生产 HA |
| OpenGauss checkpoint | 当前项目规划 | project adapter | SQLite 跨重启验证后再进入 |

## 官方示例可吸纳特性

### 1. Prompt 管理

官方 examples 中最值得吸纳的是 prompt 分层和文件化：

- `deep_research`：workflow / delegation / researcher 分层 prompt。
- `content-builder-agent`：`AGENTS.md` + `skills/*/SKILL.md` + subagent 配置。
- 多个示例使用模板变量注入运行时参数。

当前项目的差距：

- `TAX_SYSTEM_PROMPT` 仍是单层字符串。
- runtime 规则、工具调用策略、输出要求混在同一个 prompt 中。
- prompt 没有按“任务流程 / 工具规则 / 输出结构 / 风险边界”拆开。

建议：

```text
prompts/
  tax_system.md
  stream_stage_policy.md
  structured_answer_policy.md
  batch_policy.md
```

优先级：中。应在 `InteractionMode` 设计后再拆，避免先把不稳定策略文件化。

### 2. `think_tool` / 反思阶段

`deep_research` 的 `think_tool` 值得参考：它不是外部检索工具，而是让模型在检索之间暂停，自检“依据是否足够、还缺什么”。

适合当前项目的场景：

- 检索到法规后，判断证据是否覆盖问题。
- 对复杂税务判断，先列判断步骤，再回答。
- 在多问题 batch 中，对每个问题生成“证据充分性”标记。

风险：

- 容易增加 token 和延迟。
- 如果没有阶段式协议，对用户不可见，会显得系统变慢。

建议：

只在 `progress_stream`、`answer_stream` 或复杂问题模式中启用，并投影为可观察的 `tool.*` / `answer.*` / 项目层事件；不要新增抽象 `stage.*` 协议，也不要默认塞进所有请求。

优先级：中。

### 3. Subagent 外化与 fan-out

官方示例里有两类可借鉴模式：

- `content-builder-agent`：subagent YAML 外化。
- `deep_research` / `rlm_agent`：并行 fan-out 或 PTC 链式 subagent。

当前项目判断：

- 现在还没有必须引入 subagent 的稳定场景。
- batch 多问题处理更适合先做确定性 pipeline，而不是马上用 subagent。
- 如果后续出现“同一税务问题需要多个视角并行判断”，再引入 subagent。

建议：

暂不实现 subagent fan-out。若未来引入，直接采用配置外化：

```text
subagents.yaml
load_subagents()
```

优先级：低到中。

### 4. 文件系统持久化与每轮新 context

`ralph_mode` 的价值在于：长任务中用文件系统保存中间结果，避免 context 无限膨胀。

当前项目可借鉴的点：

- batch 输出中间 artifact。
- 长分析任务把 evidence、draft、final 分文件保存。
- checkpoint 只负责 execution state，不承担报告 artifact 管理。

前置条件：

- 先验证 SQLite checkpoint 跨服务重启。
- 明确 output artifact 目录和命名规则。

优先级：中，但晚于 SQLite 基线。

### 5. 部署配置

官方示例中的 `langgraph.json`、`deepagents.toml`、`.env.example` 对后续正式部署有参考价值。

当前判断：

- demo 阶段不需要完整部署形态。
- 迁移交付时需要 `.env.example` 和运行指南。
- 真正服务化时再考虑 `langgraph.json` / `deepagents.toml`。

优先级：低。

### 6. 暂不吸纳

以下模式当前不建议吸纳：

- Supabase auth / per-user auth：demo 阶段不需要用户体系。
- GPU / NVIDIA / RAPIDS：与税务场景无关。
- TypeScript / QuickJS / repl_swarm：当前没有 JS 执行需求。
- coding sandbox：税务场景不需要远程代码执行。
- 完整 deployable service 模板：当前服务边界还在审视中。

## 与当前演进方向的合并

### 方向 A：先稳 checkpoint

问题：

SQLite 是数据库；如果服务默认 DB 文件名随进程启动变化，跨服务重启恢复会被误判。

建议：

- 服务级 SQLite DB 路径已经稳定为 `output/checkpoints/service.sqlite`。
- 同一 `thread_id` 做重启前后 `/chat` 验证。
- 验证 `/threads/{thread_id}/state` 和 `/threads/{thread_id}/history`。

收益：

- 明确 SQLite 是否足以作为本地和内网部署基线。
- 为 OpenGauss 提供对照组。

优先级：高。

### 方向 B：稳定 streaming 协议

问题：

当前 `/chat/stream` 可用，但对外仍偏事件转发，需要稳定的产品协议。

建议：

- 不新增 `StageEvent` 抽象。
- 将内部 LangGraph events 映射到可观察动作域：
  - `run.started` / `run.finished` / `run.error`
  - `answer.started` / `answer.delta` / `answer.finished`
  - `tool.started` / `tool.finished` / `tool.error`
  - 后续需要时扩展 `skill.*`、`batch.*`
- `answer.delta` 只表达回答文本增量，不承载“正在理解/正在规划”这类不可判定状态。

收益：

- 用户能看懂系统进展。
- 后续 `think_tool`、batch 长任务、tool latency 都有展示位置。

优先级：高。

### 方向 C：ResponseStrategy / InteractionMode

问题：

structured response 和 streaming 都需要，但不能用一个固定路径覆盖所有问题。

建议：

先设计显式策略，不急于自动识别：

```text
mode=direct_text
mode=progress_stream
mode=answer_stream
mode=structured_final
mode=batch
```

后续再加入自动识别：

- 是否有附件。
- 是否要求报告。
- 是否是复杂税务判断。
- 是否需要实时展示。

收益：

- 避免把不稳定启发式写进核心 runtime。
- 让 UI/harness 和 API 都能明确表达用户意图。

优先级：高。

### 方向 D：批处理 pipeline + harness 确认

问题：

`/batch` 已作为接口存在，但未来真实入口不应让用户手动调接口，而应由 harness 根据附件和语言提示识别。

建议：

```text
附件/文件 + 用户提示
  -> harness 识别 batch intent
  -> 向用户确认
  -> 创建 batch job
  -> 调用 batch pipeline
  -> 返回 report artifact
```

收益：

- 保留 `/batch` 的确定性和可测性。
- 不把批处理伪装成普通 chat。

优先级：中。

### 方向 E：EvidenceProvider 边界

问题：

当前检索工具是 demo seed data，不应成为长期耦合点。

建议：

抽象：

```text
EvidenceProvider
EvidenceBundle
Citation
```

`retrieve_tax_context` 变成 provider 的一个实现。

收益：

- 后续换 RAG、企业知识库、MCP 文档源时影响面小。

优先级：中。

### 方向 F：Prompt 文件化

问题：

当前 prompt 与 runtime 逻辑混合，后续策略变化会增加代码修改成本。

建议：

在 `InteractionMode` 初步确定后，再拆 prompt 文件。不要现在直接拆，否则会把未稳定的策略固化到文件层。

收益：

- 降低 prompt 调整成本。
- 便于对照官方示例的 prompt 分层。

优先级：中到低。

## 推荐路线

### 近期讨论顺序

1. SQLite checkpoint 跨重启是否作为下一轮实现目标。
2. `/chat/stream` 稳定事件 contract。
3. `InteractionMode` 的最小枚举和 API/harness 表达方式。
4. batch 是否从同步接口升级为 job 语义。
5. EvidenceProvider 和 prompt 文件化是否进入同一轮，还是分开做。

### 近期实现顺序

若要进入实现，建议按以下顺序：

```text
1. 稳定 SQLite checkpoint DB 路径 + 跨重启验证
2. 稳定 SSE contract
3. InteractionMode 显式参数
4. batch job/harness 确认草案
5. EvidenceProvider 抽边界
6. prompt 文件化
7. think_tool / reflection 事件投影
8. subagent YAML / fan-out
```

## 关键取舍

| 取舍 | 建议 |
|---|---|
| 先做 OpenGauss 还是 SQLite | 先 SQLite，证明 checkpoint 语义，再迁移 OpenGauss |
| 先做自动识别还是显式 mode | 先显式 mode，再自动识别 |
| 先做 subagent 还是 batch pipeline | 先 batch pipeline，subagent 等复杂场景稳定后再引入 |
| 先拆 prompt 还是先定策略 | 先定 `InteractionMode`，再拆 prompt |
| 先升级检索还是抽 EvidenceProvider | 先抽边界，不急着升级检索 |
| Langfuse 是否够用 | 够用，当前需要补调试手册和项目层事件 |

## 讨论问题

1. 下一轮是否先做 SQLite checkpoint 跨重启验证？
2. `/chat/stream` 对外事件是否采用 `run.*`、`answer.*`、`tool.*`、`skill.*`、`batch.*`，并明确不使用 `stage.*`？
3. `InteractionMode` 是否先只做显式参数，不做自动识别？
4. batch 是否需要从同步接口升级为异步 job？
5. EvidenceProvider 是否作为独立小步，而不是和 RAG 升级绑定？
6. prompt 文件化是否等 `InteractionMode` 稳定后再做？

## 收敛检查

1. 否决理由 -> ADR：暂不写 ADR；本文仍是讨论整理，不是最终架构决策。
2. 踩坑教训 -> lessons：官方示例的业务场景不能直接迁移，必须按架构层拆解后再吸纳。
3. 操作规则 -> 指引文件：暂无新增强制规则；若确定 `InteractionMode`，后续应更新运行指南。
