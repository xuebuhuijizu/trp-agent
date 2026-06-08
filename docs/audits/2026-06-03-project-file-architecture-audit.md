---
topics: [architecture, file-audit, part2-tax-agent]
doc_kind: audit
created: 2026-06-03
feature_ids: [F004, F005, F006]
---

# 项目逐文件架构审计

## 审计范围

本报告审计 `git ls-files` 中的所有 tracked 文件，重点回答：

- 文件是否必要。
- 是否支持未来扩展。
- 当前方法/内容是否可精简。
- 当前目录是否合理，是否符合 4A 架构。
- 内容长度是否过长或过短。

只读证据：

- 当前 HEAD：`573be16 docs: add file audit, fix doc paths, split reference layer`
- 分支状态：`master...origin/master`
- tracked 文件数量：按 `git ls-files` 审计
- 当前 `part2-tax-agent/tax_agent` tracked 主结构：`agent/`、`business/`、`delivery/`、`runtime/`

非 tracked 结构噪音：

- `part2-tax-agent/tax_agent/__pycache__/` 已清理。它不是 Git 文件，但会干扰肉眼验收；后续如测试重新生成，不应进入 Git。

## 总体结论

代码主目录已经从旧 `domain/` / `service/` / `io/` 切到 4A 结构；本轮修订进一步删除了 `legacy/`、旧 config import、旧 runtime protocol/import wrapper 和旧 `retrieve_tax_context` tool 名。

当前剩余问题不是“旧目录还在 Git 里”，而是：

1. `runtime/executor.py` 过长，混合了执行边界、兼容 API、prompt 构造、artifact 组装、state 序列化和 reasoning 清洗。
2. `business/references/` 已拆出主实现，但需要继续保持 model/provider/manager/tool 的单一职责边界。
3. 测试仍有可拆分空间，尤其是 `test_tax_agent.py` 和 F004 相关大文件。

## 高优先级发现

### 已修复: 文档结构与实际目录不一致

- `docs/guides/part2-tax-agent-runtime-architecture.md` 已移除当前结构中的旧目录兼容层。
- `docs/guides/part2-tax-agent-current-runtime.md` 已移除 `legacy/` 和旧 config/tool 兼容描述。
- `delivery/batch_delivery/batch_io/question_extractor` 路径错误已修为 `delivery/batch_io/question_extractor`。

影响：铲屎官按架构图 2.2 验收时会继续看到“文档说有旧目录，但代码删了”的矛盾。

当前结论：文档应继续保持“旧目录已删除，旧能力已迁到 business/ 和 delivery/”的唯一表述。

### 已修复: Reference Layer 主实现藏在 `_legacy_reference_layer.py`

`business/references/manager.py`、`models.py`、`providers.py` 已承载各自实现，`_legacy_reference_layer.py` 已删除。

影响：已解除。后续扩展 provider、model、manager 时应继续在对应文件内演进，不再创建 legacy wrapper。

当前结构：

- `business/references/models.py`
- `business/references/providers.py`
- `business/references/manager.py`

`tools.py` 保留为 DeepAgents tool adapter，当前唯一 tool 名为 `find_tax_authorities`。

### P1: `runtime/executor.py` 过长且职责偏多

`runtime/executor.py` 约 370 行，虽然仍在 Runtime Adapter 层，但内部职责过宽：

- `AgentExecutor`
- `ExecutionResult`
- `ReasoningFilter`
- compatibility `execute(...)`
- prompt 构造
- artifact 构造
- tool event 收集
- structured response 提取
- checkpoint state 序列化

建议拆分为：

- `runtime/executor.py`：只保留 public runtime boundary。
- `runtime/output_cleaning.py`：`ReasoningFilter`。
- `runtime/result_mapping.py`：structured result、artifact、tool event 映射。
- compatibility `execute(...)` / `_build_prompt(...)` 若仅测试兼容，应删除或改为测试 fixture；不再移动到 `legacy/`。

### 已修复: 兼容模块过多但没有删除条件

以下文件已删除：

- `runtime/agent_executor.py`
- `runtime/ag_ui_protocol.py`
- `runtime/sse_protocol.py`
- `runtime/response_strategy.py`
- `tax_agent/config.py`
- `business/references/_legacy_reference_layer.py`
- `legacy/planner.py`
- `legacy/rag_decorator.py`

当前结论：不再保留这些 deprecated compatibility 文件；测试中增加“旧入口不存在”约束，防止回流。

