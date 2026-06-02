---
feature_ids: [F005]
related_features: [F002, F003, F004]
topics: [reference-layer, citation, deepagents, tax-agent]
doc_kind: spec
created: 2026-06-02
---

# F005: Reference Layer 外部引用框架

> Status: spec | Owner: 宪宪

## Why

当前税务 Agent 已经完成 DeepAgents 原生接入、结构化输出、审计 trace、checkpoint、streaming 协议和 `InteractionMode` 的阶段性收口。下一阶段的瓶颈不再是“Agent 如何运行”，而是“Agent 依据什么材料回答、这些材料如何被标准化、引用、追踪和替换”。

历史上的 `retrieve_tax_context` 是演讲 demo 遗留工具名，它把法规检索、seed data、citation 提取和 Agent tool 命名绑在一起。F005 要把这个边界抽成 Reference Layer，让法规/政策、术语库、历史案例、税审场景、用户上传文件等材料都能以统一引用契约进入 Agent。

## What

F005 建立 Reference Layer 的第一版架构边界：

- 定义 `ReferenceProvider`：某一种引用来源的适配器。
- 定义 `ReferenceManager`：统一调度 provider、去重、排序、标准化。
- 定义 `ReferenceBundle`：一次引用检索的标准返回包。
- 定义 `Citation`：最终可进入 `TaxAnswer`、报告、artifact、audit trace 和 streaming event 的稳定引用字段。
- 第一版只落地一个 Agent tool：`find_tax_authorities`。
- `lookup_tax_terms`、`match_tax_cases`、`match_audit_scenarios`、`inspect_uploaded_reference` 进入设计文档，但不在第一版实现。

## Architecture Decisions

### Reference 范围

`Reference` 包括法规/政策、术语库、历史案例、税审场景、用户上传文件等。内部 seed data 也算 reference，条件是它会支撑回答并进入 citation 或 trace。

### Tool 粒度规则

Tool 粒度按 Agent 的行为语义切，不按旧函数名、不按 provider 数量、不按数据存储来源切。

- 新 provider：同一种 Agent 行为，换数据来源。
- 新 tool：Agent 行为语义发生变化。

示例：

- 本地法规 seed 替换为 RAG 法规库：新增 provider，不新增 tool。
- 法规依据检索扩展到历史案例匹配：新增 tool。
- 历史案例本地 JSON 替换为数据库案例库：新增 provider，不新增 tool。
- 用户上传文件分析：新增 tool，因为输入、失败模式和引用定位都不同。

### 第一版 Tool

第一版不保留 `retrieve_tax_context` 作为未来名称，改用：

```text
find_tax_authorities
```

它负责查找税务法规、政策和正式依据。旧的本地 seed data 作为 `LocalTaxAuthorityProvider` 接入 `ReferenceManager`。

### Citation 稳定字段

`Citation` 第一版稳定字段：

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

`metadata` 用于来源特有扩展，避免不同引用来源不断污染顶层 schema。

## Acceptance Criteria

- [ ] AC-1: 存在 Reference Layer 的核心 schema：`ReferenceProvider`、`ReferenceManager`、`ReferenceBundle`、`Citation`。
- [ ] AC-2: `find_tax_authorities` 作为第一版 Agent tool，替代 `retrieve_tax_context` 的长期语义位置。
- [ ] AC-3: 当前本地税务 seed data 通过 `LocalTaxAuthorityProvider` 接入，不再由 tool 直接理解数据结构。
- [ ] AC-4: `ReferenceManager` 负责 provider 调度、去重、排序和标准化。
- [ ] AC-5: `Citation` 至少包含本 spec 定义的稳定字段，并能进入最终 answer/artifact/audit trace。
- [ ] AC-6: streaming 的 tool event 能输出标准 citation/source 信息，不依赖旧 tool 私有 payload。
- [ ] AC-7: `lookup_tax_terms`、`match_tax_cases`、`match_audit_scenarios`、`inspect_uploaded_reference` 只在设计文档中定义边界，不在第一版实现。
- [ ] AC-8: 现有 F002/F003/F004 行为保持可验证，不因 tool rename 破坏结构化回答、citation、audit trace、streaming 协议。

## Dependencies

- F002: DeepAgents 原生税务 Agent 与结构化回答。
- F003: audit trace 与 domain skills。
- F004: conversation runtime、checkpoint、observability、streaming 协议和 `InteractionMode`。

## Risk

- Tool 粒度过细会让 Agent prompt 负担变重；第一版只实现 `find_tax_authorities` 控制复杂度。
- Tool 粒度过粗会把不同失败模式混在一起；后续新增 tool 必须基于行为语义变化，而不是 provider 数量。
- 旧测试可能仍绑定 `retrieve_tax_context` 名称；实现阶段需要用 TDD 明确迁移路径。
- `confidence` 容易被误解为法律确定性；第一版应定义为检索/匹配置信度，不代表税务结论正确率。

## Open Questions

- `confidence` 是 provider 直接给出，还是由 `ReferenceManager` 统一归一化？
- `Citation.locator` 是否需要第一版拆成结构化字段，例如 `article`、`paragraph`、`page`、`path`？
- 旧 `retrieve_tax_context` 是否保留兼容 shim，还是直接迁移测试和调用方？

## Links

- [F002 DeepAgents 原生税务 Agent](F002-deepagents-native-tax-agent-spec.md)
- [F003 审计 trace 与 domain skills](F003-audit-trace-and-domain-skills-spec.md)
- [F004 Conversation runtime](F004-conversation-runtime-persistence-observability-service-spec.md)
- [2026-06-01 DeepAgents evolution options](../discussions/2026-06-01-deepagents-evolution-options.md)
- [2026-06-01 phase close and next stage](../discussions/2026-06-01-phase-close-and-next-stage.md)
