import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Citation:
    citation_id: str
    source_id: str
    source_type: str
    provider_id: str
    title: str
    locator: str | None
    snippet: str
    confidence: float
    retrieved_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReferenceItem:
    source_id: str
    source_type: str
    provider_id: str
    title: str
    locator: str | None
    snippet: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def citation(self) -> Citation:
        return Citation(
            citation_id=f"{self.provider_id}:{self.source_id}",
            source_id=self.source_id,
            source_type=self.source_type,
            provider_id=self.provider_id,
            title=self.title,
            locator=self.locator,
            snippet=self.snippet,
            confidence=self.confidence,
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True)
class ReferenceBundle:
    query: str
    provider_ids: list[str]
    items: list[ReferenceItem]
    citations: list[Citation]
    coverage: str = "seed"
    missing_facts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "provider_ids": self.provider_ids,
            "items": [asdict(item) for item in self.items],
            "citations": [asdict(citation) for citation in self.citations],
            "coverage": self.coverage,
            "missing_facts": list(self.missing_facts),
        }
