import json
from typing import Any

from tax_agent.business.references.manager import DEFAULT_REFERENCE_MANAGER


def find_tax_authorities(query: str) -> str:
    """DeepAgents tool for tax laws, policies, and formal authorities."""
    bundle = DEFAULT_REFERENCE_MANAGER.find_tax_authorities(query)
    return json.dumps(bundle.to_dict(), ensure_ascii=False)


def extract_citations_from_messages(messages: list[Any]) -> list[dict]:
    citations = []
    seen = set()
    for message in messages:
        name = _message_value(message, "name") or _message_value(message, "tool_name")
        if name != "find_tax_authorities":
            continue
        payload = _parse_tool_payload(_message_value(message, "content"))
        for citation in payload.get("citations", []):
            source_id = citation.get("source_id")
            if not source_id or source_id in seen:
                continue
            seen.add(source_id)
            citations.append(citation)
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
    "extract_citations_from_messages",
    "find_tax_authorities",
]
