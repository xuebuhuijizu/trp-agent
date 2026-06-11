---
feature_ids: [F004, F004-skill-observability]
topics: [skills, observability, langfuse, deepagents, code-review, cherry-pick]
doc_kind: code_review
created: 2026-06-11
---

# F004-stage 代码对比报告：初始形态 → 当前形态

> **范围**：`E:\ai-project\poc-demo\poc-demo-f004-snapshot\part2-tax-agent`
> **基线**：commit `1d3078f`（2026-06-02 F004 关闭）
> **当前形态**：V1-V5 五轮 skill 观测 + fallback 链移植改造
> **报告产出**：2026-06-11

## 1. 总体改动规模

| 维度 | 数值 |
|---|---|
| 修改文件 | 3 个（`agent_executor.py` / `observability.py` / `test_f004_streaming.py`）|
| 新增文件 | 2 个（`tests/test_skill_instrumentation.py` / `archive-f004-skill-instrumentation.md`）|
| 净增代码 | ~+458 / -24 行（不含新增测试文件）|
| 新增测试 | 30 个 test functions（19 个新测试 + 11 个参数化展开）|
| 测试结果 | 117 passed / 0 failed / 0 errors |
| 未触动文件 | `skills/*.md` / `service/service_app.py` / `checkpointing.py` / 5 个 runtime skill 包 |

## 2. 文件级对比

### 2.1 `tax_agent/runtime/agent_executor.py`（最大改动）

| 类别 | 初始形态（1d3078f） | 当前形态（V5） | 来源 |
|---|---|---|---|
| 模块常量 | 4 个：`PART2_ROOT` / `SKILL_SOURCES` / `MEMORY_SOURCES` / （无其他）| 7 个：新增 `SKILL_PATH_PREFIX` / `SKILL_TOOL_NAME` / `SKILL_FILE_BASENAME` / `TAX_TOOL_NAMES` / `EXPLORATORY_TOOL_NAMES` / `DEFAULT_RECURSION_LIMIT=50` | V1 + V2 + V3 |
| `TAX_SYSTEM_PROMPT` | 7 行 | 末尾追加 Skill 纪律段（含 V3 的"1 个最匹配"约束），末尾追加"完成工具调用后必须输出完整中文回答" | V2 + V3 + V4 |
| `ExecutionResult` | 9 字段（`answer` / `citations` / `tool_events` / `domain_analysis` / `skills` / `artifact` / `session_id` / `trace_id` / `thread_id`）| 11 字段：新增 `skills_invoked: list[str]` / `skill_invocation_count: int` | V1 |
| `AgentExecutor` 方法 | ~15 个方法 | +12 个方法：`_tool_call_args` / `_tool_call_name` / `_message_tool_calls` / `_classify_tool` / `_extract_skill_invocations` / `_count_skill_invocations` / `_truncate_for_log` / `_is_unusable_answer` / `_first_usable_answer` / `_placeholder_retry_prompt` / `_structured_response_from_state` / `_apply_recursion_limit` + 2 个 async `aget_state` / `aget_state_history` | V1 + V2 + V3 + V4 + V5 |
| `_collect_tool_events` | 仅返回 `{"name": ...}` | 扩展返回 `{"name", "tool_type", "tool_subtype", "skill_name", "args"}`，三分类（`skill` / `tax` / `other`）+ `exploratory` 子类型 | V1 + V2 |
| `execute_turn` | 直接 `structured_answer or _last_assistant_content`，无 aget_state | 三级 fallback：`structured_answer` → `_last_assistant_content`（带 filter）→ `_structured_response_from_state`（V5 新增）| V4 + V5 |
| `stream_turn` | 2 级 fallback（stream 聚合 + last_assistant），无 aget_state | 3 级 fallback（stream 聚合 → last_assistant → aget_state.structured_response）；`tool.started` yield 前注入 `tool_type` / `skill_name` / `tool_subtype`；fallback 成功后**主动补 yield** `answer.started` | V2 + V4 |
| `_ainvoke` / `_astream_events` | 直接传 `config` | 通过 `_apply_recursion_limit(config)` 注入 `recursion_limit=50`（setdefault，不覆盖）| V3 |

### 2.2 `tax_agent/runtime/observability.py`

