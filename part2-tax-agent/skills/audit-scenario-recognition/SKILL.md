---
name: audit-scenario-recognition
description: 业务场景识别 skill。用于根据 demo seed 税审场景库匹配问题所属业务场景，输出匹配理由、置信度和替代场景。
---

# 业务场景识别 Skill

## 使用时机

当问题描述某类交易、发票、收入、扣除、优惠、关联交易或纳税人身份变化时使用本 skill。

## 数据来源

- `refs/scenarios.json`
- 数据标记为 `demo_seed`，仅用于 POC 演示，不是正式审计场景库。

## 输出要求

1. 输出最匹配的 `scenario_id` 和场景标题。
2. 说明命中的关键词和匹配理由。
3. 给出置信度。
4. 至少保留一个可能的替代场景或说明无替代场景。

