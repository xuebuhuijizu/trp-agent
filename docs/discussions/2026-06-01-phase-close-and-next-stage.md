---
feature_ids: [F004]
related_features: [F001, F002, F003]
topics: [phase-close, sqlite, checkpoint, streaming, interaction-mode, evidence-provider]
doc_kind: discussion
created: 2026-06-01
---

# F004 当前阶段收口与下一阶段方向

## 结论

当前阶段可以收口。

本阶段已经证明：DeepAgents 税务 PoC 可以作为本地可运行的服务基线存在。`main`、`/chat`、`/chat/stream`、`/batch`、Langfuse 观测、SQLite checkpoint 跨重启恢复都已经跑通；OpenGauss 不再作为当前阶段阻塞项。

下一阶段建议从“能跑通”转向“对外协议稳定、入口语义清晰、边界可替换”。

## 已闭环能力

| 能力 | 状态 | 证据 |
|---|---|---|
| CLI batch `main` | 已跑通 | 早期阶段验证通过 |
| `/chat` | 已跑通 | FastAPI route 测试与人工调用通过 |
| `/chat/stream` | 已跑通 | SSE 返回通过，`stream_adapter.error` 已接入 Langfuse |
| `/batch` | 已跑通 | 正确端口与 payload 返回 `total_questions: 2` |
| Langfuse 观测链路 | 已跑通 | 可见模型调用、工具调用、错误事件 |
| SQLite checkpoint | 已跑通 | `service.sqlite` 基线提交 `0e2cf19`，测试 `75 passed`，人工验证服务重启后可恢复 |
| 官方 examples 参考 | 已整理 | `docs/references/deepagents-official-examples-reference.md` |
| 演进方向整理 | 已整理 | `docs/discussions/2026-06-01-deepagents-evolution-options.md` |

## SQLite 与 OpenGauss 取舍

当前阶段建议把 SQLite 定为 checkpoint 基线。

SQLite 的优点：

- 零服务依赖，部署成本低。
- 一个 `service.sqlite` 文件即可迁移。
- 已经验证跨服务重启恢复。
- 对当前 demo 和内网 PoC 的并发规模足够。

OpenGauss 的价值：

- 多实例共享 checkpoint。
- DBA 级访问控制、审计、备份。
- 更高并发与集中化运维。

当前判断：

```text
SQLite = 当前阶段 project adapter 基线
OpenGauss = 远期 project adapter，可保留方向，但不阻塞当前演进
```

不建议现在继续投入 OpenGauss adapter。原因不是 OpenGauss 没价值，而是当前瓶颈已经转移到服务协议和入口语义。

## 当前阶段遗留项

### 1. 工作区清理策略

当前工作区仍有未跟踪的本地目录和迁移产物，例如：

- `.cat-cafe/`
- `.claude/`
- `.codex/`
- `.gemini/`
- `.kimi/`
- `packages/`
- `chat-stream.json`

这些不影响当前代码状态，但正式交付前需要决定：

- 归档为迁移证据；
- 加入忽略规则；
- 或清理删除。

### 2. 服务重启 E2E 证据归档

铲屎官已经人工验证 SQLite checkpoint 可恢复。若后续需要交付级证据，可以补一份固定脚本或手工记录，包括：

- 第一次 `/chat` 请求；
- 停止并重启服务；
- 第二次同 `thread_id` 请求；
- `/threads/{thread_id}/history` 查询结果。

该项不是当前阶段阻塞项。

## 下一阶段候选方向

### 方向 A：稳定 streaming 协议

目标：把 `/chat/stream` 从“能返回 SSE”升级为“对外语义稳定的进度协议”。

建议事件：

```text
run.started
answer.started
answer.delta
answer.finished
tool.started
tool.finished
skill.started
skill.finished
batch.started
batch.finished
run.finished
run.error
```

不再把 `stage.*` 作为协议层概念。`stage` 太容易承载不可判定的抽象状态，例如 understanding、planning、retrieving；协议层只保留代码能观察到开始/结束的动作域：`run.*`、`answer.*`、`tool.*`、`skill.*`、`batch.*`。

分类：`project adapter`。DeepAgents/LangGraph 仍提供内部 stream events，项目负责投影为稳定产品协议。

优先级：高。

### 方向 B：InteractionMode / ResponseStrategy

目标：明确不同入口和输出形态，不让所有请求都挤在同一个执行策略里。

建议先支持显式模式：

```text
direct_text
progress_stream
answer_stream
structured_final
batch
```

暂不建议立即做自动识别。先让 API/harness 可以明确表达用户意图，再讨论启发式。

分类：`project adapter`。它控制对外输出形态，不是 Agent 内部推理、工具注入或系统提示，所以不应先做进 DeepAgents/LangChain middleware。

优先级：高。

### 方向 C：EvidenceProvider 边界

目标：把 `retrieve_tax_context` 从 demo seed data 里抽出稳定输入输出契约。

建议抽象：

```text
EvidenceProvider
EvidenceBundle
Citation
```

分类：当前实现是 `demo-only scaffolding`，边界应提升为 `project adapter`。

优先级：中。

### 方向 D：Prompt 文件化

目标：把当前 `TAX_SYSTEM_PROMPT` 中的任务流程、工具规则、输出结构和风险边界拆开。

建议等 `InteractionMode` 初步确定后再做，避免把尚未稳定的策略过早文件化。

分类：`project adapter`。

优先级：中到低。

### 方向 E：Subagent / fan-out

目标：处理复杂多问题或多视角判断。

当前不建议进入。batch pipeline 还可以先保持确定性，等出现明确需要并行多视角判断的场景后再引入。

分类：DeepAgents-native 能力可用，但当前项目场景尚未稳定。

优先级：低。

## 推荐下一步

建议下一阶段先讨论并设计：

```text
稳定 streaming 协议 + InteractionMode 显式策略
```

理由：

1. SQLite 已经解决“状态能否恢复”的问题。
2. 当前最容易影响后续产品化的是对外协议，而不是底层存储。
3. streaming 协议和 InteractionMode 可以共同定义“用户看到什么、调用方怎么选择执行形态”。
4. EvidenceProvider、prompt 文件化、think_tool、subagent 都可以排在这个稳定边界之后。

## 讨论问题

1. `/chat/stream` 是否采用 `run.*`、`answer.*`、`tool.*`、`skill.*`、`batch.*` 的稳定事件协议，并明确不使用 `stage.*`？
2. `InteractionMode` 是否先只支持显式参数，不做自动识别？
3. `structured_final` 是否作为最终 artifact，而不是要求每个中间 streaming chunk 都合法 JSON？
4. `/batch` 是否继续保持显式独立入口，而不是包装成 chat 的一种模式？
5. EvidenceProvider 是否作为 streaming 协议 / InteractionMode 之后的下一小步？

## 收敛检查

1. 否决理由 -> ADR：暂不写 ADR；本文仍是阶段收口与下一阶段讨论入口。
2. 踩坑教训 -> lessons：OpenGauss 有长期价值，但在 SQLite 已满足当前基线时继续推进会把注意力从真实瓶颈转移走。
3. 操作规则 -> 指引文件：若下一阶段确定 streaming 协议 / InteractionMode，应更新 runtime guide 和 F004 spec。