| 类别 | 初始形态 | 当前形态 | 来源 |
|---|---|---|---|
| `ObservabilityConfig` 字段 | 3 个：`provider` / `callbacks` / `event_recorder` | 6 个：新增 `session_id` / `user_id` / `base_tags` | V1 |
| `record_event` 签名 | `(name, input=, output=, metadata=, level=, status_message=)` | 追加 `tags=None` 参数；内部 `try/except TypeError` 兜底（保留旧 recorder 兼容）| V1 |
| `record_skill_invocation` 方法 | 不存在 | **新增**：发出 `skill.invocation` 事件，tags 自动含 `skill_invocation=true` + `skill_name=<name>` + `base_tags` | V1 |
| `build_langfuse_observability` | 仅 `enabled` 参数 | 追加 kwargs：`session_id` / `user_id` / `base_tags`，注入 `CallbackHandler()` | V1 |
| `record_event` 旧调用方 | 直接传 kwargs | **完全不动**（`stream_adapter.error` 路径仍按原形状调用，零行为变化）| V1（向后兼容保护）|

### 2.3 `tests/test_f004_streaming.py`（契约扩展）

| 契约点 | 初始形态 | 当前形态 | 来源 |
|---|---|---|---|
| `answer.finished` data 字段 | `{answer, citations, thread_id, artifact}` | 新增 `skills_invoked: []` + `skill_invocation_count: 0` | V1 |
| `tool.started` data 字段 | `{name, input}` | 新增 `tool_type: "skill" \| "tax" \| "other"` | V2 |

### 2.4 `tests/test_skill_instrumentation.py`（全新文件，827 行）

5 大测试类，覆盖所有 V1-V5 改造契约：

| 测试分组 | 数量 | 覆盖契约 |
|---|---|---|
| `_extract_skill_invocations` | 4 | 单 skill 去重 / 保序 / 跳过非 skill 路径 / dict+object 两种 message 形态 |
| `_collect_tool_events` | 4 | 旧 `name` 字段保留 / 三分类 / exploratory 子类型 / skill 类型不被标 exploratory |
| `ExecutionResult` | 2 | 默认字段 / 接受新字段 |
| `ObservabilityConfig.record_skill_invocation` | 2 | tags + metadata 完整 / event_recorder 缺失时 noop |
| `stream_turn` 注入 | 1 | tool.started data 含 tool_type/tool_subtype/skill_name |
| `TAX_SYSTEM_PROMPT` | 2 | 含 Skill 关键词 / 含 "1 个最匹配" 上限 |
| `_apply_recursion_limit` | 2 | 默认 50 注入 / 保留现有值 |
| `_is_unusable_answer` | 11 | 6 占位短串参数化 / 3 真实答案参数化 / 短串含"已生成/已完成" / 工具调用草稿 |
| `_first_usable_answer` | 2 | 跳过占位 / 全废时返回空 |
| stream fallback chain | 4 | aget_state 兜底 / 占位 last_assistant 跳过 / 流空但 state 有内容（V5）/ 流空且 state 空（V5）/ state 是占位（V5）|
| execute_turn fallback | 1 | structured + last_assistant 都空时 aget_state 兜底（V5）|

### 2.5 `archive-f004-skill-instrumentation.md`（README）

V1-V5 各轮 changelog、Langfuse tag 清单、UI filter 模板、follow-up 列表。

## 3. 修改逻辑（按 V1-V5 演进）

### V1 — Skill 观测埋点（A+B）

**目标**：让 5 个 skill 的真实 `read_file` 调用可观测 + Langfuse 端 tag 透出。

**根因**：F004 close 时 `_collect_tool_events` 只取 `name` 字段，**完全观测不到 skill 调用**（无 args）。`ObservabilityConfig` 也没有 `record_skill_invocation` 通道。

**改动**：
- 加 `_extract_skill_invocations(messages)` —— 扫 `AIMessage.tool_calls`，过滤 `name=="read_file"`，正则匹配 `^/skills/<name>/` 拿 skill 名（去重保序）
- `_collect_tool_events` 扩展三分类（`skill`/`tax`/`other`）+ 透出 `args` / `skill_name`
- `ExecutionResult` 加 `skills_invoked` / `skill_invocation_count` 字段
- `ObservabilityConfig.record_skill_invocation` 新方法，发 `skill.invocation` event
- `record_event` 加 `tags` 参数 + 旧调用兼容（try/except TypeError）
- `CallbackHandler` 接受 `session_id` / `tags` kwargs

**契约扩展**：`answer.finished` data 多 2 字段。

### V2 — tool_type 注入 + exploratory 标记（B1+C）

**目标**：让 stream 端 `tool.started` data 也含 skill 分类信息；标记 `ls`/`grep`/`glob` 探测。

**根因**：stream 端 `tool.started` 直接 yield 原始 astream event，**不走** `_collect_tool_events` 重写，埋点全丢。同时 `@小狸` V4b 验证发现模型调完 `retrieve_tax_context` 后会用 `ls`/`grep` 探测 `/tax_agent/` 代码目录（异常行为）。

