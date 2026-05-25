"""RAG 装饰器 — 为未来接入检索增强生成预留接口。

当前为桩实现（no-op），后期替换为真实 RAG 检索逻辑。
"""

from typing import Protocol


class RAGAdapter(Protocol):
    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        ...


class NoopRAG:
    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        return []


class RAGDecorator:
    def __init__(self, adapter: RAGAdapter | None = None):
        self._adapter = adapter or NoopRAG()

    def set_adapter(self, adapter: RAGAdapter):
        self._adapter = adapter

    async def enrich(self, question: str, context: str) -> str:
        docs = await self._adapter.retrieve(question)
        if not docs:
            return context
        rag_context = "\n\n".join(docs)
        return f"{context}\n\n参考文档：\n{rag_context}"
