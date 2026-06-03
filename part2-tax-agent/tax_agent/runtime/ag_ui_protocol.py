"""AG-UI protocol helpers for the tax-agent streaming boundary.

This module is intentionally independent from the executor implementation:
it owns public AG-UI event names, stable IDs, and raw LangChain event
normalization. Runtime code should compose these helpers rather than define
public protocol payloads inline.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from tax_agent.domain.tax_retrieval import extract_citations_from_messages
from tax_agent.runtime.conversation import ConversationRequest


@dataclass
class AgUiRunContext:
    run_id: str
    thread_id: str
    message_id: str
    tool_index: int = 0

    @classmethod
    def from_request(cls, request: ConversationRequest) -> "AgUiRunContext":
        run_id = request.trace_id
        return cls(
            run_id=run_id,
            thread_id=request.thread_id,
            message_id=f"{run_id}:assistant",
        )

    def next_tool_call_id(self) -> str:
        self.tool_index += 1
        return f"{self.run_id}:tool:{self.tool_index}"


def run_started_event(context: AgUiRunContext) -> dict:
    return {
        "event": "RUN_STARTED",
        "data": {"runId": context.run_id, "threadId": context.thread_id},
    }


def text_message_start_event(context: AgUiRunContext) -> dict:
    return {
        "event": "TEXT_MESSAGE_START",
        "data": {"messageId": context.message_id, "role": "assistant"},
    }


def text_message_content_event(context: AgUiRunContext, delta: str) -> dict:
    return {
        "event": "TEXT_MESSAGE_CONTENT",
        "data": {"messageId": context.message_id, "delta": delta},
    }


def text_message_end_event(context: AgUiRunContext) -> dict:
    return {
        "event": "TEXT_MESSAGE_END",
        "data": {"messageId": context.message_id},
    }


def run_finished_event(context: AgUiRunContext, result: dict) -> dict:
    return {
        "event": "RUN_FINISHED",
        "data": {
            "runId": context.run_id,
            "threadId": context.thread_id,
            "result": result,
        },
    }


def run_error_event(context: AgUiRunContext, error: str, message: str) -> dict:
    return {
        "event": "RUN_ERROR",
        "data": {
            "runId": context.run_id,
            "threadId": context.thread_id,
            "error": error,
            "message": message,
        },
    }


def normalize_ag_ui_event(raw_event: dict, context: AgUiRunContext) -> list[dict]:
    event_type = raw_event.get("event")
    data = raw_event.get("data", {})
    name = raw_event.get("name")

    if event_type in {"on_chat_model_stream", "on_llm_stream"}:
        text = chunk_text(data.get("chunk"))
        if not text:
            return []
        return [text_message_content_event(context, text)]

    if event_type == "on_tool_start":
        tool_call_id = context.next_tool_call_id()
        return [
            {
                "event": "TOOL_CALL_START",
                "data": {"toolCallId": tool_call_id, "toolName": name},
            },
            {
                "event": "TOOL_CALL_ARGS",
                "data": {"toolCallId": tool_call_id, "args": jsonable(data.get("input"))},
            },
        ]

    if event_type == "on_tool_end":
        tool_call_id = _current_tool_call_id(context)
        output = data.get("output")
        citations = extract_citations_from_messages(
            [{"name": name, "content": string_content(output)}]
        )
        return [
            {
                "event": "TOOL_CALL_END",
                "data": {"toolCallId": tool_call_id},
            },
            {
                "event": "TOOL_CALL_RESULT",
                "data": {
                    "toolCallId": tool_call_id,
                    "toolName": name,
                    "sourceIds": [item["source_id"] for item in citations if item.get("source_id")],
                    "citations": citations,
                    "summary": summarize_tool_result(citations),
                },
            },
        ]

    return []


def _current_tool_call_id(context: AgUiRunContext) -> str:
    if context.tool_index == 0:
        return context.next_tool_call_id()
    return f"{context.run_id}:tool:{context.tool_index}"


def summarize_tool_result(citations: list[dict]) -> str:
    if not citations:
        return ""
    titles = [str(item["title"]) for item in citations if item.get("title")]
    if not titles:
        return f"{len(citations)} citations"
    return "；".join(titles[:3])


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
