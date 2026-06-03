---
feature_ids: [F004, F005]
topics: [deepagents, tax-agent, runtime, reference-layer]
doc_kind: guide
created: 2026-06-03
---

# TRP Agent 税务 Agent PoC

这是一个基于 DeepAgents 的税务问答 PoC。当前主线是 `part2-tax-agent`：支持 CLI 批处理、HTTP `/chat`、HTTP `/chat/stream`，并通过 F005 Reference Layer 管理法规/政策等外部引用材料。

## 当前状态

- Runtime：F004 已完成 conversation runtime、checkpoint、observability 和 AG-UI streaming 协议；旧 `InteractionMode` 不再作为架构级概念保留。
- Reference Layer：F005 已完成第一版 `ReferenceProvider` / `ReferenceManager` / `ReferenceBundle` / `Citation`。
- 主 Agent tool：`find_tax_authorities`。
- 旧 tool：`retrieve_tax_context` 仅保留为兼容 wrapper，不是新主路径。

## 目录速览

```text
part2-tax-agent/
├── main.py                      # CLI batch 入口
├── app.py                       # FastAPI ASGI 入口
├── check_*.py                   # 本地运维/兼容性验证脚本
├── tax_agent/
│   ├── runtime/                 # AgentExecutor、checkpoint、streaming、SSE
│   ├── agent/                   # Agent Harness：instructions、tool exposure、context policy
│   ├── business/                # answers、Reference Layer、确定性分析
│   ├── delivery/                # FastAPI routes、batch、batch_io
│       └── (旧 domain/ service/ io/ 已移除，能力迁至 business/ 和 delivery/)
├── skills/                      # DeepAgents skills
├── memories/                    # DeepAgents memory source
└── tests/                       # 主项目测试
```

新人优先读：

1. `docs/guides/part2-tax-agent-current-runtime.md`
2. `part2-tax-agent/tax_agent/agent/graph.py`
3. `part2-tax-agent/tax_agent/runtime/executor.py`
4. `part2-tax-agent/tax_agent/business/references/tools.py`
5. `part2-tax-agent/tax_agent/delivery/http_api.py`

## 环境准备

建议使用 Python 3.12。

```powershell
cd E:\ai-project\poc-demo
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

如果只安装 `part2-tax-agent/requirements.txt`，也可以：

```powershell
python -m pip install -r part2-tax-agent\requirements.txt
python -m pip install pytest pytest-asyncio
```

## 配置

复制 `.env.example` 为 `.env`，按你的模型和服务配置填写。

```powershell
Copy-Item .env.example .env
```

常见变量：

```text
DEEPAGENTS_MODEL=openai:gpt-4o
OPENAI_API_KEY=...
```

## 运行测试

主项目测试：

```powershell
python -m pytest part2-tax-agent\tests -q --basetemp=.codex-tmp\pytest-basetemp -o cache_dir=.codex-tmp\pytest-cache
```

当前基线：`87 passed`。

不要直接收集 `packages/`，它是历史迁移快照，不是主项目。

## CLI 批处理

```powershell
cd part2-tax-agent
python main.py --input sample_input.txt --output ..\output
```

输出会生成 Markdown 和 JSON 报告。

## HTTP 服务

启动 API：

```powershell
cd part2-tax-agent
python -m uvicorn app:app --host 127.0.0.1 --port 3004
```

健康检查：

```powershell
curl http://127.0.0.1:3004/health
```

主要接口：

- `POST /chat`
- `POST /chat/stream`（AG-UI SSE）
- `POST /batch`
- `GET /state/history`

## Reference Layer

F005 后，外部引用主路径是：

```text
find_tax_authorities
  -> ReferenceManager
  -> LocalTaxAuthorityProvider
  -> ReferenceBundle
  -> Citation[]
```

`Citation` 稳定字段包括：

```text
citation_id
source_id
source_type
provider_id
title
locator
snippet
confidence
retrieved_at
metadata
```

当前本地法规 seed 的 `source_type` 是 `law`。

## GitHub 迁移说明

本仓库已配置 remote：

```text
https://github.com/xuebuhuijizu/trp-agent.git
```

如果命令行访问 GitHub 失败，通常需要配置 Git 代理：

```powershell
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
```

然后推送：

```powershell
git push -u origin master
```
