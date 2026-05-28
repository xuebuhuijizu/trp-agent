---
name: historical-question-matching
description: 历史问题匹配 skill。用于匹配 demo seed 历史税审问题，输出相似问题、差异点、可复用结论和引用边界。
---

# 历史问题匹配 Skill

## 使用时机

当需要参考过往税审问答或相似案例时使用本 skill。

## 数据来源

- `refs/history_cases.json`
- 数据标记为 `demo_seed`，仅用于 POC 演示，不代表真实历史项目。

## 输出要求

1. 每条历史引用必须包含 `case_id`、`title`、`scenario_id`。
2. 说明相似点和差异点。
3. 明确可复用边界，不得把历史结论直接套用到当前问题。