### P2: 根目录/Part 2 根目录脚本归类可更清晰

`check_langfuse_observability.py`、`check_opengauss_compat.py`、`check_sqlite_checkpoint_persistence.py` 属于运维/兼容验证脚本，放在 `part2-tax-agent/` 根目录可以运行方便，但从架构清晰度看，更适合迁入 `part2-tax-agent/scripts/` 或 `tools/`。

## 逐文件审计

说明：

- 必要性：保留 / 暂留 / 可删 / 占位。
- 扩展性：好 / 一般 / 弱 / 不适用。
- 精简性：合理 / 可精简 / 过长 / 过短。
- 位置：合理 / 可调整 / 不合理。

### 根目录

| 文件 | 行数 | 必要性 | 扩展性 | 精简性 | 位置与架构判断 |
|---|---:|---|---|---|---|
| `.env.example` | 8 | 保留 | 一般 | 偏短 | 合理。应补齐 F004/F005/F006 相关 env 示例，如 checkpoint、Langfuse、API port。 |
| `.gitignore` | 25 | 保留 | 好 | 合理 | 合理。已覆盖缓存和输出类目录，但应确认 `__pycache__` 本地清理。 |
| `AGENTS.md` | 25 | 保留 | 一般 | 合理 | 合理。仓库治理入口，当前短小可用。 |
| `CLAUDE.md` | 25 | 保留 | 一般 | 合理 | 合理。多 provider 入口，内容重复可接受。 |
| `GEMINI.md` | 25 | 保留 | 一般 | 合理 | 合理。与 `CLAUDE.md`/`KIMI.md` 重复，后续可由模板生成。 |
| `KIMI.md` | 25 | 保留 | 一般 | 合理 | 合理。同上。 |
| `BACKLOG.md` | 13 | 保留 | 弱 | 偏短 | 合理但过短。只列 active feature，缺少“架构清理后续项”。 |
| `README.md` | 116 | 保留 | 好 | 合理 | 合理。作为项目入口必要；需持续同步实际结构。 |
| `pyproject.toml` | 24 | 保留 | 一般 | 合理 | 合理。建议补 pytest 配置，降低 Windows 临时目录问题。 |

### docs

| 文件 | 行数 | 必要性 | 扩展性 | 精简性 | 位置与架构判断 |
|---|---:|---|---|---|---|
| `docs/SOP.md` | 19 | 保留 | 一般 | 偏短 | 合理。作为 SOP 索引可用，但应链接 feature lifecycle 和 review flow。 |
| `docs/architecture/4a-architecture.md` | 177 | 保留 | 好 | 合理 | 合理。是当前架构真相源；迁移映射表保留旧路径作为历史映射是合理的。 |
| `docs/decisions/.gitkeep` | 0 | 占位 | 不适用 | 合理 | 合理。保持 decisions 目录。 |
| `docs/discussions/.gitkeep` | 0 | 占位 | 不适用 | 合理 | 合理。若已有 discussion 文件，可删除 `.gitkeep`。 |
| `docs/features/.gitkeep` | 0 | 占位 | 不适用 | 合理 | 合理。若已有 feature 文件，可删除 `.gitkeep`。 |
| `docs/discussions/2026-05-26-deepagents-concept-calibration.md` | 48 | 保留 | 一般 | 合理 | 合理。概念校准记录，支持架构决策。 |
| `docs/discussions/2026-05-30-runtime-capability-review.md` | 153 | 保留 | 好 | 合理 | 合理。F004/F006 背景材料。 |
| `docs/discussions/2026-06-01-deepagents-evolution-options.md` | 182 | 保留 | 好 | 合理 | 合理。路线讨论。 |
| `docs/discussions/2026-06-01-interaction-mode-design.md` | 346 | 保留 | 一般 | 过长 | 合理但偏长。建议拆出最终决策摘要，历史讨论留原文。 |
| `docs/discussions/2026-06-01-phase-close-and-next-stage.md` | 126 | 保留 | 一般 | 合理 | 合理。阶段收口记录。 |
| `docs/features/TEMPLATE.md` | 16 | 保留 | 一般 | 偏短 | 合理。建议补 AC、决策、验证证据字段。 |
| `docs/features/F001-deepagents-poc-spec.md` | 75 | 保留 | 一般 | 合理 | 合理。历史 spec。 |
| `docs/features/F002-deepagents-native-tax-agent-spec.md` | 139 | 保留 | 好 | 合理 | 合理。DeepAgents-native 边界真相源。 |
| `docs/features/F003-audit-trace-and-domain-skills-spec.md` | 172 | 保留 | 好 | 合理 | 合理。skills/audit trace 背景。 |
| `docs/features/F004-conversation-runtime-persistence-observability-service-spec.md` | 214 | 保留 | 好 | 合理 | 合理但较长。可拆验收摘要。 |
| `docs/features/F005-reference-layer-spec.md` | 61 | 保留 | 好 | 合理 | 合理。Reference Layer 已完成主实现拆分；历史 spec 中的旧 tool 名保留为阶段记录。 |
| `docs/features/F006-ag-ui-interaction-protocol-spec.md` | 125 | 保留 | 好 | 合理 | 合理。AG-UI 唯一协议真相源。 |
| `docs/guides/2026-05-27-project-diff-and-migration-notes.md` | 232 | 保留 | 一般 | 偏长 | 合理。历史迁移记录，建议作为 archive guide。 |
| `docs/guides/agent-harness-design-principles.md` | 73 | 保留 | 好 | 合理 | 合理。架构边界说明清楚。 |
| `docs/guides/demo-walkthrough.md` | 234 | 保留 | 一般 | 偏长 | 合理。演示指南可保留；若频繁变更应拆“快速演示”和“完整演示”。 |
| `docs/guides/part2-tax-agent-current-runtime.md` | 104 | 保留 | 好 | 合理 | 合理但内容需修：仍残留旧三目录和错误路径。 |
| `docs/guides/part2-tax-agent-runtime-architecture.md` | 104 | 保留 | 好 | 合理 | 合理但内容需修：仍残留旧 compat 层和错误路径。 |
| `docs/guides/python-primer-for-java-devs.md` | 82 | 保留 | 一般 | 合理 | 合理。面向 Java 背景读者的辅助文档。 |
| `docs/references/deepagents-official-examples-reference.md` | 184 | 保留 | 好 | 合理 | 合理。外部能力映射参考。 |

