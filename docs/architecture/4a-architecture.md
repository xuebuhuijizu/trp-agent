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
│   ├── LangGraph checkpoint state 持久化
│   └── 本地 audit trace JSONL 兼容保留
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

本项目的架构以 DeepAgents harness 为中心，但并非所有项目自有抽象都强行归为 DeepAgents 原生概念。参考 OpenHands、CrewAI、LangGraph 等明星项目，成熟 agent 项目会围绕 harness 建立多个一等边界：

- **Agent Harness**：DeepAgents `create_deep_agent` — 负责 planning、tool calling、skills、memory、filesystem
- **Business Subsystems**：项目自有的稳定抽象，如引用/证据体系、确定性分析逻辑
- **Runtime Adapters**：将 DeepAgents/LangGraph 能力适配到项目执行环境
- **Delivery Surfaces**：不同形态的交付接口（HTTP、CLI、batch、前端）

这些边界通过**显式 adapter** 连接，而不是全部揉进 tool 或 middleware。

开发时的具体设计准则见：[Agent Harness 设计准则](../guides/agent-harness-design-principles.md)。

### 2.2 模块结构

```text
tax_agent/
│
├── agent/                              # Agent Harness
│   ├── graph.py                        # build_tax_agent(): create_deep_agent(...)
│   ├── prompts.py                      # TAX_SYSTEM_PROMPT
│   └── response_schema.py              # TaxAnswer / TaxCitation / TaxAnswerArtifact
│
├── references/                         # Business Subsystem: 引用/证据架构
│   ├── models.py                       # Citation / ReferenceItem / ReferenceBundle
│   ├── providers.py                    # ReferenceProvider / LocalTaxAuthorityProvider
│   ├── manager.py                      # ReferenceManager（去重、排序、标准化）
│   └── tools.py                        # find_tax_authorities: DeepAgents tool adapter
│
├── analysis/                           # Business Subsystem: 确定性分析
│   ├── intent_classifier.py            # 意图分类（definition/rate/compliance）
│   └── tax_context.py                  # analyze_tax_question / analyze_tax_context
│
├── runtime/                            # Runtime Adapters
│   ├── agent_executor.py               # execute_turn / stream_turn 主编排
│   ├── conversation.py                 # ConversationRequest / ConversationMessage
│   ├── checkpointing.py                # LangGraph checkpointer 配置（SQLite/memory）
│   ├── ag_ui_protocol.py               # DeepAgents raw events → AG-UI events
│   ├── response_strategy.py            # InteractionMode 策略
│   ├── observability.py                # Langfuse adapter
│   └── sse_protocol.py                 # SSE 文本渲染
│
├── delivery/                           # Delivery Surfaces
│   ├── http_api.py                     # FastAPI /chat, /chat/stream, /batch
│   ├── batch.py                        # 文件批处理编排
│   └── io/                             # 离线批处理输入输出
│       ├── question_extractor.py       # txt/docx → questions
│       └── output_formatter.py         # Markdown / JSON 报告
│
├── deprecated/                         # 明确待删除的兼容层
│   ├── tax_retrieval.py                # 旧 find_tax_authorities 名，兼容 wrapper
│   ├── planner.py                      # F001 静态 planner
│   ├── rag_decorator.py                # F001 RAG decorator
│   └── audit_trace.py                  # F003 本地 trace，当前非主路径
│
├── config.py                           # env/config
├── main.py                             # CLI batch 入口
└── app.py                              # FastAPI ASGI 入口
```

### 2.3 文件归类与当前状态映射

| 当前路径 | 新归类 | 性质 |
|---------|--------|------|
| `runtime/agent_executor.py` | `runtime/` | Runtime Adapter |
| `runtime/checkpointing.py` | `runtime/` | Runtime Adapter |
| `runtime/ag_ui_protocol.py` | `runtime/` | Runtime Adapter |
| `runtime/conversation.py` | `runtime/` | Runtime Adapter |
| `runtime/response_strategy.py` | `runtime/` | Runtime Adapter |
| `runtime/observability.py` | `runtime/` | Runtime Adapter |
| `runtime/sse_protocol.py` | `runtime/` | Runtime Adapter |
| `domain/reference_layer.py` | → `references/` | Business Subsystem |
| `domain/domain_knowledge.py` | → `analysis/` | Business Subsystem |
| `domain/intent_classifier.py` | → `analysis/` | Business Subsystem |
| `domain/tax_retrieval.py` | → `deprecated/` | 兼容层 |
| `service/service_app.py` | → `delivery/http_api.py` | Delivery Surface |
| `service/batch_runtime.py` | → `delivery/batch.py` | Delivery Surface |
| `io/output_formatter.py` | → `delivery/io/` | Delivery Surface |
| `io/question_extractor.py` | → `delivery/io/` | Delivery Surface |
| `legacy/planner.py` | → `deprecated/` | 兼容层 |
| `legacy/rag_decorator.py` | → `deprecated/` | 兼容层 |
| `runtime/audit_trace.py` | → `deprecated/` | 兼容层 |

### 2.4 核心调用链

```text
# 流式对话 (/chat/stream)
delivery/http_api.py
  → runtime/agent_executor.stream_turn()
    → DeepAgents astream_events
    → runtime/ag_ui_protocol.normalize_ag_ui_event()
    → runtime/sse_protocol.render_sse()

# 同步对话 (/chat)
delivery/http_api.py
  → runtime/agent_executor.execute_turn()
    → DeepAgents ainvoke
    → references/tools.find_tax_authorities
    → analysis/tax_context.analyze_tax_context

# 批处理 (/batch / CLI)
delivery/batch.py / main.py
  → delivery/io/question_extractor → analysis/intent_classifier
  → runtime/agent_executor.execute_turn() (per question)
  → delivery/io/output_formatter (Markdown + JSON)
```

### 2.5 InteractionMode 策略

| Mode | 适用接口 | 行为 |
|------|---------|------|
| `answer_stream` | `/chat/stream` | 默认，输出 AG-UI `TEXT_MESSAGE_CONTENT` |
| `progress_stream` | `/chat/stream` | 过滤 `TEXT_MESSAGE_CONTENT`，保留 tool / final result 事件 |
| `structured_final` | `/chat` | 返回完整 TaxAnswer JSON |

---

## 3. 数据架构 (Data Architecture)

### 3.1 数据流转

```text
输入文件 (.txt/.docx)
   → delivery/io/question_extractor → list[str]
   → analysis/intent_classifier → ClassifiedQuestion[]
   → runtime/agent_executor → ExecutionResult
       → DeepAgents answer generation
       → references/tools.find_tax_authorities → ReferenceBundle / Citation[]
   → delivery/io/output_formatter → Markdown + JSON
```

### 3.2 持久化存储

| 存储 | 技术 | 用途 | 生命周期 |
|------|------|------|---------|
| Checkpoint | SQLite (`service.sqlite`) | LangGraph state 持久化 | 持续累积 |
| Audit Trace | JSONL 文件 | 兼容保留，非主路径 | 按需清理 |
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
