---
feature_ids: [F004, F005, F006]
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
│   ├── 本地法规语料     seed data (demo)
│   └── Reference Layer  可扩展的引用提供者接口
├── 审计追溯            核心：运行过程可记录、可复现
│   ├── Langfuse observability 观测平台
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

### 2.1 模块分层

```
┌──────────────────────────────────────────────┐
│                入口层 (Entry)                  │
│  main.py (CLI)    app.py (ASGI/FastAPI)       │
├──────────────────────────────────────────────┤
│                服务层 (Service)                │
│  service/service_app.py    (路由/SSE/校验)     │
│  service/batch_runtime.py  (批处理管道)        │
├──────────────────────────────────────────────┤
│                运行时层 (Runtime)               │
│  runtime/agent_executor.py (主执行器)          │
│  runtime/ag_ui_protocol.py (AG-UI 协议)       │
│  runtime/checkpointing.py  (checkpoint 工厂)   │
│  runtime/conversation.py   (请求/响应 schema)  │
│  runtime/response_strategy.py (InteractionMode)│
│  runtime/observability.py  (Langfuse 适配器)   │
│  runtime/audit_trace.py    (本地 trace 兼容)   │
├──────────────────────────────────────────────┤
│                领域层 (Domain)                 │
│  domain/reference_layer.py  (引用框架核心)     │
│  domain/tax_retrieval.py    (旧兼容层)         │
│  domain/domain_knowledge.py (F003 领域匹配)    │
│  domain/intent_classifier.py(意图分类)         │
├──────────────────────────────────────────────┤
│                IO 层 (Input/Output)            │
│  io/output_formatter.py     (报告生成)         │
│  io/question_extractor.py   (问题提取)         │
├──────────────────────────────────────────────┤
│              遗留层 (Legacy)                   │
│  legacy/planner.py          (旧规划器)         │
│  legacy/rag_decorator.py    (旧 RAG 装饰器)   │
└──────────────────────────────────────────────┘
```

### 2.2 核心调用链

```
# 流式对话 (/chat/stream)
service_app.py
  → agent_executor.stream_turn()
    → DeepAgents astream_events
    → ag_ui_protocol.normalize_ag_ui_event()
    → sse_protocol.render_sse()

# 同步对话 (/chat)
service_app.py
  → agent_executor.execute_turn()
    → DeepAgents ainvoke
    → tools: find_tax_authorities / analyze_tax_question

# 批处理 (/batch / CLI)
batch_runtime.py / main.py
  → question_extractor → intent_classifier
  → agent_executor.execute_turn() (per question)
  → output_formatter (Markdown + JSON)
```

### 2.3 InteractionMode 策略

| Mode | 适用接口 | 行为 |
|------|---------|------|
| `answer_stream` | `/chat/stream` | 默认，输出 AG-UI `TEXT_MESSAGE_CONTENT` |
| `progress_stream` | `/chat/stream` | 过滤 `TEXT_MESSAGE_CONTENT`，保留 tool / final result 事件 |
| `structured_final` | `/chat` | 返回完整 TaxAnswer JSON |

---

## 3. 数据架构 (Data Architecture)

### 3.1 数据流转

```
输入文件 (.txt/.docx)
   → question_extractor  → list[str]
   → intent_classifier   → ClassifiedQuestion[]
   → AgentExecutor       → ExecutionResult
       → DeepAgents answer generation
       → tool: find_tax_authorities → ReferenceBundle / Citation[]
   → output_formatter    → Markdown + JSON
```

说明：`audit_trace.py` 是 F003 兼容保留，不在当前 `/chat`、`/chat/stream` 或 `/batch` 主调用链上。当前主观测路径是 Langfuse adapter，当前本地可运行基线是 checkpoint + output 文件。

### 3.2 持久化存储

| 存储 | 技术 | 用途 | 生命周期 |
|------|------|------|---------|
| Checkpoint | SQLite (`service.sqlite`) | LangGraph state 持久化 | 持续累积 |
| Audit Trace | JSONL 文件 | F003 兼容 trace 记录 | 按需清理 |
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
| 服务框架 | FastAPI + Uvicorn | — |
| Checkpoint | langgraph-checkpoint-sqlite | 见 `pyproject.toml` / `requirements.txt` |
| 观测 | Langfuse (本地部署) | — |
| 协议 | AG-UI (SSE) | — |

### 4.2 部署拓扑

```
┌─────────────────┐
│  内网机器/本机   │
│                  │
│  FastAPI :3004   │ ← HTTP API for external systems
│  ├ /chat         │
│  ├ /chat/stream  │ ← AG-UI SSE
│  ├ /batch        │
│  └ /health       │
│                  │
│  SQLite          │ ← Checkpoint
│  Filesystem      │ ← Reports / Trace / Skills
│                  │
│  Langfuse :3000  │ ← Observability (optional)
└─────────────────┘
```

### 4.3 关键依赖

```text
deepagents          — Agent 框架
langchain           — init_chat_model / OpenAI-compatible 模型接入
langchain-ollama    — Ollama 模型支持（可选路径）
langgraph-checkpoint-sqlite — SQLite checkpoint
langfuse            — 观测平台 SDK
fastapi + uvicorn   — HTTP 服务
python-docx         — Word 文件解析
pydantic            — Schema 验证
```

### 4.4 环境要求

- `.env` 文件（不提交 git）配置 API key、模型、Langfuse 等
- `OPENAI_API_KEY` / `OPENAI_BASE_URL` — OpenAI-compatible 模型配置
- `DEEPAGENTS_MODEL=openai:gpt-4o` — 代码默认模型，可改为 MiniMax / Ollama 等兼容模型
- `LANGFUSE_ENABLED=1` — 可选，开启 Langfuse 观测
