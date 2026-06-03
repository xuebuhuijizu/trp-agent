---
feature_ids: [F001, F002, F003, F004, F005, F006]
topics: [architecture, 4a, deepagents, tax-agent]
doc_kind: guide
created: 2026-06-03
---

# 项目 4A 架构文档

## 1. 业务架构 (Business Architecture)

### 1.1 业务域

```text
税务智能问答 Agent
├── 税审问题处理        核心：接收税审问题，生成结构化回答
│   ├── 单问题即时回答    /chat, /chat/stream
│   └── 批量文档处理     /batch, CLI main.py
├── 证据引用管理        核心：法规依据检索与结构化引用
│   └── Reference Layer  可扩展的引用提供者接口
├── 审计追溯            核心：运行过程可记录、可复现
│   ├── Langfuse observability 观测平台（主观测）
│   └── LangGraph checkpoint state 持久化
└── 交互协议            核心：标准化的前端交互事件
    └── AG-UI protocol  对外唯一 streaming 协议
```

### 1.2 用户角色

| 角色 | 使用方式 | 场景 |
|------|---------|------|
| 税审人员 | CLI / 服务 API | 批量处理税审报告 |
| 应用系统 | HTTP API | 集成 Agent 能力到工作流 |
| 前端用户 | AG-UI 协议 | 未来实时交互式税务问答 |

---

## 2. 应用架构 (Application Architecture)

### 2.1 架构设计原则

本项目的架构以 Agent Harness 为中心，但这里的 Harness 不是 DeepAgents 原生能力集合，而是**项目对模型的约束与可供性设计层**。DeepAgents / LangGraph 提供 planning、tool calling、skills、memory、filesystem、checkpoint 等机制；Harness 决定本项目如何配置、约束和暴露这些机制。

参考 OpenHands、CrewAI、LangGraph 等明星项目，成熟 agent 项目会围绕 harness 建立多个一等边界：

- **Agent Harness**：项目对模型的 instructions、tool exposure、context policy、response format 接入方式的约束设计。
- **Business Subsystems**：项目自有的稳定抽象，如引用/证据体系、确定性分析逻辑。
- **Runtime Adapters**：将 DeepAgents/LangGraph 能力适配到项目执行环境。
- **Delivery Surfaces**：不同形态的交付接口（HTTP、CLI、batch、前端）。

这些边界通过**显式 adapter** 连接，而不是全部揉进 tool 或 middleware。

开发时的具体设计准则见：[Agent Harness 设计准则](../guides/agent-harness-design-principles.md)。

### 2.2 模块结构

目标模块结构必须和四个架构层级一一对应。`app.py` 和 `main.py` 只保留为仓库根部的薄启动脚本，调用 `tax_agent.delivery`，不再作为应用架构层级。

```text
part2-tax-agent/
├── app.py                         # 薄入口：uvicorn app:app --port 3004
├── main.py                        # 薄入口：CLI batch
└── tax_agent/
    ├── agent/                     # 1. Agent Harness
    │   ├── graph.py               # build_tax_agent(): create_deep_agent(...)
    │   ├── instructions.py        # system prompt / behavior constraints
    │   ├── tool_manifest.py       # 暴露给模型的 tools 名称、描述、参数边界
    │   └── context_policy.py      # skills / memory / filesystem 暴露策略
    │
    ├── business/                  # 2. Business Subsystems
    │   ├── answers/
    │   │   └── models.py          # TaxAnswer / TaxCitation / TaxAnswerArtifact
    │   ├── references/
    │   │   ├── models.py          # Citation / ReferenceItem / ReferenceBundle
    │   │   ├── providers.py       # ReferenceProvider / LocalTaxAuthorityProvider
    │   │   ├── manager.py         # ReferenceManager
    │   │   └── tools.py           # find_tax_authorities: DeepAgents tool adapter
    │   └── analysis/
    │       ├── intent_classifier.py
    │       └── tax_context.py     # analyze_tax_question / analyze_tax_context
    │
    ├── runtime/                   # 3. Runtime Adapters
    │   ├── executor.py            # execute_turn / stream_turn 主编排
    │   ├── conversation.py        # ConversationRequest / ConversationMessage
    │   ├── checkpointing.py       # LangGraph checkpointer 配置
    │   ├── ag_ui.py               # DeepAgents raw events → AG-UI events
    │   ├── observability.py       # Langfuse adapter
    │   ├── sse.py                 # SSE 文本渲染
    │   └── config.py              # env/config
    │
    └── delivery/                  # 4. Delivery Surfaces
        ├── http_api.py            # FastAPI /chat, /chat/stream, /batch
        ├── batch.py               # 文件批处理编排
        └── batch_io/
            ├── question_extractor.py
            └── output_formatter.py
```

