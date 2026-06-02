"""Compatibility helpers for the pre-F005 tax retrieval shape.

New code should start from `tax_agent.domain.reference_layer` and the
`find_tax_authorities` tool. This module only keeps the old demo tool name and
legacy payload parsing alive while tests and historical examples migrate.
"""

import json
from typing import Any

from tax_agent.domain.reference_layer import (
    TAX_AUTHORITY_SOURCES as TAX_SOURCES,
    find_tax_authorities,
)


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