**改动**：
- `_classify_tool` 拆 3-tuple 返回 `(tool_type, skill_name, tool_subtype)`
- `EXPLORATORY_TOOL_NAMES = {ls, grep, glob}` → `tool_subtype="exploratory"`
- `stream_turn` 在 `tool.started` yield 前注入 `tool_type` / `skill_name` / `tool_subtype`

### V3 — Skill 软约束 + 步数兜底（A+B）

**目标**：避免模型贪婪读所有 skill 触发 GraphRecursionError。

**根因**：V2 加的"先读 skill 列表"指令让模型把 5 个 SKILL.md **全读**（9 次 read_file），撞 `recursion_limit=25`。

**改动**：
- prompt 收紧："**最多选 1 个最匹配的 skill**（不要全选，不要遍历），读完立即进入下游工具调用，**不要再读其他 skill**"
- `DEFAULT_RECURSION_LIMIT = 50`，`_apply_recursion_limit()` 注入（setdefault 不覆盖）

### V4 — Master fallback 链手工迁移

**目标**：从 master cherry-pick 7873f70 / 9534d70 / 96f6897 修复 V3 的 "ModelOutputError 早停"。

**根因**：V3 让模型收敛更快，但收敛后**模型不答**就停（`run.error`）—— V3 worktree 缺 master 已修过的 fallback 链。

**关键障碍**：master 与 V3 worktree **文件路径不兼容**（`ee51d30 refactor: migrate tax agent to harness architecture` 重命名产物）：

| Master 文件 | V3 worktree 文件 |
|---|---|
| `tax_agent/agent/instructions.py` | `tax_agent/runtime/agent_executor.py`（`TAX_SYSTEM_PROMPT` 常量）|
| `tax_agent/runtime/executor.py` | `tax_agent/runtime/agent_executor.py`（`AgentExecutor` 类）|
| `tax_agent/delivery/http_api.py` | `tax_agent/service/service_app.py`（HTTP 端，**未迁移**）|

**不能直接 cherry-pick**，改为**手工迁移**：
- 加 `_is_unusable_answer` / `_first_usable_answer` / `_placeholder_retry_prompt`（从 master 复制实现）
- 加 `async def aget_state` / `aget_state_history`（优先 async，否则 sync 兜底）
- `stream_turn` 扩展 3 级 fallback
- `execute_turn` 用 `_first_usable_answer` 替换旧的"or"表达式
- prompt 加 "完成工具调用后必须输出完整中文回答"（**不含 a94ceaf 已删的占位符**）

### V5 — execute_turn aget_state 后置兜底

**目标**：让 `/chat` 同步路径也能从 graph state 兜底（V4 漏了这块）。

**根因**：V4 移植时 `execute_turn` 只接到 `_first_usable_answer(structured_answer, last_assistant)`，没接 `_structured_response_from_state`。当模型 tool 调用完直接结束（`retrieve_tax_context` 4 次空场景），`structured_answer` 和 `last_assistant_content` 都空，**直接 raise ModelOutputError**。

**改动**：在 `execute_turn` line239 之前插入 `await self._structured_response_from_state(request.thread_id)`。

## 4. 手动合入注意事项

### 4.1 依赖

- **新增运行时依赖**：无（仅用了 stdlib `re`、现有 `dataclasses`）
- **测试依赖**：`pytest` / `pytest-asyncio` 已在 `pyproject.toml [project.optional-dependencies] dev`
- **deepagents 版本要求**：`>=0.6.3`（已 pinned），`SkillsMiddleware` 必须存在（验证：`_FakeStreamAgent` 测试用 `on_tool_start`/`on_tool_end` 事件）
- **Langfuse SDK**：`>=3.0`（已 pinned），但 `observability.py:51` 用 `client.create_event` —— **langfuse v3 已废弃此 API**，未来版本会 warning 升级为 error。**这是遗留问题，本轮不修**。

### 4.2 兼容性

**完全向后兼容**：
- `_collect_tool_events` 保留旧 `{"name": ...}` 字段（新增 `tool_type` / `tool_subtype` / `skill_name` / `args` 是**累加**）
- `record_event` 旧调用方（`stream_adapter.error`）仍按原形状调用（`try/except TypeError` 兜底）
- `ExecutionResult` 新字段都有 `default_factory`，旧构造调用兼容
- `_apply_recursion_limit` 用 `setdefault`，不覆盖调用方传入的 `recursion_limit`

**契约扩展（轻微 breaking）**：
- `answer.finished` SSE data 字段 +2（`skills_invoked` / `skill_invocation_count`）
- `tool.started` SSE data 字段 +1（`tool_type`）