### 2.3 文件归类与当前状态映射

| 当前路径 | 目标归类 | 性质 |
|---------|--------|------|
| `runtime/agent_executor.py::build_agent` | `agent/graph.py` | Agent Harness 装配 |
| `runtime/agent_executor.py::TAX_SYSTEM_PROMPT` | `agent/instructions.py` | Agent Harness 约束 |
| `runtime/agent_executor.py::SKILL_SOURCES / MEMORY_SOURCES / FilesystemBackend` | `agent/context_policy.py` | Agent Harness 上下文策略 |
| `runtime/agent_executor.py::tools=[...]` | `agent/tool_manifest.py` | Agent Harness 工具暴露策略 |
| `runtime/agent_executor.py::TaxAnswer / TaxCitation` | `business/answers/models.py` | 业务输出契约 |
| `runtime/agent_executor.py::ExecutionResult / AgentExecutor` | `runtime/executor.py` | Runtime Adapter |
| `runtime/checkpointing.py` | `runtime/checkpointing.py` | Runtime Adapter |
| `runtime/ag_ui_protocol.py` | `runtime/ag_ui.py` | Runtime Adapter |
| `runtime/conversation.py` | `runtime/conversation.py` | Runtime Adapter |
| `runtime/observability.py` | `runtime/observability.py` | Runtime Adapter |
| `runtime/sse_protocol.py` | `runtime/sse.py` | Runtime Adapter |
| `config.py` | `runtime/config.py` | Runtime Adapter |
| `domain/reference_layer.py` | `business/references/` | Business Subsystem |
| `domain/domain_knowledge.py` | `business/analysis/tax_context.py` | Business Subsystem |
| `domain/intent_classifier.py` | `business/analysis/intent_classifier.py` | Business Subsystem |
| `service/service_app.py` | `delivery/http_api.py` | Delivery Surface |
| `service/batch_runtime.py` | `delivery/batch.py` | Delivery Surface |
| `io/output_formatter.py` | `delivery/batch_io/` | Delivery Surface |
| `io/question_extractor.py` | `delivery/batch_io/` | Delivery Surface |

说明：上表只映射继续保留的主路径能力。旧 `InteractionMode` / `response_strategy.py`、旧 `retrieve_tax_context` wrapper、`legacy/*` 和本地 JSON trace 相关实现属于清理清单，不进入目标架构模块结构。

### 2.4 核心调用链

```text
# 流式对话 (/chat/stream)
delivery/http_api.py
  → runtime/executor.stream_turn()
    → DeepAgents astream_events
    → runtime/ag_ui.normalize_ag_ui_event()
    → runtime/sse.render_sse()

# 同步对话 (/chat)
delivery/http_api.py
  → runtime/executor.execute_turn()
    → DeepAgents ainvoke
    → business/references/tools.find_tax_authorities
    → business/analysis/tax_context.analyze_tax_context
    → business/answers/models.TaxAnswer

# 批处理 (/batch / CLI)
delivery/batch.py / main.py
  → delivery/batch_io/question_extractor → business/analysis/intent_classifier
  → runtime/executor.execute_turn() (per question)
  → delivery/batch_io/output_formatter (Markdown + JSON)
```