### part1-capability-validation

| 文件 | 行数 | 必要性 | 扩展性 | 精简性 | 位置与架构判断 |
|---|---:|---|---|---|---|
| `part1-capability-validation/examples/__init__.py` | 2 | 可删 | 不适用 | 过短 | 若 examples 不作为 package import，可删除。 |
| `part1-capability-validation/examples/01_file_tools.py` | 41 | 保留 | 一般 | 合理 | 合理。DeepAgents 文件工具能力验证。 |
| `part1-capability-validation/examples/02_sub_agent.py` | 62 | 保留 | 一般 | 合理 | 合理。sub-agent 示例。 |
| `part1-capability-validation/examples/03_planning.py` | 41 | 保留 | 一般 | 合理 | 合理。规划示例，但应确认与当前 DeepAgents API 同步。 |
| `part1-capability-validation/examples/04_memory.py` | 70 | 保留 | 一般 | 合理 | 合理。memory 示例。 |
| `part1-capability-validation/examples/05_tool_calling.py` | 52 | 保留 | 一般 | 合理 | 合理。tool calling 示例。 |
| `part1-capability-validation/examples/06_human_in_loop.py` | 67 | 保留 | 一般 | 合理 | 合理。HITL 示例。 |
| `part1-capability-validation/examples/07_streaming.py` | 41 | 保留 | 一般 | 合理 | 合理。streaming 示例。 |
| `part1-capability-validation/examples/08_event_streaming.py` | 54 | 保留 | 一般 | 合理 | 合理。event streaming 示例。 |
| `part1-capability-validation/examples/09_permissions.py` | 48 | 保留 | 一般 | 合理 | 合理。权限示例。 |

### part2 根入口与运行脚本

