---
feature_ids: [F004]
related_features: [F002, F003]
topics: [interaction-mode, response-strategy, streaming, sse, adapter]
doc_kind: discussion
created: 2026-06-01
---

# InteractionMode 设计稿

## 结论先行

`InteractionMode` 是项目 adapter 层的入口语义，不是 DeepAgents/LangChain middleware。

它回答的是：

```text
调用方希望这次交互以什么形态呈现？
```

它不回答：

```text
Agent 内部怎么推理？
要不要注入 tool？
要不要改 system prompt？
要不要维护 agent state？
```

因此 `InteractionMode` 的落点应在 FastAPI route、SSE projector、response adapter、harness 这一层。DeepAgents/LangGraph 继续提供模型调用、tools、checkpoint、stream events；项目只负责把同一个底层执行能力投影成不同对外形态。

## 设计目标

1. 让调用方显式表达交互意图，避免 `/chat`、`/chat/stream`、`/batch` 被混成一个隐式猜测入口。
2. 把“是否流式”“是否输出 token delta”“是否要结构化最终产物”“是否批处理”从底层 Agent 能力里分离出来。
3. 保持协议稳定：外部只看到 `run.*`、`answer.*`、`tool.*`、`skill.*`、`batch.*`，不暴露内部 LangGraph event schema。
4. 先不做自动识别。启发式可以后置，当前先让 API/harness 明确传参。

## 已确认决策（2026-06-02）

1. `/chat/stream` 默认值为 `answer_stream`。
2. `structured_final` 第一版复用当前 `TaxAnswer`，把 `TaxAnswer` 视为当前已配置的结构化最终产物。
3. `progress_stream` 在 `answer.finished` 前发送“正在生成最终回答”的可观察事件；协议上用 `answer.started` 表达，UI 可把它翻译成“正在生成最终回答”。
4. `/batch` 第一版不做 SSE/job 语义，等批处理耗时和 UI 需求稳定后再决定。
5. 不允许 `/chat` 请求带 `interaction_mode=answer_stream` 后自动重定向到 `/chat/stream`；错误入口组合直接返回 `400`。
6. 消费者单入口 facade 当前不做，先保留清晰能力端点。
7. facade 的 `Accept` header / `interaction_mode` 分流机制先不考虑。
8. `progress_stream` 的 `answer.started` payload 暂时不加固定 `status` 字段。
9. `TaxAnswer` 是否演进为更强 artifact schema 之后再考虑。

## 实现状态（2026-06-02）

第一版已实现：

1. `ConversationRequest` / `BatchRequest` 接受可选 `interaction_mode`。
2. 新增 `ResponseStrategy` 解析与 route 级 mode 校验。
3. `/chat` 允许 `direct_text`、`structured_final`，拒绝 `answer_stream` / `progress_stream` / `batch`。
4. `/chat/stream` 允许 `answer_stream`、`progress_stream`，拒绝 `structured_final`。
5. `/batch` 只允许 absent 或 `batch`。
6. `progress_stream` 过滤 `answer.delta`，保留 `answer.started` / `answer.finished`。

未实现且已暂缓：

1. 消费者单入口 facade。
2. facade 的 `Accept` header / `interaction_mode` 分流机制。
3. `answer.started` payload 的固定 `status` 字段。
4. `TaxAnswer` 之外的新 artifact schema。
5. `/batch` job/SSE。

## 能力分类

| 能力 | 分类 | 说明 |
|---|---|---|
| `InteractionMode` 枚举 | project adapter | 对外入口语义，控制响应形态 |
| `ResponseStrategy` 解析 | project adapter | 把 mode 映射成 route、SSE、final response 策略 |
| `answer.delta` 开关 | project adapter | 是否向调用方发送内容增量 |
| `structured_final` artifact | project adapter | 最终结构化输出，基于现有 `response_format` 或项目 schema |
| `/batch` 独立入口 | project adapter | 显式批处理，不包装成 DeepAgents skill |
| DeepAgents `write_todos` / tools / checkpoint | DeepAgents-native / LangGraph-native | InteractionMode 不改变这些内部能力 |

