---
feature_ids: [F004]
topics: [deepagents, reference, examples]
doc_kind: reference
created: 2026-05-30
---

# DeepAgents 官方示例完整参考

来源：https://github.com/langchain-ai/deepagents/tree/main/examples
总计：16 个示例

---

## 1. Research 类

### 1.1 deep_research — 多步深度研究 Agent

**路径：** `examples/deep_research/`
**核心文件：** `agent.py`, `research_agent/prompts.py`, `research_agent/tools.py`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| 并行 sub-agent | 同时运行多个 research sub-agent | ⭐ 建议：税务多问题场景可借鉴 |
| `think_tool` | 搜索间隙让模型暂停反思 | ⭐ 建议：税务检索后增加自我审视 |
| 三段式 Prompt | 工作流 / 委托策略 / 子 Agent 规则分层 | ⭐ 建议：当前 system prompt 太扁平 |
| `langgraph.json` | 可部署的 graph 入口 | 下一阶段参考 |

---

## 2. Coding 类

### 2.1 deploy-coding-agent — 编码 Agent

**路径：** `examples/deploy-coding-agent/`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| LangSmith sandbox | 隔离沙箱执行代码 | ❌ 当前用 MiniMax，不需要 sandbox |
| `langgraph.json` 部署 | 可部署 graph | 下一阶段参考 |

### 2.2 nvidia_deep_agent — NVIDIA Nemotron Agent

**路径：** `examples/nvidia_deep_agent/`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| RAPIDS GPU 加速 | GPU 加速执行 | ❌ 与税务场景无关 |

---

## 3. Content 类

### 3.1 content-builder-agent — 内容构建 Agent

**路径：** `examples/content-builder-agent/`
**核心文件：** `content_writer.py`, `subagents.yaml`, `AGENTS.md`, `skills/*/SKILL.md`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| `subagents.yaml` 外化 | subagent 定义抽到 YAML | ⭐ 建议：高优先级，当前代码 hardcode |
| `load_subagents()` 辅助函数 | YAML → list[dict] 的映射函数 | ⭐ 建议：可直接复用此模式 |
| AGENTS.md + skills + subagents 三层 | 记忆/技能/子代理三层分离 | ⭐ 建议：当前已部分实现，可对齐 |
| Yaml frontmatter for skills | SKILL.md 带 name/description | ✅ 当前已实现 |

### 3.2 text-to-sql-agent — 自然语言转 SQL

**路径：** `examples/text-to-sql-agent/`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| 规划 + skill 驱动的 SQL 生成 | 多步规划后再生成 SQL | ❌ 与税务场景无关，但 skill 组织方式可参 |
| Chinook 演示数据库 | 小型 demo 数据 | ℹ️ 类似我们的 demo seed data |

### 3.3 llm-wiki — LLM Wiki

**路径：** `examples/llm-wiki/`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| 通过 `langsmith hub` 同步 wiki | 集中管理知识 | ❌ 当前不需要 langsmith hub |

---

## 4. Deployable Services 类

### 4.1 deploy-content-writer — 带用户隔离的内容写入 Agent

**路径：** `examples/deploy-content-writer/`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| per-user memory | 每个用户隔离 memory 文件 | ℹ️ 多人税审场景可参考 |
| `deepagents.toml` | 部署配置 | ❌ 当前 demo 阶段不需要 |
| Supabase 自定义 auth | 身份认证 | ❌ demo 阶段不需要 |

### 4.2 deploy-gtm-agent — GTM 策略 Agent

**路径：** `examples/deploy-gtm-agent/`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| sync + async subagents 协同 | 同步子代理 + 异步子代理配合 | ℹ️ 税务场景可参考异步的子任务 |
| 多策略对比 | 生成多个策略后对比 | ❌ 与税务场景不太匹配 |

### 4.3 async-subagent-server — 异步子代理服务

**路径：** `examples/async-subagent-server/`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| Agent Protocol 服务 | 自托管的异步子代理 MCP 服务 | ❌ 当前 demo 阶段不需要 |