| 文件 | 行数 | 必要性 | 扩展性 | 精简性 | 位置与架构判断 |
|---|---:|---|---|---|---|
| `part2-tax-agent/__init__.py` | 0 | 可删 | 不适用 | 过短 | 目录名含 `-`，不能作为常规 Python package；若无 import 需求可删。 |
| `part2-tax-agent/app.py` | 6 | 保留 | 好 | 合理 | 合理。ASGI thin entrypoint。 |
| `part2-tax-agent/main.py` | 48 | 保留 | 好 | 合理 | 合理。CLI thin entrypoint。 |
| `part2-tax-agent/check_langfuse_observability.py` | 83 | 保留 | 一般 | 合理 | 必要的运维验证脚本；建议移到 `scripts/`。 |
| `part2-tax-agent/check_opengauss_compat.py` | 116 | 保留 | 一般 | 合理 | 必要的兼容性 spike；建议移到 `scripts/`。 |
| `part2-tax-agent/check_sqlite_checkpoint_persistence.py` | 88 | 保留 | 一般 | 合理 | 必要的 checkpoint 验证脚本；建议移到 `scripts/`。 |
| `part2-tax-agent/requirements.txt` | 10 | 保留 | 一般 | 合理 | 合理。与 `pyproject.toml` 重复但方便局部安装。 |
| `part2-tax-agent/sample_input.txt` | 2 | 保留 | 弱 | 偏短 | 合理。演示输入，但应增加多轮/法规引用样例。 |
| `part2-tax-agent/memories/AGENTS.md` | 4 | 保留 | 弱 | 偏短 | 合理。DeepAgents memory 输入太短，建议补适用边界和不确定性偏好。 |

### skills 与 seed data

| 文件 | 行数 | 必要性 | 扩展性 | 精简性 | 位置与架构判断 |
|---|---:|---|---|---|---|
| `skills/audit-intent-inference/SKILL.md` | 11 | 保留 | 一般 | 偏短 | 合理。可补输入/输出格式。 |
| `skills/audit-intent-inference/refs/intent-taxonomy.json` | 32 | 保留 | 一般 | 合理 | 合理。seed data。 |
| `skills/audit-scenario-recognition/SKILL.md` | 11 | 保留 | 一般 | 偏短 | 合理。可补场景匹配规则。 |
| `skills/audit-scenario-recognition/refs/scenarios.json` | 47 | 保留 | 一般 | 合理 | 合理。seed data。 |
| `skills/historical-question-matching/SKILL.md` | 11 | 保留 | 一般 | 偏短 | 合理。可补复用边界。 |
| `skills/historical-question-matching/refs/history_cases.json` | 38 | 保留 | 一般 | 合理 | 合理。seed data。 |
| `skills/solution-generation/SKILL.md` | 10 | 保留 | 一般 | 偏短 | 合理。可补方案结构约束。 |
| `skills/solution-generation/templates/solution-outline.md` | 8 | 保留 | 一般 | 偏短 | 合理。模板较薄。 |
| `skills/tax-finance-logic-decomposition/SKILL.md` | 11 | 保留 | 一般 | 偏短 | 合理。可补术语拆解示例。 |
| `skills/tax-finance-logic-decomposition/refs/terms.json` | 74 | 保留 | 好 | 合理 | 合理。seed data 扩展性最好。 |

### tax_agent/agent

| 文件 | 行数 | 必要性 | 扩展性 | 精简性 | 位置与架构判断 |
|---|---:|---|---|---|---|
| `tax_agent/__init__.py` | 0 | 保留 | 不适用 | 合理 | 合理。package marker。 |
| `tax_agent/agent/__init__.py` | 0 | 保留 | 不适用 | 合理 | 合理。package marker。 |
| `tax_agent/agent/context_policy.py` | 7 | 保留 | 一般 | 偏短 | 合理。后续可承载 skills/memory/filesystem policy。 |
| `tax_agent/agent/graph.py` | 23 | 保留 | 好 | 合理 | 合理。Agent Harness 装配入口。 |
| `tax_agent/agent/instructions.py` | 4 | 保留 | 一般 | 偏短 | 合理。当前 prompt 过短，长期应转移更多规则到 skills/memory。 |
| `tax_agent/agent/tool_manifest.py` | 3 | 保留 | 好 | 合理 | 合理。tool exposure 单一真相源。 |
| `tax_agent/config.py` | 3 | 已删除 | 弱 | 过短 | 旧 pre-migration config import，已删除；当前唯一 config 入口是 `tax_agent/runtime/config.py`。 |

### tax_agent/business

