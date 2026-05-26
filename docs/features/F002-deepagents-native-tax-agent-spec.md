---
feature_ids: [F002]
related_features: [F001]
topics: [deepagents, tax-agent, planning, rag, agentic-rag]
doc_kind: spec
created: 2026-05-26
---

# F002: DeepAgents 原生税务 Agent 优化

> 状态: spec | 负责人: 待定

## 为什么

F001 证明了 POC 可以运行 DeepAgents 示例和税务 Agent E2E 管道。但 Part 2 中的几个概念当前是以项目层适配器实现的：

- 意图分类是 Agent 之前的业务分类
- 规划是由意图选择的静态模板
- RAG 是空操作的装饰器占位

下一阶段应使 Part 2 更贴近 DeepAgents 的原生执行模型，特别是原生规划和 Agent 式检索。

## 做什么

重构 Part 2 税务 Agent，使核心推理循环由 DeepAgents 驱动，而非静态预计算计划。

### 范围内

1. 用 DeepAgents 原生规划路径替换静态规划器驱动的提示词构建。
   - Agent 应被指示使用其原生规划行为分解工作。
   - 运行时验证应捕获 Agent 使用规划的证据，例如流式输出中的 `write_todos` 工具事件。

2. 用实际的检索工具替换空操作的 RAG 装饰器。
   - 通过 `create_deep_agent(tools=[...])` 注册检索工具。
   - 从仓库中提交的小型本地税务知识语料库开始。
   - 检索结果必须包含源标识符，以便生成结构化引用。

3. 重新定位意图分类。
   - 如有用，保留 `definition` / `rate` / `compliance` 作为业务报告元数据。
   - 不要将分类器用作主要规划开关。
   - 不要将意图分类描述为 DeepAgents 原生能力。

4. 改进输出质量。
   - 从最终的 Markdown/JSON 中剥离模型推理标签（如 `<think>...</think>`）。
   - 使用检索结果填充 JSON `citations` 字段。
   - 保留 Markdown 和 JSON 输出作为公开产物。

### 范围外

- 生产级税法知识库。
- 外部向量数据库或托管的 RAG 服务。
- 专家法律/税务验证。
- 除非单独要求，否则不完整重跑本地 Ollama/vLLM。

## 验收标准

1. [ ] 存在概念记录，明确区分 DeepAgents 原生能力与项目适配器。
2. [ ] Part 2 不再依赖静态 `DefaultPlanner` 模板驱动回答执行。
3. [ ] 至少一次 Part 2 运行时验证捕获 DeepAgents 原生规划证据，如 `write_todos` 工具事件。
4. [ ] RAG 实现为注册的 DeepAgents 工具，而非回答后的空操作装饰器。
5. [ ] 基于检索的回答在 JSON 输出中包含结构化引用元数据。
6. [ ] 最终的 Markdown/JSON 输出不包含泄漏的推理标签，如 `<think>...</think>`。
7. [ ] 现有测试通过，新测试覆盖规划器移除、检索工具注册、引用提取和推理标签清理。
8. [ ] E2E 验证从 `sample_input.txt` 生成 Markdown 报告和 JSON 报告。

## 依赖

- `deepagents >= 0.6.3`
- F001 验证中使用的 MiniMax OpenAI 兼容运行时
- 现有 Part 2 模块：
  - `question_extractor.py`
  - `intent_classifier.py`
  - `planner.py`
  - `rag_decorator.py`
  - `agent_executor.py`
  - `output_formatter.py`

## 建议架构

```text
sample_input.txt / input.docx
  -> question_extractor
  -> 可选的意图元数据
  -> AgentExecutor
       -> create_deep_agent(
            tools=[retrieve_tax_context],
            system_prompt=带规划 + 引用规则的税务提示词
          )
       -> 原生规划/工具循环
  -> output_formatter
       -> 剥离推理标签
       -> Markdown
       -> 带引用的 JSON
```

## 实现说明

### 规划

静态 `Planner` 可暂时保留以兼容，但主 E2E 路径应停止将静态计划步骤注入用户提示词。

推荐的运行时证据：

- 使用 `agent.stream(..., version="v2")` 或 `agent.stream_events(..., version="v3")`
- 捕获工具事件
- 对多步骤税务问题断言至少出现一个规划相关事件

### 检索工具

从简单的本地工具开始：

```python
def retrieve_tax_context(query: str) -> list[dict]:
    return [
        {
            "source_id": "vat-temporary-regulations",
            "title": "中华人民共和国增值税暂行条例",
            "snippet": "...",
        }
    ]
```

这足以证明 DeepAgents 工具路径，而无需引入向量数据库。

### 输出格式化

格式化器应将引用视为结构化数据，而不仅仅是模型答案中的文本。

最小的 JSON 结构：

```json
{
  "question": "...",
  "intent": "definition",
  "answer": "...",
  "citations": [
    {
      "source_id": "vat-temporary-regulations",
      "title": "中华人民共和国增值税暂行条例"
    }
  ]
}
```

## 风险

- 工具调用行为取决于模型遵从度。运行时测试应使用使检索成为必要的提示词。
- DeepAgents 事件格式可能因 `stream` / `stream_events` 版本而异。测试应将事件解析隔离到一个小型辅助函数中。
- 小型本地语料库可以证明机制，但不能证明税法的完整性。

## 开放问题

- 意图分类应放在 Agent 执行前仅用于报告，还是移至回答生成后作为输出元数据？
- F002 应完全移除 `Planner`，还是保留为遗留适配器并附加测试证明主路径未使用它？
- 第一个检索语料库应是手工制作的税务片段，还是从公开法律参考文献生成？
