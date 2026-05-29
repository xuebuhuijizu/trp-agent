---
feature_ids: [F003]
related_features: [F001, F002]
topics: [deepagents, audit-trace, skills, tax-agent, demo]
doc_kind: spec
created: 2026-05-28
---

# F003: 审计 Trace 与税审领域 Skills 增强

> 状态: completed
> 负责人: 宪宪
> 完成提交: `c125666 feat: F003 audit trace checkpoint and domain skills`

## 为什么

F002 已经把 Part 2 税务 Agent 从“静态规划 + 空 RAG 占位”推进到更贴近 DeepAgents 原生执行模型：原生规划证据、检索工具、Skills、Memory 和 Structured output 都已经接入。

下一阶段需要补两类能力：

1. **可追溯性**：当前输出能证明“最后答了什么”，但还不够证明“Agent 为什么这么答、用了哪些技能、调用了哪些工具、引用了哪些资料、每一步耗时和失败点是什么”。演示和后续审计都需要 trace。
2. **领域技能丰富度**：当前 `tax-answering` skill 只能算示例性回答规范，不足以展示税审场景下的专业拆解、场景识别、历史案例参考、方案生成和质询意图分析。

## 做什么

新增 F003，分两条主线推进：

1. 审计记录：分成本地 audit trace 和 LangGraph checkpoint 两层实现。前者面向业务审计可读性，后者面向 graph state 的恢复、回放和调试。
2. 领域 skills：删除或替换当前示例性 `tax-answering` skill，新增 5 个税审领域 skill，并为每个 skill 配套最小示例数据和可验证输出。

## 能力分类

| 能力 | 分类 | 说明 |
|---|---|---|
| DeepAgents `skills=[...]` 加载机制 | DeepAgents-native | 继续使用原生 skills progressive disclosure。 |
| LangGraph checkpoint | LangGraph-native | 保存 graph state snapshot，用于恢复、回放、time travel debugging。 |
| 本地审计 JSONL/JSON 报告 | project adapter | 为内网和离线演示保留本地审计账本。 |
| 税务/财务术语库 | demo-only scaffolding -> project adapter | 第一版自行生成，后续可替换为真实业务词库。 |
| 税审场景库 | demo-only scaffolding -> project adapter | 第一版自行生成，后续由业务专家维护。 |
| 历史问题库 | demo-only scaffolding -> project adapter | 第一版自行生成，后续可接入真实历史问答。 |
| 解决方案生成规则 | project adapter | 基于场景、历史问题和检索依据组织输出。 |
| 税审问题意图识别 | project adapter | 不是 DeepAgents 原生能力，作为领域分析 skill 表达。 |

## 范围内

### 1. 审计 Trace 与 Checkpoint

F003 审计只做两个层面：

1. **本地 audit trace**：面向业务审计和演示，可读、可导出、可和最终报告互相定位。
2. **LangGraph checkpoint**：面向技术调试和运行恢复，保存 graph state snapshot，支持 state history / replay / time travel debugging。

LangSmith 不作为 F003 实现范围，只作为未来线上观测的可选方向。

#### 1.1 本地 audit trace

新增本地审计记录，至少覆盖：

- `run_id`
- `question_id`
- 输入问题文本或脱敏文本
- 输入文件路径、文件哈希、问题提取结果
- 模型配置摘要：provider、model、temperature、max_tokens
- 触发的 skill 名称
- tool calls：工具名、参数摘要、返回源标识、错误信息
- retrieved sources：`source_id`、`title`、命中原因
- structured response：answer、citations、confidence 或 quality flags
- `write_todos` / planning 事件摘要
- latency：总耗时、模型耗时、工具耗时
- output paths：Markdown / JSON / trace 文件路径
- error chain：异常类型、异常消息、是否 fallback

审计输出建议：

```text
part2-tax-agent/output/
  tax_report_YYYYMMDD_HHMMSS.md
  tax_report_YYYYMMDD_HHMMSS.json
  trace_YYYYMMDD_HHMMSS.jsonl
  trace_YYYYMMDD_HHMMSS.summary.json
```

#### 1.2 LangGraph checkpoint

新增 LangGraph checkpointer 配置，用于保存每次 graph / agent 执行的 state snapshot。

第一版建议：

- 本地开发优先使用 SQLite checkpointer 或等价本地 checkpointer。
- 每次运行生成稳定 `thread_id`，并与 `run_id` 关联。
- 本地 audit trace summary 中记录 `thread_id` 和 checkpoint backend 类型。
- checkpoint 不作为业务审计报告直接展示；它服务于恢复、回放和 debug。
- checkpoint 可能包含原始 state，默认只保存在本地，不上传外部平台。

