import json
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from tax_agent.domain.tax_retrieval import extract_citations_from_messages


def normalize_stream_event(raw_event: dict) -> dict | None:
    event_type = raw_event.get("event")
    data = raw_event.get("data", {})
    name = raw_event.get("name")

    if event_type in {"on_chat_model_stream", "on_llm_stream"}:
        text = chunk_text(data.get("chunk"))
        if not text:
            return None
        return {"event": "answer.delta", "data": {"text": text}}

    if event_type == "on_tool_start":
        return {
            "event": "tool.started",
            "data": {"name": name, "input": jsonable(data.get("input"))},
        }

    if event_type == "on_tool_end":
        output = data.get("output")
        citations = extract_citations_from_messages(
            [{"name": name, "content": string_content(output)}]
        )
        return {
            "event": "tool.finished",
            "data": {
                "name": name,
                "source_ids": [item["source_id"] for item in citations if item.get("source_id")],
                "citations": citations,
            },
        }

    return None


def chunk_text(chunk: Any) -> str:
    content = content_value(chunk)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(content_block_text(block) for block in content)
    return ""


def content_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return value.get("content")
    return getattr(value, "content", None)


def content_block_text(block: Any) -> str:
    if isinstance(block, str):
        return block
    if isinstance(block, Mapping):
        if block.get("type") == "text":
            return str(block.get("text", ""))
        return str(block.get("content", ""))
    return ""


def string_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    try:
        return json.dumps(jsonable(value), ensure_ascii=False)
    except TypeError:
        return str(value)


def jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)