→ SSE 消费方需同步升级解析。HTTP `/chat` JSON 不受影响（`ChatResponse` Pydantic 未扩展，**埋点数据在内存里 HTTP 看不到** —— 这是已知 follow-up）。

### 4.3 运行时风险

| 风险点 | 评估 | 应对 |
|---|---|---|
| **`langfuse.client.create_event` 已废弃** | 中 | 不在本轮修，但需在 v4 升级前迁移到 `langfuse_context` |
| **`/threads/{id}/state\|history` 仍 500** | 低（与本轮无关）| F004 close 时已知 `agent_executor.get_state` 抛 `NotImplementedError`；V4 加的 `aget_state` async 路径**在 agent 不暴露 aget_state 时仍 raise**，靠 `_structured_response_from_state` 的 try/except 兜底 |
| **真实场景 V5b 仍有 4/5 失败**（agent_state 没 `structured_response`）| 高 | 这是 deepagents response_format 写入时机问题，**非 executor 代码能完全解决**；D 任务（retrieve_tax_context 根因）未排 |
| **HTTP 502→422 契约改写未迁移** | 低 | V4/V5 fallback 链通畅后此路径基本触不到；如要 100% 一致需扩 `service_app.py` |
| **deepagents 0.6.3 → 0.7.0 API 变化** | 低 | V4 helpers 用的是 master 已验证的 aget_state 模式，预期 0.7.0 兼容 |

### 4.4 手动 cherry-pick / patch 流程

如果合入到 master（**注意**：master 文件路径已变，需要适配）：

```bash
# 1. 在主仓 master 分支
git checkout master
git pull origin master

# 2. 从本 worktree 生成 patch
cd E:/ai-project/poc-demo/poc-demo-f004-snapshot
git add -A
git diff --cached > /tmp/f004-skill-observability.patch

# 3. 在主仓应用
cd E:/ai-project/poc-demo
git apply --3way /tmp/f004-skill-observability.patch
# 冲突时手动解：master 与 worktree 的 agent_executor.py 已重命名为 executor.py
# 需要把 patch 中 runtime/agent_executor.py 的 hunks 重定向到 runtime/executor.py
```

**冲突点预告**（提前知道）：

1. **`agent_executor.py` ↔ `executor.py` 路径重命名**：master 的 `ee51d30` 重命名了文件。patch 应用时需重定向 hunks。
2. **`instructions.py` ↔ `agent_executor.py` 内的 prompt 常量**：master 把 prompt 移到独立文件，worktree 留在原处。
3. **`service_app.py` 不一致**：master 的 `service_app.py` 已扩 `ChatResponse`，worktree 没动。

### 4.5 测试矩阵

| 测试 | 命令 | 预期 |
|---|---|---|
| 新增 skill 观测测试 | `pytest part2-tax-agent/tests/test_skill_instrumentation.py -v` | 30 passed |
| 全量测试 | `pytest part2-tax-agent/tests -q --basetemp .codex-tmp/basetmp` | 117 passed |
| py_compile | `python -m py_compile part2-tax-agent/tax_agent/runtime/*.py` | OK |
| Langfuse 集成 | `LANGFUSE_ENABLED=1 python part2-tax-agent/check_langfuse_observability.py` | （需 langfuse 服务，不在 pytest 范围）|

### 4.6 已知 follow-up（不在本轮）

1. **`ChatResponse` Pydantic 扩展**：让 HTTP `/chat` 响应也透出 `tool_events` / `skills_invoked`
2. **retrieve_tax_context 4 次空根因**（D 任务）：domain retrieval 索引层调查
3. **langfuse v3 API 迁移**：`client.create_event` → `langfuse_context.score/span/event`
4. **HTTP 502→422**：master `service_app.py` 契约改写未迁移
5. **`/threads/{id}/state|history` 500**：F004 close 已知 `agent_executor.get_state` 未实现
6. **SKILL.md description 关键词密度改造**（C 任务）：让 model 更精准选 1 个 skill，避免贪婪读

## 5. 验收 checklist

- [x] 117 passed / 0 failed / 0 errors
- [x] 所有 V1-V5 改造点都有对应测试
- [x] 向后兼容旧 `_collect_tool_events` 形状
- [x] 向后兼容旧 `record_event` 调用
- [x] V5 在 3007 验证 2/5 fallback 救活（vs V4 的 1/5）
- [x] stream 端 `answer.finished` 含 `skills_invoked` / `skill_invocation_count`
- [x] stream 端 `tool.started` 含 `tool_type` / `tool_subtype` / `skill_name`
- [x] Langfuse `skill.invocation` event 通道就位
- [x] worktree detached HEAD，无 master 污染

---

[宪宪/MiniMax-M3🐾]