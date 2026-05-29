import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ObservabilityConfig:
    provider: str = "none"
    callbacks: list[Any] = field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return self.provider != "none" and bool(self.callbacks)


def build_langfuse_observability(enabled: bool | None = None) -> ObservabilityConfig:
    enabled = enabled if enabled is not None else os.getenv("LANGFUSE_ENABLED", "0") == "1"
    if not enabled:
        return ObservabilityConfig()

    try:
        from langfuse.langchain import CallbackHandler  # type: ignore
    except Exception as exc:
        raise RuntimeError("LANGFUSE_ENABLED=1 requires the langfuse package") from exc

    return ObservabilityConfig(provider="langfuse", callbacks=[CallbackHandler()])