### 2. 五个税审领域 Skill

当前 `part2-tax-agent/skills/tax-answering/SKILL.md` 可以视为示例内容。F003 应将其删除或替换为更细分的领域 skills。

建议新增目录：

```text
part2-tax-agent/skills/
  tax-finance-logic-decomposition/
    SKILL.md
    refs/terms.yaml
  audit-scenario-recognition/
    SKILL.md
    refs/scenarios.yaml
  historical-question-matching/
    SKILL.md
    refs/history_cases.json
  solution-generation/
    SKILL.md
    templates/solution-outline.md
  audit-intent-inference/
    SKILL.md
    refs/intent-taxonomy.yaml
```

#### Skill 1: 税务/财务逻辑拆解

目标：

- 匹配术语库。
- 从问题中提取税务/财务术语。
- 拆解涉及的税种、主体、交易、时间、金额、税率、凭证、合规风险。
- 输出“问题 -> 术语 -> 税务逻辑链 -> 待确认事实”。

第一版术语库可自行生成，建议至少包含：

- 增值税、企业所得税、印花税、个税、附加税、小规模纳税人、一般纳税人
- 销项税额、进项税额、抵扣、留抵退税、视同销售、纳税调整
- 发票、合同、收入确认、成本费用、关联交易、税收优惠

#### Skill 2: 业务场景识别

目标：

- 根据税审场景库做语义匹配。
- 判断问题属于哪类税审场景。
- 输出匹配场景、匹配理由、置信度、可能的替代场景。

第一版税审场景可自行生成，建议至少包含：

- 收入确认与增值税纳税义务发生时间
- 发票取得与进项抵扣风险
- 成本费用税前扣除风险
- 小规模/一般纳税人身份切换
- 税收优惠适用条件
- 关联交易和转让定价风险
- 跨期收入/成本确认
- 资产处置与视同销售

#### Skill 3: 历史问题匹配

目标：

- 匹配曾经处理过的历史问题。
- 给出相似问题、相似点、差异点、可复用结论和不可复用边界。
- 历史问题引用必须带 `case_id`、`title`、`scenario_id`。

第一版历史问题可自行生成，数量建议 10-20 条，覆盖主要税审场景。

#### Skill 4: 解决方案生成

目标：

- 基于税审场景识别和历史问题样例生成解决方案。
- 输出可执行建议，而不是泛泛解释。
- 结构建议：
  - 事实前提
  - 适用场景
  - 历史参考
  - 税务逻辑
  - 处理建议
  - 风险提示
  - 需要补充的材料
  - 引用来源

该 skill 不应单独凭空生成结论，必须引用场景识别、历史问题匹配或检索工具结果。

#### Skill 5: 税审问题意图识别

目标：

- 分析税审问题背后可能的质询逻辑。
- 输出“可能在问什么、为什么这么问、审计关注点、需要反问或补证的事实”。

注意：

- “揣测”必须以假设形式表达，不得断言用户真实意图。
- 每个意图需给出置信度和触发词。
- 至少输出一个替代解释，避免单一路径误判。

## 范围外

- 不接入真实企业税务数据。
- 不把自行生成的术语库、场景库、历史问题库包装成权威知识库。
- 不要求第一版接入外部向量数据库。
- 不把 LangSmith 云端 trace 纳入 F003 第一版实现范围。
- 不在 F003 中实现生产级权限、用户体系或审计合规认证。

## 补充说明与需要澄清的问题

### 建议补充说明 1：审计数据的隐私边界

需要明确 audit trace 和 checkpoint 是否允许保存原始税审问题和原始文档片段。

建议默认：

- 本地 audit trace 可保存原文，但应支持脱敏开关。
- LangGraph checkpoint 只保存在本地目录或本地数据库。
- `.env` 增加开关，例如 `AUDIT_TRACE_REDACTION=none|strict`。
- 对外传输压缩包时，默认不包含 checkpoint 数据库和真实 audit trace。

### 建议补充说明 2：五个 Skill 的执行关系

五个 skill 不应全部强制串行执行。建议主路径为：

```text
问题
  -> 税审问题意图识别
  -> 税务/财务逻辑拆解
  -> 业务场景识别
  -> 历史问题匹配
  -> 解决方案生成
  -> 审计 trace 汇总
```

但 DeepAgents skills 本身是按任务匹配加载的 progressive disclosure，因此实现时应通过 orchestrator prompt / native planning / tests 保证关键场景触发，而不是把所有 skill 文本塞进 system prompt。

### 建议补充说明 3：自行生成数据的身份

术语库、税审场景和历史问题第一版可以自行生成，但必须标注为 demo seed data。

建议字段：

```text
source_type: demo_seed
version: 2026-05-28
maintainer: poc-demo
review_status: unreviewed
```