## 最小枚举

建议第一版只支持 5 个显式值：

```text
direct_text
progress_stream
answer_stream
structured_final
batch
```

### `direct_text`

面向普通问答。

```text
入口：POST /chat
输出：一次性 JSON response
内容：answer + citations + checkpoint + observability
SSE：无
answer.delta：无
```

适用场景：

- 用户问一个短问题。
- UI 不需要展示中间过程。
- 调用方只关心最终回答文本。

### `progress_stream`

面向“用户需要知道系统在工作，但不需要逐字看回答”的场景。

```text
入口：POST /chat/stream
输出：SSE
事件：run.* + tool.* + skill.* + answer.started + answer.finished
answer.delta：不发送
```

适用场景：

- 回答可能耗时较长。
- UI 想显示“正在检索法规 / 正在调用工具 / 正在生成答案”。
- 前端不想处理大量 token chunk。

协议示例：

```text
event: run.started
data: {"session_id":"sess-001","trace_id":"trace-001","thread_id":"thread-001"}

event: tool.started
data: {"name":"retrieve_tax_context"}

event: tool.finished
data: {"name":"retrieve_tax_context","source_ids":["vat-regulation"]}

event: answer.started
data: {"thread_id":"thread-001"}

event: answer.finished
data: {"answer":"...","citations":[],"thread_id":"thread-001"}

event: run.finished
data: {"thread_id":"thread-001"}
```

UI 展示建议：

```text
answer.started -> 正在生成最终回答
answer.finished -> 最终回答已完成
```

### `answer_stream`

面向 chat 体验。

```text
入口：POST /chat/stream
输出：SSE
事件：progress_stream 的全部事件 + answer.delta
answer.delta：发送
```

适用场景：

- 回答较长，用户希望边生成边看。
- UI 是聊天窗口。
- 调用方能处理增量文本拼接。

协议示例：

```text
event: answer.started
data: {"thread_id":"thread-001"}

event: answer.delta
data: {"text":"第一段"}

event: answer.delta
data: {"text":"第二段"}

event: answer.finished
data: {"answer":"第一段第二段","citations":[],"thread_id":"thread-001"}
```

约束：

- `answer.delta` 只表示答案文本增量。
- 不把“正在理解”“正在规划”“正在检索”塞进 `answer.delta`。
- 如果模型只产生最终消息而没有 token delta，仍应发送 `answer.started` 和 `answer.finished`。

### `structured_final`

面向系统集成和报告生成。

```text
入口：POST /chat
输出：一次性 JSON response
内容：artifact/schema + answer + citations + checkpoint + observability
SSE：无
answer.delta：无
```

适用场景：

- 调用方需要稳定 JSON/schema。
- UI 要渲染结构化报告卡片。
- 下游系统要读取字段，而不是解析自然语言。

约束：

- 第一版复用当前 `TaxAnswer`，不另起 artifact schema。
- 只要求最终 artifact 合法。
- 不要求 streaming 中间 chunk 都是合法 JSON。
- 如果未来需要“流式进度 + 最终结构化产物”，应组合为 `progress_stream` 的 SSE 事件，并在 `answer.finished` 或后续 artifact 事件中给最终结构化结果；不要让每个 delta 承担结构化语义。

### `batch`

面向文档/问题列表处理。

```text
入口：POST /batch 或 CLI --batch
输出：batch response / report path
SSE：第一版不要求
answer.delta：无
```

适用场景：

- 输入是一份文档或多个问题。
- 每个问题需要确定性抽取、分类、执行、汇总。
- 调用方关心整体报告，而不是单轮 chat。

约束：

- `/batch` 保持显式独立入口。
- 不把 batch 包装成 `/chat` 的一种隐式模式。
- 不把确定性 batch pipeline 包装成 DeepAgents skill。

## API 形态

### 请求字段

在 `ConversationRequest` 增加可选字段：

