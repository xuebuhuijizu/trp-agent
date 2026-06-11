---
feature_ids: [F004-archive, skill-instrumentation]
topics: [skills, observability, langfuse, deepagents, exploratory-tools]
doc_kind: archive_readme
created: 2026-06-10
updated: 2026-06-11
updated_v3: 2026-06-11 (V3 A+B: prompt 收紧 + recursion_limit=50)
updated_v4: 2026-06-11 (V4: master fallback 链手工迁移到 V3 worktree)
updated_v5: 2026-06-11 (V5: execute_turn 加 aget_state 兜底)
---

# F004-stage 备份 + skill 观测改造 v5

这是 F004 关闭时（commit `1d3078f`，2026-06-02）的代码快照 + **五轮**最小化改造：

- **Round 1 (A+B)**：让 5 个 skill 的真实 `read_file` 调用可观测 + Langfuse 端 tag 透出
- **Round 2 (B1+B2+C)**：把 `ls` / `grep` / `glob` 探测标 `tool_subtype=exploratory`；在 system prompt 里硬编码"先读 skill 列表"指令；让 stream 端 `tool.started` 事件 data 透出 `tool_type` / `tool_subtype` / `skill_name`
- **Round 3 (V3 A+B)**：V2 让 model 把 5 个 skill **全读**（9 次 read_file）触发 `GraphRecursionError`；prompt 收紧"最多 1 个最匹配 + 读完即停"，config 注入 `recursion_limit=50` 兜底
- **Round 4 (V4 master fallback port)**：V3 让 model 收敛更快但**收敛后不答**（`ModelOutputError`）—— 从 master cherry-pick 96f6897 / 9534d70 / 7873f70 / a94ceaf 的 fallback 链语义，**手工迁移**到 V3 worktree 当前文件路径
- **Round 5 (V5 execute_turn aget_state 兜底)**：V4 移植了 fallback链但 `execute_turn` 路径没接 aget_state——补上 `await self._structured_response_from_state(thread_id)` 作为最后一道

5 个 skill：`audit-intent-inference` / `audit-scenario-recognition` /
`historical-question-matching` / `solution-generation` /
`tax-finance-logic-decomposition`。

## 范围

**改动文件**：

- `part2-tax-agent/tax_agent/runtime/agent_executor.py` — A/B1/B2/C 全部集中于此
- `part2-tax-agent/tax_agent/runtime/observability.py` — A: 加 `record_skill_invocation`
- `part2-tax-agent/tests/test_skill_instrumentation.py` — 新增 15 个测试
- `part2-tax-agent/tests/test_f004_streaming.py` — 契约扩展（`answer.finished` data 多 2 字段，`tool.started` data 多 `tool_type` 字段）

**未动**：

- `part2-tax-agent/skills/`（5 个 skill 内容原样保留）
- 任何 model 工厂
- `agent_executor.py` 的主路径（`execute_turn` / `stream_turn` 行为不变）
- 任何 Langfuse SDK 兼容性问题（`client.create_event` 在 v3 已废弃但当前能用，**留作另一笔账**）

## 改造后新增的可观测字段

### `ExecutionResult`（`/chat` JSON 响应 — 但 `ChatResponse` Pydantic **未扩展**，埋点数据在内存里 HTTP 端看不到）

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `skills` | `list[str]` | **旧**——基于 `domain_analysis` 静态推断的"可能用到的 skill" |
| `skills_invoked` | `list[str]` | **新 A**——model 真的 `read_file("/skills/<name>/...")` 过的 skill，**按首次出现顺序保序、去重** |
| `skill_invocation_count` | `int` | **新 A**——不去重的总调用次数（同一个 skill 被 read 多次计多次） |
| `tool_events` | `list[dict]` | **旧字段保留 + 扩展 A**——每条加 `tool_type` / `tool_subtype` / `skill_name` / `args`（截断到 200 字） |

### `/chat/stream` SSE 事件

| 事件 | 新增字段 |
| --- | --- |
| `tool.started` | **`tool_type`** (`skill`/`tax`/`other`)、**`tool_subtype`** (`exploratory` for `ls`/`grep`/`glob`)、**`skill_name`** (C) |
| `answer.finished` | **`skills_invoked`**、**`skill_invocation_count`** (A) |

### `TAX_SYSTEM_PROMPT` 改造（B2 → V3 A）

