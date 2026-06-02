"""Legacy RAG decorator.

F005+ main paths use the Reference Layer `find_tax_authorities` tool. This no-op adapter is
kept for compatibility tests and historical examples, not for the main path.
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
