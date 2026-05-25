---
topics: [python, java, primer]
doc_kind: guide
created: 2026-05-26
---

# Python 前置知识指南（Java 开发者视角）

## 1. 环境准备

```bash
# 安装 Python 3.11+
python --version

# 推荐使用 uv (高速包管理)
pip install uv

# 创建虚拟环境
uv venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

## 2. Java vs Python 快速对照

| Java | Python | 说明 |
|------|--------|------|
| `public class Foo {}` | `class Foo:` | 无访问修饰符，无大括号 |
| `interface Foo {}` | `Protocol` / ABC | 鸭子类型，协议可选 |
| `List<String> list = new ArrayList<>()` | `list: list[str] = []` | 类型注解（运行时可选） |
| `for (int i = 0; i < n; i++) {}` | `for i in range(n):` | for-each 风格 |
| `if (cond) { ... }` | `if cond:` | 无括号，冒号+缩进 |
| `try { ... } catch (Exception e) { ... }` | `try: ... except Exception as e:` | 同理 |
| `// comment` / `/* block */` | `# comment` / `"""docstring"""` | |
| `mvn/gradle` 依赖管理 | `uv add / pip install` | |
| `null` | `None` | |
| `&& \|\| !` | `and or not` | |
| `method(args)` | `def method(args):` | |

## 3. 关键 Python 特性（阅读 Deep Agents 代码必需）

### 3.1 类型注解（类似 Java 泛型）

```python
from typing import Optional

def add(a: int, b: int) -> int:
    return a + b

name: str = "hello"
count: Optional[int] = None  # 等价 Integer?
```

### 3.2 async/await（Deep Agents 大量使用）

```python
async def fetch_data(url: str) -> dict:
    result = await http_client.get(url)
    return result.json()
```

### 3.3 Pydantic（数据模型，类似 Java Record/Lombok）

```python
from pydantic import BaseModel

class TaxQuestion(BaseModel):
    text: str
    intent: str  # "definition" | "rate" | "compliance"

q = TaxQuestion(text="增值税是什么", intent="definition")
print(q.model_dump_json())  # {"text": "增值税是什么", "intent": "definition"}
```

### 3.4 装饰器（类似 Java 注解）

```python
def log_call(func):
    def wrapper(*args, **kwargs):
        print(f"Calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper

@log_call
def my_func():
    pass
```

### 3.5 上下文管理器（类似 Java try-with-resources）

```python
with open("file.txt", "r") as f:
    content = f.read()
# 自动 close
```

## 4. 常见坑

| 问题 | 说明 |
|------|------|
| 可变默认参数 | `def f(lst=[])` → 多次调用共享同一 list |
| 缩进 | 4 空格，禁止 tab 混用 |
| pip 全局安装 | 一定要在 venv 内操作 |
| `==` vs `is` | `==` 值比较，`is` 引用比较（类似 Java `equals` vs `==`） |

## 5. 推荐学习路径

1. [Python 官方教程](https://docs.python.org/3/tutorial/)（2 小时）
2. [Deep Agents Quickstart](https://docs.langchain.com/oss/python/deepagents/overview)
3. 运行本项目的 `part1-capability-validation/examples/` 示例