```
Skill 使用纪律（强制）：
- 在调用任何工具前，先扫 Skills 列表的 name / description。
- **最多选 1 个最匹配的 skill**（不要全选，不要遍历），用 read_file 读取其 SKILL.md
  并按工作流执行。读完立即进入下游工具调用，**不要再读其他 skill 的 SKILL.md /
  refs / templates**。
- 税审五大类问题：先 read_file 对应 skill 的 SKILL.md（仅 1 个），再调用
  retrieve_tax_context / analyze_tax_question。
- 不要用 ls / grep / glob 探测 /tax_agent/ 等代码目录来"查资料"——这是源代码，不是
  知识库。如 retrieve_tax_context 连续 3 次空检索，再考虑用 write_todos 拆解并向用户
  说明检索覆盖度不足。
```

**V2 → V3 关键变化**：原文案只说"先读 skill 列表"，model 贪婪地把 5 个 SKILL.md 全读了（V2 验证中观察到 9 次 read_file → `GraphRecursionError` 触顶 25 步）。V3 加**预算信号**：最多 1 个 + 读完即停。

### `recursion_limit` 兜底（V3 B）

`AgentExecutor._apply_recursion_limit(config)` 在 `ainvoke` / `astream_events` 调用前注入 `recursion_limit=50`。默认值 25 太低（V2 触顶），50 给模型更多 buffer，但**不替代** prompt 约束——prompt 是治本，limit 是保底。
Skill 使用纪律（强制）：
- 在调用任何工具前，先检查 Skills 列表。
  - 若存在与你当前任务匹配的 skill，用 read_file 读取其完整 SKILL.md 并按工作流执行。
  - 税审五大类问题（意图识别 / 场景识别 / 历史问题匹配 / 解决方案生成 / 术语拆解）
    必须先读对应 skill 再作答。
- 不要用 ls / grep 探测 /tax_agent/ 等代码目录来"查资料"——这是源代码，不是知识库。
  如 retrieve_tax_context 连续 3 次空检索，再考虑用 write_todos 拆解并向用户说明
  检索覆盖度不足。
