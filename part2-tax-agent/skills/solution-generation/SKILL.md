---
name: solution-generation
description: 解决方案生成 skill。用于基于税审场景、历史问题样例、术语拆解和检索来源生成结构化处理建议。
---

# 解决方案生成 Skill

## 使用时机

当问题需要形成可执行税审处理建议时使用本 skill。

## 约束

1. 不单独凭空生成结论。
2. 必须引用场景识别、历史问题匹配、术语拆解或检索工具结果。
3. 如事实不足，优先列出补充材料，而不是强行下结论。
4. demo seed 数据只能作为参考框架。

## 输出结构

使用 `templates/solution-outline.md` 的结构输出。