```python
InteractionMode = Literal[
    "direct_text",
    "progress_stream",
    "answer_stream",
    "structured_final",
    "batch",
]

class ConversationRequest(BaseModel):
    session_id: str
    trace_id: str
    thread_id: str
    messages: list[ConversationMessage]
    interaction_mode: InteractionMode | None = None
```

### Route 默认值

不同入口有不同默认值：

| Route | 默认 mode | 允许 mode |
|---|---|---|
| `POST /chat` | `direct_text` | `direct_text`, `structured_final` |
| `POST /chat/stream` | `answer_stream` | `progress_stream`, `answer_stream` |
| `POST /batch` | `batch` | absent, `batch` |

如果调用方在错误入口传入不匹配 mode，应返回 `400`，不要静默改写。例如：

```text
POST /chat + interaction_mode=batch -> 400
POST /batch + interaction_mode=answer_stream -> 400
POST /chat/stream + interaction_mode=structured_final -> 400
```

## ResponseStrategy

`InteractionMode` 不应散落在 route、executor、SSE adapter 里做字符串判断。建议先集中解析成内部策略对象：

```python
class ResponseStrategy(BaseModel):
    mode: InteractionMode
    route_kind: Literal["chat", "stream", "batch"]
    emit_sse: bool
    include_answer_delta: bool
    final_shape: Literal["text", "structured", "batch"]
```

解析规则：

```text
direct_text      -> chat,   emit_sse=false, include_answer_delta=false, final_shape=text
structured_final -> chat,   emit_sse=false, include_answer_delta=false, final_shape=structured
progress_stream  -> stream, emit_sse=true,  include_answer_delta=false, final_shape=text
answer_stream    -> stream, emit_sse=true,  include_answer_delta=true,  final_shape=text
batch            -> batch,  emit_sse=false, include_answer_delta=false, final_shape=batch
```

代码边界：

```text
service_app.py
  - 解析 route + interaction_mode
  - 不直接关心 LangGraph 内部事件

response_strategy.py
  - 定义 InteractionMode / ResponseStrategy
  - 校验 route 与 mode 是否匹配

agent_executor.py
  - 继续提供 execute_turn / stream_turn
  - 可接受 include_answer_delta 之类的 projector 参数
  - 不负责解释“用户为什么要这个 mode”

stream_events.py
  - 只做内部 event -> 稳定 event 的映射

sse_protocol.py
  - 只做 SSE 文本渲染
```

## 单入口与多接口的关系

当前看起来有一个矛盾：

```text
面向消费者的 LLM/Agent 通常只有一个交互入口
本项目却提供 /chat、/chat/stream、/batch 等多个接口
```

我的判断：这不是矛盾，而是“产品入口”和“工程能力边界”处在不同层。

建议分三层：

```text
Layer 1: Consumer Facade
  用户或外部消费者看到的单入口，例如一个聊天框或未来的 POST /interactions

Layer 2: Interaction Adapter
  解析 interaction_mode、Accept header、stream 参数、输出格式偏好
  生成 ResponseStrategy

Layer 3: Capability Endpoints
  /chat
  /chat/stream
  /batch
  state/history
```

### 为什么不直接只保留一个接口

如果现在把所有能力都压进一个 `/chat`，会出现几个问题：

1. 同一个 URL 既可能返回 JSON，也可能返回 SSE，调用方和测试都必须猜测响应形态。
2. `/batch` 的输入是文档/问题列表处理，不是单轮 chat；强行塞进 chat 会混淆语义。
3. route 层无法清晰表达错误组合，例如 `/chat + answer_stream` 到底是自动流式、报错，还是降级。
4. 观测、验收、测试会变含糊：失败时很难判断是入口选择错了，还是 Agent 执行错了。

所以第一版应保留明确能力端点。

### 为什么未来可以提供单入口

消费者需要的是“一个地方交互”，不等于后端只能有一个 route。

未来可以新增一个 facade，例如：

```text
POST /interactions
```

请求示例：

```json
{
  "session_id": "sess-001",
  "trace_id": "trace-001",
  "thread_id": "thread-001",
  "messages": [
    {"role": "user", "content": "请解释视同销售毛利率差异"}
  ],
  "interaction_mode": "answer_stream"
}
```

