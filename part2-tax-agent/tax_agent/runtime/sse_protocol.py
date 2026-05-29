import json
from collections.abc import Mapping
from typing import Any


def render_sse(event: str, data: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(data), ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"