| 文件 | 行数 | 必要性 | 扩展性 | 精简性 | 位置与架构判断 |
|---|---:|---|---|---|---|
| `tax_agent/business/__init__.py` | 0 | 保留 | 不适用 | 合理 | 合理。package marker。 |
| `tax_agent/business/analysis/__init__.py` | 0 | 保留 | 不适用 | 合理 | 合理。package marker。 |
| `tax_agent/business/analysis/intent_classifier.py` | 44 | 保留 | 一般 | 合理 | 合理。确定性分类保留为业务元数据，不驱动主规划。 |
| `tax_agent/business/analysis/tax_context.py` | 138 | 保留 | 一般 | 可精简 | 合理。多个 matcher 可拆成 `terms.py`、`scenarios.py`、`history.py`，但当前规模可接受。 |
| `tax_agent/business/answers/__init__.py` | 0 | 保留 | 不适用 | 合理 | 合理。package marker。 |
| `tax_agent/business/answers/models.py` | 18 | 保留 | 好 | 合理 | 合理。业务输出契约。 |
| `tax_agent/business/references/__init__.py` | 0 | 保留 | 不适用 | 合理 | 合理。package marker。 |
| `tax_agent/business/references/_legacy_reference_layer.py` | 24 | 已删除 | 弱 | 过短 | 旧 Reference Layer compatibility wrapper，已删除。 |
| `tax_agent/business/references/manager.py` | 29 | 保留 | 好 | 合理 | 合理。承载 `ReferenceManager` 与默认 manager。 |
| `tax_agent/business/references/models.py` | 56 | 保留 | 好 | 合理 | 合理。承载 Citation/ReferenceItem/ReferenceBundle。 |
| `tax_agent/business/references/providers.py` | 59 | 保留 | 好 | 合理 | 合理。承载 provider protocol 与本地 seed provider。 |
| `tax_agent/business/references/tools.py` | 68 | 保留 | 好 | 合理 | 合理。DeepAgents tool adapter 与 citation extraction。 |

### tax_agent/runtime

| 文件 | 行数 | 必要性 | 扩展性 | 精简性 | 位置与架构判断 |
|---|---:|---|---|---|---|
| `tax_agent/runtime/__init__.py` | 0 | 保留 | 不适用 | 合理 | 合理。package marker。 |
| `tax_agent/runtime/ag_ui.py` | 164 | 保留 | 好 | 合理 | 合理。AG-UI event 投影边界清楚。 |
| `tax_agent/runtime/ag_ui_protocol.py` | 2 | 已删除 | 弱 | 过短 | 旧 AG-UI import wrapper，已删除。 |
| `tax_agent/runtime/agent_executor.py` | 11 | 已删除 | 弱 | 过短 | 旧 executor import wrapper，已删除。 |
| `tax_agent/runtime/audit_trace.py` | 137 | 保留 | 一般 | 合理 | 位置可接受，但 audit trace 更像 observability 子能力，可考虑并入 `runtime/observability/` 包。 |
| `tax_agent/runtime/checkpointing.py` | 152 | 保留 | 好 | 合理 | 合理。checkpoint 工厂复杂度可接受。 |
| `tax_agent/runtime/config.py` | 18 | 保留 | 好 | 合理 | 合理。runtime env/config。 |
| `tax_agent/runtime/conversation.py` | 34 | 保留 | 好 | 合理 | 合理。HTTP/SSE/batch 对话 schema。 |
| `tax_agent/runtime/executor.py` | 370 | 保留但需拆分 | 一般 | 过长 | 位置合理，内部职责过多。建议拆 mapping/cleaning/legacy。 |
| `tax_agent/runtime/observability.py` | 56 | 保留 | 好 | 合理 | 合理。Langfuse adapter。 |
| `tax_agent/runtime/response_strategy.py` | 11 | 已删除 | 弱 | 过短 | 旧 InteractionMode compatibility module，已删除。 |
| `tax_agent/runtime/sse.py` | 6 | 保留 | 一般 | 合理 | 合理。SSE 文本渲染独立。 |
| `tax_agent/runtime/sse_protocol.py` | 3 | 已删除 | 弱 | 过短 | 旧 SSE import wrapper，已删除。 |

### tax_agent/delivery

| 文件 | 行数 | 必要性 | 扩展性 | 精简性 | 位置与架构判断 |
|---|---:|---|---|---|---|
| `tax_agent/delivery/__init__.py` | 0 | 保留 | 不适用 | 合理 | 合理。package marker。 |
| `tax_agent/delivery/batch.py` | 56 | 保留 | 好 | 合理 | 合理。batch delivery 编排。 |
| `tax_agent/delivery/http_api.py` | 105 | 保留 | 好 | 合理 | 合理。FastAPI routes 边界清楚。 |
| `tax_agent/delivery/batch_io/__init__.py` | 0 | 保留 | 不适用 | 合理 | 合理。package marker。 |
| `tax_agent/delivery/batch_io/output_formatter.py` | 105 | 保留 | 一般 | 合理 | 位置合理。可将 report render 与 single answer format 拆开，但当前可接受。 |
| `tax_agent/delivery/batch_io/question_extractor.py` | 40 | 保留 | 一般 | 合理 | 合理。文件输入解析只在 delivery。 |

