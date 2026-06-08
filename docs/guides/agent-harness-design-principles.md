---
feature_ids: [F004, F005, F006]
topics: [architecture, design-principles, agent-harness, deepagents]
doc_kind: guide
created: 2026-06-03
---

# Agent Harness 设计准则

本文是开发时判断“新能力应该放在哪里”的设计手册。它基于当前税务 Agent 架构讨论，并参考 OpenHands、CrewAI、LangGraph 三类高 star / 高 fork 且近期活跃的 agent harness 项目。

## 1. 核心原则

### 1.1 Harness 居中，但不吞掉所有架构

DeepAgents `create_deep_agent` 是本项目的 Agent Harness 装配点。DeepAgents / LangGraph 提供 planning、tool calling、skills、memory、filesystem、checkpoint 等机制；Harness 决定本项目如何配置、约束和暴露这些机制。

但项目自有稳定抽象不应被强行归入 DeepAgents 原生概念。成熟 agent 项目通常会围绕 harness 建立多个一等边界：

- Agent Harness：模型配置、instructions、tool exposure、context policy、response format 接入方式。
- Business Subsystems：业务证据、引用、确定性分析等项目自有抽象。
- Runtime Adapters：checkpoint、observability、streaming、protocol projection。
- Delivery Surfaces：HTTP、CLI、batch、frontend、cloud 等不同交付形态。

### 1.2 Tool 是接入点，不是业务子系统本体

`find_tax_authorities` 是 DeepAgents tool adapter；`Reference Layer` 不是 tool。

正确边界：

```text
business/references/
  models.py       Citation / ReferenceItem / ReferenceBundle
  providers.py    ReferenceProvider / LocalTaxAuthorityProvider
  manager.py      ReferenceManager
  tools.py        find_tax_authorities，暴露给 DeepAgents
```

判断规则：

- 如果代码表达的是业务领域的稳定概念、可替换 provider、数据模型或治理规则，放入 Business Subsystem。
- 如果代码只是把业务能力包装成 Agent 可调用函数，放入 tool adapter。
- 不要因为 DeepAgents 通过 tool 调用某能力，就把该能力整体降格成 tool 文件。

同理，`TaxAnswer` / `TaxCitation` 是业务输出契约，不是 Agent Harness 本体。Harness 可以把它们作为 `response_format` 接入模型，但 schema 应归入业务答案模型。

### 1.3 Adapter 必须显式，不把外部协议混进核心执行

AG-UI、FastAPI、SSE、Langfuse、SQLite checkpoint 都是 adapter 边界。它们应把 DeepAgents / LangGraph 能力投影成项目稳定契约，而不是让外部协议污染 Agent Harness。

判断规则：

- 对外协议变化时，优先改 adapter，不改 `create_deep_agent` 装配核心。
- DeepAgents / LangGraph 原始事件不直接暴露给产品协议。
- checkpoint、observability 和 streaming 都是运行时能力，不应散落在业务工具里。

### 1.4 Delivery Surface 与核心 Agent 解耦

HTTP `/chat`、HTTP `/chat/stream`、CLI batch、未来 frontend 都是 delivery surface。它们可以共享同一个 Agent Harness，但不应彼此伪装。

判断规则：

- batch 文件处理只放在 delivery/batch 或 batch_io，不进入核心 Agent Harness。
- frontend 交互协议由 AG-UI adapter 承载，不把 UI 状态写进业务 tool。
- CLI 是交付形态，不是业务能力本身。

### 1.5 Deprecated 不是 layer，是隔离区

旧 `legacy/` 目录、旧 `retrieve_tax_context`、旧静态 planner、旧 RAG decorator 已删除；后续不得重新引入 deprecated compatibility 层。

判断规则：

- 新能力不得依赖 deprecated 目录。
- 兼容 wrapper 必须写明替代路径和删除条件。
- 如果兼容代码中仍有主路径需要的函数，应先迁出函数，再删除 wrapper。
- Deprecated 内容不进入 4A 架构图、模块结构或部署拓扑；它只进入清理任务、迁移说明或测试兼容说明。

## 2. 三个开源项目的启发

### 2.1 OpenHands：runtime 和 delivery surface 是一等架构

OpenHands 把 SDK、CLI、Local GUI、Cloud、Enterprise 分开，并把 sandbox runtime、action execution、plugin system、actions / observations 作为核心边界。

对本项目的启发：

- 不要只画 Agent；运行环境、动作执行、交付界面也要进入架构图。
- Runtime adapter 要有明确边界，未来如果引入 sandbox、remote execution 或 frontend session，不应塞进业务工具。
- Delivery surface 可以有多个，但应共享同一套核心 harness 契约。

### 2.2 CrewAI：自治协作和确定性流程控制要分开

CrewAI 同时提供 Crews 和 Flows：前者偏自治多 Agent 协作，后者偏事件驱动流程控制。

对本项目的启发：

- Agent Harness 配置模型可见约束和可供性；batch、附件识别、长任务确认等确定性流程应由 adapter / workflow 承载。
- `Reference Layer`、batch job 这类确定性结构不应伪装成 prompt 技巧。
- 可配置的 agents/tasks/flows 说明项目结构应让“能力编排”和“业务子系统”都可被独立阅读。

### 2.3 LangGraph：stateful execution 是底层坐标系

LangGraph 强调 durable execution、thread id、checkpointer、state history、streaming 和 human-in-the-loop。

对本项目的启发：

- `thread_id`、checkpoint、state/history 是运行时契约，不是普通业务字段。
- 非确定性或有副作用的执行应被清楚包在 runtime 边界中，便于恢复、调试和 replay。
- DeepAgents 是更高层 harness，但底层 stateful workflow 能力来自 LangGraph；项目 adapter 不应重新发明 checkpoint 或状态表。

## 3. 放置新代码的决策表

| 新能力 | 首选位置 | 判断依据 |
|---|---|---|
| 新 Agent 装配参数、system prompt、tool exposure、context policy | `agent/` | 决定模型可见约束和可供性 |
| 新业务回答 schema / artifact contract | `business/answers/` | 属于业务输出契约，可被 harness 作为 `response_format` 引用 |
| 新法规/政策/案例/上传文件引用来源 | `business/references/` | 属于业务证据子系统 |
| 把引用查询暴露给 Agent 调用 | `business/references/tools.py` | 只是 tool adapter |
| 税务意图、术语、场景的确定性分析 | `business/analysis/` | 项目自有分析逻辑 |
| 新 HTTP route / CLI 命令 / batch job | `delivery/` | 交付形态变化 |
| 新 streaming event / 外部交互协议 | `runtime/` 或 `adapters/` | 协议投影和运行时边界 |
| checkpoint / observability / trace 接入 | `runtime/` | 运行时能力适配 |
| 旧接口名兼容 | 清理任务 / 兼容说明 | 不进入目标架构模块 |

## 4. 反模式

- 把所有 Agent 会调用的东西都放进 `tools/`。
- 把 HTTP、SSE、AG-UI 事件混入业务检索代码。
- 为了“看起来原生”重写 DeepAgents / LangGraph 已提供的 checkpoint、memory、streaming 能力。
- 把 batch 文件输入输出放进 Agent Harness。
- 让 deprecated 目录继续承载新功能。
- 只按当前文件夹命名解释架构，不说明扩展依据和删除路径。

## 5. 当前项目采用的四圈结构

```text
Agent Harness
  -> Business Subsystems
  -> Runtime Adapters
  -> Delivery Surfaces
```

这不是一次性目录重构要求，而是开发时的设计坐标系。代码迁移应在有测试保护和 review 后分阶段进行。
