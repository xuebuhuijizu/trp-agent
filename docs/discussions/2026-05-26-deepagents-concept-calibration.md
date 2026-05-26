---
feature_ids: [F001, F002]
topics: [deepagents, planning, intent-classification, rag, tax-agent]
doc_kind: discussion
created: 2026-05-26
---

# DeepAgents 概念校准

## 目的

在启动下一阶段之前，我们澄清了当前 E2E 流程中三个易混淆的概念：

- 意图分类（intent classification）
- 规划（planning）
- RAG

目标是区分 DeepAgents 原生能力与项目层适配器及演示脚手架。

## 信息来源

- DeepAgents 概述：规划与任务分解、子 Agent、文件系统、记忆、人机交互。
  <https://docs.langchain.com/oss/python/deepagents/overview>
- DeepAgents 上下文工程与记忆：通过文件系统、记忆文件、Store 后端和工具管理上下文。
  <https://docs.langchain.com/oss/python/deepagents/context-engineering>
  <https://docs.langchain.com/oss/python/deepagents/memory>
- LangChain 检索/RAG：检索通过运行时外部知识增强生成，可以是两步式或 Agent 式。
  <https://docs.langchain.com/oss/python/langchain/retrieval>

## 概念对比

| 概念 | DeepAgents / LangChain 含义 | 当前项目含义 | 分类 | 差距 |
|---|---|---|---|---|
| 意图分类 | 不是独立的 DeepAgents 原生原语。可以通过模型推理、工具、结构化输出或应用层路由实现。 | `IntentClassifier` 在 Agent 运行前将税务问题映射为 `definition`、`rate` 或 `compliance`。 | 项目适配器 | 不应将其描述为 DeepAgents 特性。 |
| 规划 | DeepAgents 原生任务分解，通过 `write_todos` 等内置规划行为实现，Agent 可在执行过程中创建和更新任务状态。 | `Planner` 根据意图标签返回静态三步模板，然后注入到用户提示词中。 | 演示脚手架 / 项目适配器 | 展示类似规划的体验，但非 DeepAgents 原生规划。 |
| RAG | LangChain 检索模式。在 DeepAgents 风格的 Agent 中，检索通常应作为 Agent 需要时可调用的工具或上下文源暴露。 | `RAGDecorator` 暴露了未来的适配器接口，但默认的 `NoopRAG` 不返回任何文档。 | 占位适配器 | 当前 E2E 未执行真正的检索增强生成。 |

## 当前 E2E 流程解读

当前 Part 2 E2E 流程验证了以下管道：

```text
输入文本
  -> 问题提取
  -> 项目层意图分类
  -> 静态项目规划器
  -> DeepAgents 回答执行
  -> 可选的空操作 RAG 装饰
  -> Markdown/JSON 输出
```

这是一个有效的 POC 管道，但只有回答执行步骤直接由 Part 2 中的 DeepAgents 驱动。

## 建议的下一方向

下一阶段，通过改变管道形态使 Part 2 更贴近 DeepAgents：

```text
输入文本
  -> 问题提取
  -> 带有原生规划 + 检索工具的 DeepAgents Agent
  -> 输出格式化器
```

意图分类可以保留为报告元数据，但不应用来声称 DeepAgents 原生的路由或规划能力。

RAG 应成为通过 `create_deep_agent(tools=[...])` 注册的实际检索工具，而不是回答生成后的空操作装饰器。

## 已知输出质量问题

当前生成的输出证明管道可运行，但也显示两个质量缺口：

- 模型推理标签如 `<think>...</think>` 泄漏到最终报告中
- JSON `citations` 数组为空，即使回答正文包含税法依据文字

这些不是 F001 POC 的阻塞项，但在达到演示级输出或外部审查前应解决。