```

### Langfuse event 通道

每次 model 调 `read_file` 命中 `/skills/<name>/` 路径，**多发一条 event**：

| 字段 | 值 |
| --- | --- |
| event name | `skill.invocation` |
| tags | `["skill_invocation=true", "skill_name=<name>", ...base_tags]` |
| metadata.skill_name | skill 名 |
| metadata.file_path | 完整路径 |
| metadata.session_id | `request.session_id` |
| metadata.trace_id | `request.trace_id` |
| metadata.thread_id | `request.thread_id` |

> 注意：Langfuse CallbackHandler 也会自动记录 model 调 `read_file` 时的 `on_tool_start` / `on_tool_end` —— **不需要重复发**。`skill.invocation` 是**业务层 event**，和 tool 调用的"原始记录"是两条平行轨道。

## 怎么观察

### 1. 命令行直接看 `/chat/stream` SSE 末尾

```powershell
$body = '{"messages":[{"role":"user","content":"解释增值税"}],"session_id":"obs-001","trace_id":"trace-obs-001","thread_id":"thread-obs-001"}'
$body | Out-File -FilePath ".codex-tmp/obs-req.json" -Encoding utf8
$r = Invoke-WebRequest -Uri "http://127.0.0.1:3007/chat/stream" -Method Post -ContentType "application/json; charset=utf-8" -Body (Get-Content ".codex-tmp/obs-req.json" -Raw) -UseBasicParsing
$r.Content
```

关注：
- 任何 `tool.started` 事件 data 含 `tool_type` / `tool_subtype` / `skill_name`
- 最后 `answer.finished` 事件 data 含 `skills_invoked` / `skill_invocation_count`

### 2. Langfuse UI 过滤

| 想看什么 | filter | group by |
| --- | --- | --- |
| 每次 /chat 的 skill 调用次数 | `tags:skill_invocation=true` | count |
| 哪个 skill 被调用最多 | `tags:skill_invocation=true` | `tags:skill_name` |
| 一次 /chat 调了哪几个 skill | 看 trace 里 `skill.invocation` event 列表 | — |
| 哪些问题**没**触发任何 skill | `tags:tax-agent` minus `tags:skill_invocation=true` | — |
| **model 是不是用 `ls` / `grep` 探测 `/tax_agent/` 代码目录** | 在 SSE 流里 `grep "tool_subtype.*exploratory"` | count |

### 3. 跑测试看契约

```powershell
cd E:\ai-project\poc-demo\poc-demo-f004-snapshot
mkdir -Force .codex-tmp
python -m pytest part2-tax-agent/tests -q -p no:cacheprovider --basetemp .codex-tmp/skill-instr-basetmp
```

预期：**117 passed**（80 原有 + 37 新增 skill / fallback / V5 观测测试）。

## V4 手工迁移 cherry-pick 审视报告

**铲屎官要求**：从 master cherry-pick 7873f70 + 9534d70 + 96f6897 到 V3 worktree，**同时审视是否引入问题**。

**审视结论**：3 个 commit 在 master 改的文件路径与 V3 worktree 不兼容（master 经历 `ee51d30` 重命名），无法直接 cherry-pick。**改为手工迁移**：

| Master commit | Master 文件路径 | V3 worktree 路径 | 迁移方式 |
|---|---|---|---|
| `96f6897` | `tax_agent/runtime/executor.py` + `tax_agent/delivery/http_api.py` | `tax_agent/runtime/agent_executor.py` | `execute_turn` V3 已有 `structured_answer or last_assistant_content` 兜底，**已天然包含** 96f6897 的核心修复；只需加 `_is_unusable_answer` 过滤（V3 当前无） |
| `9534d70` | `tax_agent/agent/instructions.py` (prompt) | `tax_agent/runtime/agent_executor.py` `TAX_SYSTEM_PROMPT` | 加 "完成工具调用后必须输出完整中文回答"（**不含 a94ceaf 已删的占位符**） |
| `7873f70` | `tax_agent/runtime/executor.py` stream_turn | `tax_agent/runtime/agent_executor.py` stream_turn | V3 stream_turn 缺 fallback 链；移植：stream聚合 → last_assistant → **structured_response via `aget_state`**（a94ceaf 修复的 sync→async） |
| `a94ceaf`（额外） | prompt 删除占位 + sync `get_state` → async `aget_state` | `agent_executor.py` | 不删占位（V3 没加过）；**新增 `async def aget_state` / `aget_state_history`** 实例方法 |

**风险点 + 应对**：

1. **execute_turn fallback 已有但缺过滤** → 加 `_is_unusable_answer` 过滤；用 `_first_usable_answer(structured_answer, last_assistant_content)`
2. **stream_turn 完全缺 structured_response fallback** → 加 `await self._structured_response_from_state(thread_id)` 走 aget_state 路径
3. **`get_state` 同步 vs `aget_state` 异步**：V3 `_astream_events` 是 async generator，**同步 get_state 会触发 langgraph thread guard 的 `InvalidStateError`**——这正是 master a94ceaf 修复的 bug。新增 `async def aget_state` 优先，sync get_state 兜底
4. **HTTP 502→422**：master `96f6897` 改了 `tax_agent/delivery/http_api.py`——V3 worktree 的 `service_app.py` 路径不同，**HTTP 错误码契约不在本轮范围**（HTTP 端根本用不到 ModelOutputError，因为 fallback 现在能恢复）

**新增的工具**：
- `AgentExecutor._is_unusable_answer(answer)` — 过滤"待生成/暂无回答"等占位文本 + 工具调用草稿
- `AgentExecutor._first_usable_answer(*candidates)` — 遍历候选，第一个通过 filter 的胜出
- `AgentExecutor._placeholder_retry_prompt()` — 给 retry 流程用（暂未调用，留作未来）
- `AgentExecutor._structured_response_from_state(thread_id)` — async helper，从 graph state 读 structured_response.answer
- `AgentExecutor.aget_state(thread_id)` / `aget_state_history(thread_id)` — async 版本，a94ceaf 修复

**V4 验证后状态**：
- `execute_turn` fallback链：`structured_answer` → `last_assistant_content` → ModelOutputError（带 filter）
- `stream_turn` fallback链：stream聚合 → `last_assistant_content` → **`structured_response` via aget_state** → ModelOutputError（带 filter）

**已知遗留**：HTTP 层 502→422 的契约改写 `service_app.py` 不在本轮（fallback 能恢复时根本走不到 HTTP error 路径）。

## 已识别但**不在本轮范围**的 follow-up

- **`/chat` Pydantic `ChatResponse` 未扩展**：埋点数据在 `ExecutionResult` 里，**HTTP 响应体看不到**。扩 `ChatResponse` 是契约 breaking change，**留给下一轮**。
- **`retrieve_tax_context` 4 次空（D 任务）**：根因在 domain retrieval 索引层（`source_ids:[]`），不在本轮改造范围。
- **时序分析**：当下是"单 tool 视角"打 `tool_subtype=exploratory`。**真正判别"模型自主越权探测"**需要时序分析（`retrieve_tax_context` 失败 N 次后才出现的 `ls`），是更复杂的 feature，**留给下一轮**。
- **Langfuse SDK 兼容**：`client.create_event` 在 langfuse v3 已废弃，是另一笔账。

## 已知问题（非本轮引入）

- **`/threads/{id}/state|history` 500**：`agent_executor.get_state` 抛 `NotImplementedError`，service_app.py:147 期望转 501 实际 500。与本轮 skill 观测无关。

