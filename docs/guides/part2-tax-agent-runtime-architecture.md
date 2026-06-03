---
feature_ids: [F004, F005, F006]
topics: [architecture, runtime, tax-agent, deepagents, fastapi, checkpoint, langfuse]
doc_kind: guide
created: 2026-05-29
updated: 2026-06-03
---

# Part 2 税务 Agent 结构与运行时架构

本文是 `part2-tax-agent/` 的维护入口。当前代码已迁移到四个主边界：

```text
Agent Harness -> Business Subsystems -> Runtime Adapters -> Delivery Surfaces
```

更完整的目标结构见 [项目 4A 架构文档](../architecture/4a-architecture.md)。

## 当前项目整体结构

```text
part2-tax-agent/
├─ app.py                         # ASGI thin entrypoint
├─ main.py                        # CLI batch thin entrypoint
├─ check_opengauss_compat.py       # OpenGauss checkpoint 兼容性验证脚本
├─ check_sqlite_checkpoint_persistence.py # SQLite checkpoint 本地验证脚本
├─ sample_input.txt
├─ requirements.txt
├─ skills/                         # DeepAgents progressive disclosure skills
├─ memories/                       # DeepAgents memory seed
├─ output/                         # 本地运行输出
├─ tax_agent/
│  ├─ agent/                       # Agent Harness
│  │  ├─ graph.py                  # create_deep_agent 装配
│  │  ├─ instructions.py           # system prompt / behavior constraints
│  │  ├─ tool_manifest.py          # tools 暴露策略
│  │  └─ context_policy.py         # skills / memory / filesystem 策略
│  ├─ business/
│  │  ├─ answers/                  # TaxAnswer / TaxCitation
│  │  ├─ references/               # Reference Layer
│  │  └─ analysis/                 # 意图分类与税务上下文分析
│  ├─ runtime/
│  │  ├─ executor.py               # AgentExecutor、execute_turn、stream_turn
│  │  ├─ conversation.py           # /chat 请求与响应 schema
│  │  ├─ checkpointing.py          # LangGraph checkpointer 配置
│  │  ├─ ag_ui.py                  # AG-UI event projection
│  │  ├─ sse.py                    # SSE event 渲染
│  │  ├─ observability.py          # Langfuse callback adapter
│  │  └─ config.py                 # 环境变量与运行配置
│  ├─ delivery/
│  │  ├─ http_api.py               # FastAPI 路由
│  │  ├─ batch.py                  # batch pipeline
│  │  └─ batch_io/                 # txt/docx 输入与 Markdown/JSON 输出
│  ├─ domain/ service/ io/         # 旧路径兼容 wrapper
│  └─ legacy/                      # 历史实验代码，不是主路径
└─ tests/
```

## 分层边界

| 层 | 目录 | 职责 | 不负责 |
|---|---|---|---|
| Agent Harness | `tax_agent/agent/` | 模型可见约束、tool exposure、context policy、`create_deep_agent` 装配 | 保存业务证据模型 |
| Business Subsystems | `tax_agent/business/` | 业务输出契约、Reference Layer、确定性分析 | HTTP/SSE/CLI 交付 |
| Runtime Adapters | `tax_agent/runtime/` | 执行器、checkpoint、observability、AG-UI/SSE 投影 | 文件解析、报告输出 |
| Delivery Surfaces | `tax_agent/delivery/` | FastAPI、CLI batch、batch IO | DeepAgents 装配细节 |
| Compatibility | `tax_agent/domain/` `service/` `io/` | 旧 import wrapper | 新功能扩展 |
| Assets | `skills/`, `memories/` | DeepAgents 原生 skills/memory 输入 | Python 控制流 |

## 运行时架构图

```mermaid
flowchart TD
    Client[调用方 App / CLI] -->|POST /chat| ChatRoute[delivery/http_api /chat]
    Client -->|POST /chat/stream| StreamRoute[delivery/http_api /chat/stream]
    Client -->|POST /batch 或 main.py| BatchRoute[delivery/batch]

    ChatRoute --> Turn[ConversationRequest messages + session_id + trace_id + thread_id]
    StreamRoute --> Turn

    BatchRoute --> Extract[delivery/batch_delivery/batch_io/question_extractor]
    Extract --> Classify[business/analysis/IntentClassifier]
    Classify --> PerQuestion[per-question ConversationRequest]
    PerQuestion --> Turn

    Turn --> Executor[runtime/executor]
    Executor --> Harness[agent/graph build_tax_agent]
    Harness --> DeepAgents[DeepAgents agent]
    DeepAgents --> Tools[business/references/tools + business/analysis]

    Executor --> Checkpoint[LangGraph checkpointer]
    Executor --> Obs[Langfuse callback adapter]
    Executor --> Response[ExecutionResult]

    Response --> ChatResp[ChatResponse]
    Response --> SSE[AG-UI SSE events]
    Response --> Report[Markdown / JSON batch report]
```

## 关键取舍

- `/chat` 和 `/chat/stream` 是实时问答主路径：调用方显式传入当前 conversation 的 `messages`，`thread_id` 只负责 checkpoint 恢复。
- `/chat/stream` 输出 AG-UI SSE；旧 `InteractionMode` 不再作为架构级概念保留。
- `/batch` 是独立 delivery surface：保留“文件 -> 提取问题 -> 分类 -> 逐题回答 -> 报告”能力，但不包装成 DeepAgents skill。
- `TaxAnswer` / `TaxCitation` 属于 `business/answers/`，只是被 harness 作为 `response_format` 引用。
- `Reference Layer` 属于 `business/references/`，`find_tax_authorities` 只是暴露给 DeepAgents 的 tool adapter。
- `domain/`、`service/`、`io/` 只保留旧 import wrapper；新能力不得继续扩展这些目录。

## 常用调用

```powershell
# CLI batch
cd E:\ai-project\poc-demo\part2-tax-agent
python main.py --input sample_input.txt --output output

# FastAPI 服务，默认端口 3004
uvicorn app:app --host 0.0.0.0 --port 3004

# OpenGauss checkpoint 兼容性验证
$env:CHECKPOINT_BACKEND="opengauss"
$env:OPENGAUSS_DSN="postgresql://user:password@localhost:5432/postgres"
python check_opengauss_compat.py

# SQLite checkpoint 调用链验证
python check_sqlite_checkpoint_persistence.py --output output --thread-id demo-sqlite-thread
```