### 2.5 AG-UI 后的交互策略

引入 AG-UI 后，`InteractionMode` 不再作为架构级概念保留。架构层只保留稳定交付面：

- `/chat/stream`：对外唯一 streaming 协议，输出 AG-UI SSE。
- `/chat`：同步 JSON API，最终业务产物与 AG-UI `RUN_FINISHED.result` 对齐。
- `/batch` / CLI：批处理交付面，不复用 `/chat/stream` 的 mode 模型。

如后续需要“只看进度、不看文本 delta”这类视图差异，应作为 delivery 层的投影策略或前端展示策略处理，不回到 `InteractionMode` 枚举。

---

## 3. 数据架构 (Data Architecture)

### 3.1 数据流转

```text
输入文件 (.txt/.docx)
   → delivery/batch_io/question_extractor → list[str]
   → business/analysis/intent_classifier → ClassifiedQuestion[]
   → runtime/executor → ExecutionResult
       → DeepAgents answer generation
       → business/references/tools.find_tax_authorities → ReferenceBundle / Citation[]
   → delivery/batch_io/output_formatter → Markdown + JSON
```

### 3.2 持久化存储

| 存储 | 技术 | 用途 | 生命周期 |
|------|------|------|---------|
| Checkpoint | SQLite (`service.sqlite`) | LangGraph state 持久化 | 持续累积 |
| 输出报告 | Markdown + JSON | 税审报告 | 按需保留 |
| Langfuse | 外部服务 | 主观测 trace | 按需保留 |
| 语义记忆 | DeepAgents memory + virtual filesystem | 跨对话参考材料 | 按需管理 |

### 3.3 Citation 数据模型

```json
{
  "source_id": "vat-temporary-regulations",
  "title": "中华人民共和国增值税暂行条例",
  "snippet": "...",
  "provider_id": "local_tax_authorities",
  "source_type": "law",
  "locator": null,
  "confidence": 0.95
}
```

---

## 4. 技术架构 (Technology Architecture)

### 4.1 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 语言 | Python | ≥ 3.11 |
| Agent 框架 | DeepAgents (LangChain/LangGraph) | ≥ 0.6.3 |
| 服务框架 | FastAPI + Uvicorn | 见 `pyproject.toml` |
| Checkpoint | langgraph-checkpoint-sqlite | ≥ 3.0 |
| 观测 | Langfuse (本地部署) | — |
| 协议 | AG-UI (SSE) | — |
| 文件解析 | python-docx | 见 `pyproject.toml` |

### 4.2 部署拓扑

```text
┌─────────────────────┐
│  内网机器 / 本机     │
│                      │
│  FastAPI :3004       │ ← HTTP API
│  ├ /chat             │
│  ├ /chat/stream      │ ← AG-UI SSE
│  ├ /batch            │
│  └ /health           │
│                      │
│  SQLite              │ ← Checkpoint
│  Filesystem          │ ← Reports / Skills / Memories
│                      │
│  Langfuse :3000      │ ← Observability (optional)
└─────────────────────┘
```

### 4.3 关键依赖

```text
deepagents                Agent 框架
langchain                 init_chat_model / OpenAI-compatible 模型接入
langgraph-checkpoint-sqlite  SQLite checkpoint
langfuse                 观测平台 SDK
fastapi + uvicorn        HTTP 服务
python-docx              Word 文件解析
pydantic                 Schema 验证
```

### 4.4 环境要求

- `.env` 文件（不提交 git）配置 API key、模型、Langfuse 等
- `OPENAI_API_KEY` / `OPENAI_BASE_URL` — OpenAI-compatible 模型配置
- `DEEPAGENTS_MODEL=openai:gpt-4o` — 代码默认模型，可改为 MiniMax / Ollama 等
- `LANGFUSE_ENABLED=1` — 可选，开启 Langfuse 观测
