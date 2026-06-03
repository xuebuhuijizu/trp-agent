import json
from typing import Any

from tax_agent.business.references._legacy_reference_layer import (
    DEFAULT_REFERENCE_MANAGER,
    TAX_AUTHORITY_SOURCES,
    Citation,
    LocalTaxAuthorityProvider,
    ReferenceBundle,
    ReferenceItem,
    ReferenceManager,
    ReferenceProvider,
)


def find_tax_authorities(query: str) -> str:
    """DeepAgents tool for tax laws, policies, and formal authorities."""
    bundle = DEFAULT_REFERENCE_MANAGER.find_tax_authorities(query)
    return json.dumps(bundle.to_dict(), ensure_ascii=False)


def retrieve_tax_context(query: str) -> str:
    """Compatibility wrapper for the old demo retrieval tool name."""
    return find_tax_authorities(query)


def extract_citations_from_messages(messages: list[Any]) -> list[dict]:
    citations = []
    seen = set()
    for message in messages:
        name = _message_value(message, "name") or _message_value(message, "tool_name")
        if name not in {"find_tax_authorities", "retrieve_tax_context"}:
            continue
        payload = _parse_tool_payload(_message_value(message, "content"))
        for citation in payload.get("citations", []):
            source_id = citation.get("source_id")
            if not source_id or source_id in seen:
                continue
            seen.add(source_id)
            citations.append(citation)
        for source in payload.get("sources", []):
            source_id = source.get("source_id")
            title = source.get("title")
            if not source_id or not title or source_id in seen:
                continue
            seen.add(source_id)
            citations.append({"source_id": source_id, "title": title})
    return citations


def _parse_tool_payload(content: Any) -> dict:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return {}
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _message_value(message: Any, key: str):
    if isinstance(message, dict):
        return message.get(key)
    return getattr(message, key, None)


__all__ = [
    "Citation",
    "DEFAULT_REFERENCE_MANAGER",
    "LocalTaxAuthorityProvider",
    "ReferenceBundle",
    "ReferenceItem",
    "ReferenceManager",
    "ReferenceProvider",
    "TAX_AUTHORITY_SOURCES",
    "extract_citations_from_messages",
    "find_tax_authorities",
    "retrieve_tax_context",
]