### tax_agent/legacy

`tax_agent/legacy/` 已删除。重构目标是移除旧静态 planner、旧 RAG decorator 和历史 demo 包袱；后续不再为这些旧能力保留 package。

### tests

| 文件 | 行数 | 必要性 | 扩展性 | 精简性 | 位置与架构判断 |
|---|---:|---|---|---|---|
| `tests/__init__.py` | 0 | 可删 | 不适用 | 过短 | 若 tests 不需要 package import，可删。 |
| `tests/test_architecture_migration.py` | 37 | 保留 | 好 | 合理 | 必要。锁定 4A 结构和旧概念移除。 |
| `tests/test_f003_audit_and_skills.py` | 95 | 保留 | 一般 | 合理 | 合理。覆盖 audit trace 和 skills seed。 |
| `tests/test_f004_reasoning_guard.py` | 80 | 保留 | 好 | 合理 | 必要。覆盖 reasoning-only 风险。 |
| `tests/test_f004_runtime.py` | 196 | 保留 | 好 | 偏长 | 合理。可按 checkpoint/observability/batch 拆分。 |
| `tests/test_f004_service_routes.py` | 188 | 保留 | 好 | 偏长 | 合理。可按 chat/batch/state 拆分。 |
| `tests/test_f004_streaming.py` | 226 | 保留 | 好 | 偏长 | 合理。AG-UI 行为测试，可拆成 protocol 与 route。 |
| `tests/test_f005_reference_layer.py` | 72 | 保留 | 好 | 合理 | 必要。Reference Layer contract。 |
| `tests/test_legacy_cleanup.py` | 27 | 保留 | 好 | 合理 | 必要。防止旧架构回流。 |
| `tests/test_part1_deepagents_examples.py` | 69 | 保留 | 一般 | 合理 | 合理。保护 Part 1 示例与官方 API 对齐。 |
| `tests/test_tax_agent.py` | 296 | 保留但应拆分 | 一般 | 过长 | 不理想。混合 extractor/classifier/planner/formatter/RAG/executor，应按模块拆。 |

## 建议清理顺序

### 第一批：立即修文档一致性

1. 修 `docs/guides/part2-tax-agent-runtime-architecture.md`：
   - 删除 `domain/ service/ io/` compat 层描述。
   - 修 `delivery/batch_delivery/batch_io`。
   - 将 compatibility 表改为“旧目录已删除，旧 import 不再支持；legacy 仅隔离历史实验”。
2. 修 `docs/guides/part2-tax-agent-current-runtime.md`：
   - 删除 `tax_agent/domain/*` / `service/*` / `io/*` 行。
   - 删除“不要从 domain/service/io 开始读”。
   - 删除“旧 import 兼容只能留在 wrapper 中”。
3. 清理本地 `__pycache__`。

### 第二批：Reference Layer 命名收口

1. `_legacy_reference_layer.py` 已拆到 `models.py`、`providers.py`、`manager.py`。
2. `_legacy_reference_layer.py` 已删除，不保留 legacy adapter。
3. tests import 已更新到正式模块。

### 第三批：Runtime 过宽拆分

1. 从 `runtime/executor.py` 拆出 `ReasoningFilter`。
2. 拆出 result/artifact mapping。
3. 删除 compatibility `execute(...)` / static plan prompt，或改为测试 fixture；不再移动到 `legacy/`。

### 第四批：测试结构整理

1. 拆 `test_tax_agent.py`。
2. 拆 F004 大测试文件。
3. 为已删除的 compat/deprecated 入口保留不存在性测试，避免永久兼容层回流。

## 当前最小验收口径

如果只判断“目录是否已经按架构图 2.2 迁移”，代码层面通过；如果判断“整个项目每个文件都与架构设计一致”，剩余主要风险是 `runtime/executor.py` 过宽、部分测试文件过长，以及部分历史讨论文档仍保留旧概念作为历史上下文。