### 建议补充说明 4：删除旧 Skill 的时机

不建议先删 `tax-answering` 再做新 skill。建议：

1. 新增五个 skill 和测试。
2. 确认主路径能触发新 skill。
3. 将旧 `tax-answering` 标记为 deprecated。
4. 删除旧 skill 或将其内容合并到 `solution-generation`。

## 验收标准

1. [ ] 存在本地审计 trace 输出，且每个问题至少记录 `run_id`、`question_id`、skill 触发、tool calls、citations、latency 和 error chain。
2. [ ] trace 输出和最终 Markdown/JSON 报告能通过 `run_id` 互相定位。
3. [ ] 存在 LangGraph checkpoint 配置，能通过 `thread_id` 保存并读取执行 state history。
4. [ ] audit trace summary 记录 `thread_id`、checkpoint backend 类型和 checkpoint 是否启用。
5. [ ] 新增 5 个领域 skill，且每个 skill 有独立 `SKILL.md` 和至少一个配套 `refs/` 或 `templates/` 文件。
6. [ ] 删除或废弃当前示例性 `tax-answering` skill，并在文档中说明替代关系。
7. [ ] 术语库、税审场景库和历史问题库均存在第一版 demo seed data，并明确不是权威知识库。
8. [ ] 税务/财务逻辑拆解 skill 能输出术语命中、逻辑链和待确认事实。
9. [ ] 业务场景识别 skill 能输出场景匹配、理由、置信度和替代场景。
10. [ ] 历史问题匹配 skill 能输出相似历史问题、差异点和引用边界。
11. [ ] 解决方案生成 skill 能综合场景、历史问题和检索来源输出结构化方案。
12. [ ] 税审问题意图识别 skill 使用假设和置信度表达质询逻辑，不断言用户真实意图。
13. [ ] 新增测试覆盖 trace schema、checkpoint 配置、skill 文件存在性、seed data 加载、主路径输出字段和旧 skill 迁移。

## 建议实施顺序

### 第一刀：审计骨架

- 新增 `audit_trace.py` 或等价模块。
- 定义 `AuditTraceEvent` / `AuditTraceSummary` schema。
- 新增 LangGraph checkpointer 配置，生成并记录 `thread_id`。
- 在 `main.py` 或 `AgentExecutor` 外层记录 run/question/tool/answer/error 事件。
- 输出 `trace_*.jsonl` 和 `trace_*.summary.json`。
- 测试 trace 文件可生成并能关联报告；checkpoint state history 可读取。

### 第二刀：Seed Data 与工具化匹配

- 新增术语库、税审场景库、历史问题库。
- 新增确定性匹配函数：
  - `match_terms`
  - `match_audit_scenario`
  - `match_historical_questions`
- 先用普通 Python 函数测试，避免把可确定逻辑交给模型猜。

### 第三刀：五个 Skill

- 新增五个 `SKILL.md`。
- 每个 skill 描述必须具体，便于 DeepAgents 匹配。
- 为每个 skill 配 refs/templates。
- 替换或废弃旧 `tax-answering`。

### 第四刀：Agent 主路径整合

- 调整 system prompt，让 Agent 使用原生规划选择合适 skill。
- 必要时新增工具，让 skill 能调用确定性匹配结果。
- 输出中增加：
  - `terms`
  - `scenario_matches`
  - `historical_references`
  - `solution`
  - `intent_hypotheses`

### 第五刀：验证与演示

- 单测：schema、checkpoint 配置、匹配函数、skill 文件、trace 关联。
- 集成测试：给定 sample input，生成报告 + trace。
- 演示文档：更新 `docs/guides/demo-walkthrough.md`，展示 trace 文件和五个 skill 如何被触发。

## 风险

- Skill 太多会导致匹配混乱。缓解：每个 `description` 写清触发条件，避免重叠。
- 自行生成数据容易被误解为真实税务知识。缓解：所有 seed data 标注 `demo_seed`。
- Trace/checkpoint 可能保存敏感内容。缓解：默认本地保存，压缩包迁移时默认排除真实审计数据和 checkpoint 数据库。
- 模型可能不稳定触发 skill。缓解：可确定逻辑做成工具，skill 负责解释和流程，不负责唯一事实来源。

## 参考资料

- DeepAgents Skills：<https://docs.langchain.com/oss/python/deepagents/skills>
- DeepAgents Context Engineering：<https://docs.langchain.com/oss/python/deepagents/context-engineering>
- LangGraph Persistence / Checkpoints：<https://docs.langchain.com/oss/python/langgraph/persistence>
- LangGraph Observability：<https://docs.langchain.com/oss/python/langgraph/observability>