### 4.4 deploy-mcp-docs-agent — MCP 文档 Agent

**路径：** `examples/deploy-mcp-docs-agent/`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| 通过 MCP 工具查询文档 | 用 MCP 协议连接文档源 | ℹ️ 如后续接入税务法规文档 MCP 可参考 |

---

## 5. Advanced Patterns 类

### 5.1 ralph_mode — 自动循环迭代 Agent

**路径：** `examples/ralph_mode/`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| 每轮新上下文 + 文件持久化 | 每次迭代用全新上下文，通过文件系统保留历史 | ⭐ 建议：对需要多轮深化的税务问题有价值 |
| 自主决定是否继续迭代 | Agent 自行判断结果是否足够 | ℹ️ 需谨慎控制迭代次数 |

### 5.2 rlm_agent — 递归 REPL Agent

**路径：** `examples/rlm_agent/`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| `create_rlm_agent` 辅助函数 | 封装递归 REPL 模式 | ℹ️ 如后续需要多轮对话增强可参考 |
| PTC subagent chain | Pass-The-Conch 链式并行分派 | ⭐ 建议：税务多问题可并行分派到不同 subagent |
| 并行 fan-out | 同时分派到多个子代理 | ⭐ 建议：多税审问题并行处理 |

### 5.3 repl_swarm — REPL Swarm

**路径：** `examples/repl_swarm/`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| TypeScript `swarm` skill | QuickJS 中运行 JavaScript | ❌ 当前不需要 JavaScript 执行 |
| 并行 subagent 分派 | 从 QuickJS 代码中分派 | ❌ 机制太复杂，不适合当前阶段 |

### 5.4 downloading_agents — Agent 即文件夹

**路径：** `examples/downloading_agents/`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| 下载 zip → 解压 → 运行 | 整个 Agent 作为文件分发 | ℹ️ 对内网迁移包的设计有参考价值 |

### 5.5 better-harness — eval 驱动的优化循环

**路径：** `examples/better-harness/`

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| Eval 驱动的外部优化 | 通过评估结果迭代优化 harness | ❌ 当前 demo 阶段不需要 |

---

## 6. Featured 独立项目

### 6.1 Deep Agents Code

**路径：** `libs/code/`（非 examples 目录）

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| 终端 TUI | 交互式终端界面 | ℹ️ 如后续需要交互式 demo 可参考 |
| 远程 sandbox | 隔离执行 | ❌ 当前不需要 |
| 自定义 skills 系统 | 类似我们的 skill 体系 | ✅ 当前已部分实现 |

### 6.2 Open SWE

**仓库：** https://github.com/langchain-ai/open-swe

| 特性 | 说明 | 借鉴意见 |
|------|------|---------|
| Slack/Linear/GitHub 集成 | 企业 IM 集成 | ℹ️ 如后续集成企业工作流可参考 |

---

## 汇总：特性分类矩阵

| 优先级 | 特性 | 来源示例 | 对应我们项目 |
|--------|------|---------|-------------|
| ⭐ 建议立即做 | YAML 外化 subagent | content-builder-agent | `agent_executor.py` 内 hardcode |
| ⭐ 建议立即做 | `think_tool` 反思 | deep_research | 税务检索后可自检 |
| ⭐ 建议立即做 | 三段式 Prompt 分层 | deep_research | 当前单层 system prompt |
| ⭐ 建议立即做 | `write_todos` + 报告结构模板 | deep_research | `RESEARCH_WORKFLOW_INSTRUCTIONS` 含完整报告模板 |
| ⭐ 建议参考 | Tool 命名空间与 `InjectedToolArg` | deep_research `tools.py` | LangChain 原生参数注入机制 |
| ⭐ 建议立即做 | 并行 subagent fan-out | rlm_agent / deep_research | 当前串行处理问题 |
| ℹ️ 下一阶段 | 每轮新 context | ralph_mode | checkpoint 后可借鉴 |
| ℹ️ 下一阶段 | per-user memory | deploy-content-writer | 多人使用场景 |
| ℹ️ 下一阶段 | `langgraph.json` 部署 | deep_research | 正式部署时参考 |
| ❌ 暂不需要 | TypeScript/QuickJS | repl_swarm | 当前无 JS 需求 |
| ❌ 暂不需要 | Sandbox 执行 | deploy-coding-agent | 当前用 MiniMax |
| ❌ 暂不需要 | Supabase auth | deploy-content-writer | demo 阶段不需要 |