facade 的职责是：

```text
根据 interaction_mode / Accept / stream 参数
-> 解析 ResponseStrategy
-> 内部分派到 /chat 或 /chat/stream 或 /batch 对应能力
-> 对外保持一个入口体验
```

这个 facade 可以用 HTTP content negotiation 控制响应形态：

```text
Accept: application/json       -> direct_text / structured_final
Accept: text/event-stream      -> progress_stream / answer_stream
interaction_mode=batch         -> 第一版不支持，未来按 job 语义设计
```

### 当前阶段建议

第一版不要急着新增 `/interactions`。先把底层能力边界做清楚：

1. `/chat` 明确只处理非流式对话。
2. `/chat/stream` 明确只处理流式对话。
3. `/batch` 继续保持独立，但第一版不升级 job/SSE。
4. `InteractionMode` 先作为显式参数和校验规则落地。
5. 等 UI/harness 确认“单入口体验”真的需要后，再新增 facade。

这样做的好处是：

```text
产品上可以走向单入口
工程上不会牺牲清晰边界
测试上仍能精确验证每种能力
```

## 与现有协议的关系

当前已收束的 streaming 协议继续保留：

```text
run.started
answer.started
answer.delta
answer.finished
tool.started
tool.finished
tool.error
skill.started
skill.finished
skill.error
batch.started
batch.finished
batch.error
run.finished
run.error
```

第一版实现可以只覆盖：

```text
run.started
answer.started
answer.delta
answer.finished
tool.started
tool.finished
run.finished
run.error
```

`skill.*` 与 `batch.*` 等有真实可观察动作后再接入，不提前伪造。

## 非目标

1. 不做自动 mode 识别。
2. 不把 `InteractionMode` 放进 DeepAgents/LangChain middleware。
3. 不新增抽象 `stage.*` 协议。
4. 不让 `/chat` 隐式承载 batch。
5. 不要求 streaming delta 是结构化 JSON。
6. 不改变 checkpoint、memory、tools、system prompt 的内部机制。

## 建议实施顺序

### Step 1: 只加类型与校验

- 新增 `InteractionMode` 和 `ResponseStrategy`。
- route 根据入口解析默认 mode。
- 错误组合返回 `400`。
- 不改底层 Agent 行为。

验证：

```text
POST /chat 默认 direct_text
POST /chat/stream 默认 answer_stream
POST /chat interaction_mode=batch 返回 400
```

### Step 2: 控制 `answer.delta`

- `answer_stream` 保留 `answer.delta`。
- `progress_stream` 过滤 `answer.delta`，但仍保留 `answer.started` / `answer.finished`。

验证：

```text
progress_stream: 无 answer.delta，有 answer.finished
answer_stream: 有 answer.delta，有 answer.finished
```

### Step 3: 接入 `structured_final`

- 第一版复用当前 `TaxAnswer` 作为最终 artifact schema。
- `/chat + structured_final` 返回结构化字段。
- 不改 `/chat/stream`。

验证：

```text
structured_final 返回 schema artifact
answer_stream 不承诺 chunk 是 JSON
```

### Step 4: 让 harness 显式传 mode

- demo harness / API 示例显式传入 mode。
- 文档说明默认值和错误组合。

### Step 5: 评估单入口 facade

- 暂不实现。
- 等 UI/harness 确认需要单入口体验后，再设计 `/interactions` 或等价 facade。
- facade 只能分派到既有能力边界，不把 `/batch` 偷偷包装进 `/chat`。

## 已暂缓问题

1. 消费者单入口 facade，例如 `POST /interactions`：当前不做。
2. facade 分流机制，例如 `Accept` header 还是显式 `interaction_mode`：先不考虑。
3. `progress_stream` 的 `answer.started` payload 是否携带固定 `status`：暂时不加。
4. `TaxAnswer` 是否演进为更贴近 UI/报告的 artifact schema：之后考虑。
5. `/batch` 何时进入 job/SSE 设计：之后由实际耗时、用户等待体验和报告生成需求共同触发。
