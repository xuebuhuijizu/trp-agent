---
feature_ids: [F004]
topics: [architecture, runtime, tax-agent, deepagents, fastapi, checkpoint, langfuse]
doc_kind: guide
created: 2026-05-29
---

# Part 2 税务 Agent 结构与运行时架构

本文是 `part2-tax-agent/` 的维护入口。F004 之后，项目不再按“一个脚本 + 一批工具文件”组织，而是按运行时职责分层：领域知识、输入输出、Agent runtime、服务入口、legacy adapter 分开维护。

## 当前项目整体结构

```text
part2-tax-agent/
├─ app.py                         # ASGI 入口：uvicorn app:app --port 3004
├─ main.py                        # CLI batch 入口
├─ check_opengauss_compat.py       # OpenGauss checkpoint 兼容性验证脚本
├─ check_sqlite_checkpoint_persistence.py # SQLite checkpoint 本地验证脚本
├─ sample_input.txt                # 本地 batch 示例输入
├─ requirements.txt
├─ skills/                         # DeepAgents progressive disclosure skills
├─ memories/                       # DeepAgents memory seed
├─ output/                         # 本地运行输出
├─ tax_agent/
│  ├─ config.py                    # 环境变量与运行配置
│  ├─ domain/
│  │  ├─ domain_knowledge.py       # 税审领域 seed 匹配与上下文分析
│  │  ├─ intent_classifier.py      # batch 问题意图分类
│  │  └─ tax_retrieval.py          # retrieve_tax_context tool 与 citation 提取
│  ├─ io/
│  │  ├─ question_extractor.py     # txt/docx 问题提取
│  │  └─ output_formatter.py       # Markdown/JSON 报告输出
│  ├─ runtime/
│  │  ├─ agent_executor.py         # AgentExecutor、execute_turn、DeepAgents 构造
│  │  ├─ audit_trace.py            # checkpoint config 与本地 audit trace fallback
│  │  ├─ conversation.py           # /chat 请求与响应 schema
│  │  ├─ observability.py          # Langfuse callback adapter
│  │  └─ sse_protocol.py           # 稳定 SSE event 渲染
│  ├─ service/
│  │  ├─ batch_runtime.py          # 显式 batch pipeline
│  │  └─ service_app.py            # FastAPI 路由
│  └─ legacy/
│     ├─ planner.py                # F001 静态 plan adapter，保留兼容
│     └─ rag_decorator.py          # F001 RAG adapter，保留兼容
└─ tests/
   ├─ test_tax_agent.py
   ├─ test_f003_audit_and_skills.py
   ├─ test_f004_runtime.py
   ├─ test_legacy_cleanup.py
   └─ test_part1_deepagents_examples.py
```

## 分层边界

| 层 | 目录 | 职责 | 不负责 |
|---|---|---|---|
| Entrypoints | `app.py`, `main.py`, `check_opengauss_compat.py` | 对外启动入口和运维验证脚本 | 承载业务逻辑 |
| Service | `tax_agent/service/` | FastAPI 路由、SSE、batch 路由编排 | 直接实现领域匹配或模型细节 |
| Runtime | `tax_agent/runtime/` | DeepAgents 调用、checkpoint、observability、conversation schema | 文档解析、报告输出 |
| Domain | `tax_agent/domain/` | 税审领域 seed、检索 tool、意图分类 | 保存运行状态 |
| IO | `tax_agent/io/` | 输入文件解析、输出报告格式化 | 调用模型 |
| Legacy | `tax_agent/legacy/` | 兼容 F001/F002 早期演示接口 | 新主路径扩展 |
| Assets | `skills/`, `memories/` | DeepAgents 原生 skills/memory 输入 | Python 控制流 |

## 运行时架构图

```mermaid
flowchart TD
    Client[调用方 App / CLI] -->|POST /chat| ChatRoute[FastAPI /chat]
    Client -->|POST /chat/stream| StreamRoute[FastAPI /chat/stream]
    Client -->|POST /batch 或 main.py| BatchRoute[显式 batch route]

    ChatRoute --> Turn[ConversationRequest messages + session_id + trace_id + thread_id]
    StreamRoute --> Turn

    BatchRoute --> Extract[question_extractor]
    Extract --> Classify[IntentClassifier]
    Classify --> PerQuestion[per-question ConversationRequest]
    PerQuestion --> Turn

    Turn --> Executor[AgentExecutor.execute_turn]
    Executor --> DeepAgents[DeepAgents agent]
    DeepAgents --> Tools[retrieve_tax_context / analyze_tax_question]
    Tools --> Domain[domain seed knowledge + skills refs]

    Executor --> Checkpoint[LangGraph checkpointer: memory/sqlite/opengauss]
    Executor --> Obs[Langfuse callback adapter]
    Executor --> Response[ExecutionResult]

    Response --> ChatResp[ChatResponse]
    Response --> SSE[SSE events]
    Response --> Report[Markdown / JSON batch report]
```

## 调用示例图

```mermaid
sequenceDiagram
    participant App as 调用方应用
    participant API as FastAPI 3004
    participant Exec as AgentExecutor
    participant Agent as DeepAgents
    participant CKPT as Checkpoint
    participant LF as Langfuse

    App->>API: POST /chat {session_id, trace_id, thread_id, messages}
    API->>Exec: execute_turn(ConversationRequest)
    Exec->>CKPT: invoke_config(thread_id, metadata, tags)
    Exec->>LF: callbacks + metadata + tags
    Exec->>Agent: ainvoke({messages}, config)
    Agent-->>Exec: messages + structured_response
    Exec-->>API: ExecutionResult(answer, citations, checkpoint ids)
    API-->>App: ChatResponse

    App->>API: POST /chat same thread_id + new messages
    API->>Exec: execute_turn(...)
    Exec->>CKPT: load previous state by thread_id
    Exec->>Agent: continue conversation
    Agent-->>Exec: next answer
    API-->>App: continued ChatResponse
```

## 关键取舍

- `/chat` 和 `/chat/stream` 是 F004 主路径：调用方显式传入当前 conversation 的 `messages`，`thread_id` 只负责 checkpoint 恢复，不把长期偏好塞进 messages。
- `/batch` 是兼容路径：保留原来的“文件 -> 提取问题 -> 分类 -> 逐题回答 -> 报告”能力，但由 CLI/API 路由显式选择，不包装成 DeepAgents skill。
- `skills/` 仍然是 Agent 可读的 progressive disclosure 指令和领域参考，不承担确定性 pipeline。
- `legacy/` 只保留早期演示适配器，新功能默认不要继续扩展这里。
- `runtime/audit_trace.py` 目前仍保留本地 trace/checkpoint 辅助能力；Langfuse 是 F004 的主观测方向，本地 JSON trace 后续应继续降级为 fallback。

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

`POST /chat` 示例：

```json
{
  "session_id": "sess-001",
  "trace_id": "trace-001",
  "thread_id": "tax-thread-001",
  "messages": [
    {"role": "user", "content": "请解释增值税进项税额抵扣规则"},
    {"role": "assistant", "content": "需要结合发票、用途和认证状态判断。"},
    {"role": "user", "content": "那用于集体福利的进项税额呢？"}
  ]
}
```