---

## 7. 跨示例架构模式分析（核心调用层）

以下分析不按业务场景划分，而是按**架构层**提取各示例的共同模式。

### 7.1 Prompt 管理策略

| 模式 | 代表示例 | 核心文件 | 做法 |
|------|---------|---------|------|
| **分层 Prompt** | deep_research | `prompts.py` | Workflow / Delegation / Researcher 三层独立 |
| **文件即 Prompt** | content-builder-agent | `AGENTS.md` + `skills/*/SKILL.md` | Prompt 写在飞书，不是代码里 |
| **模板 + 变量注入** | deep_research | `prompts.py:RESEARCHER_INSTRUCTIONS` | `{date}`、`{max_concurrent}` 等运行时填充 |

**我们的差距：** 当前 `TAX_SYSTEM_PROMPT` 是单层字符串，没有分层，没有变量注入，没有独立的 prompt 文件。

### 7.2 Tool 设计模式

| 模式 | 代表示例 | 做法 |
|------|---------|------|
| **思考型 Tool** | deep_research `think_tool` | Tool 不执行外部操作，只让模型输出反思文本，作为链路中的"暂停点" |
| **工具名→对象映射** | content-builder-agent `load_subagents()` | YAML 中写工具名，代码中做名字到函数对象的映射 |
| **`InjectedToolArg`** | deep_research `tavily_search` | LangChain 原生参数注入，tool 可自动接收 runtime 上下文 |

### 7.3 上下文加载策略

| 策略 | 代表示例 | 做法 |
|------|---------|------|
| **Always-loaded** | all | `memory=[...]` — 始终加载到 system prompt |
| **On-demand** | content-builder-agent `skills/` | 通过 `SkillsMiddleware` progressive disclosure |
| **文件系统外部化** | deep_research `write_file` + `read_file` | Agent 自己把中间结果存文件，避免 context 膨胀 |

### 7.4 Sub-agent 调度模式

| 模式 | 代表示例 | 做法 |
|------|---------|------|
| **串行单调度** | 大部分示例 | 一次委托一个 sub-agent |
| **并行 fan-out** | deep_research / rlm_agent | 同一轮多次 `task()` 调用，并发执行多个 sub-agent |
| **链式 PTC** | rlm_agent `PTC subagent chain` | sub-agent 完成后结果传入下一个，类似管道 |
| **YAML 外化** | content-builder-agent `subagents.yaml` | subagent 定义不在代码中，在配置中 |

### 7.5 部署与配置管理

| 模式 | 代表示例 |
|------|---------|
| `langgraph.json` 入口 | deep_research, deploy-coding-agent |
| `deepagents.toml` 部署配置 | deploy-content-writer, deploy-gtm-agent |
| `.env.example` 模板 | deep_research, deploy-content-writer |
| `pyproject.toml` + `uv.lock` 锁依赖 | deep_research, content-builder-agent |

### 7.6 错误与边界处理

| 模式 | 代表示例 | 做法 |
|------|---------|------|
| 文件系统权限声明 | content-builder-agent | 明确标注文件访问风险 |
| Tool 超时 | deep_research `fetch_webpage_content` | `timeout=10.0` |
| Hard limits | deep_research `RESEARCHER_INSTRUCTIONS` | 搜索次数上限 5，防止无限循环 |
| API key 检查 | content-builder-agent `web_search` | 缺少 key 时明确返回错误 |
