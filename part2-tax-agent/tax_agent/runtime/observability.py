import os
from dataclasses import dataclass, field
from typing import Any, Callable


EventRecorder = Callable[..., None]


@dataclass
class ObservabilityConfig:
    provider: str = "none"
    callbacks: list[Any] = field(default_factory=list)
    event_recorder: EventRecorder | None = None

    @property
    def enabled(self) -> bool:
        return self.provider != "none" and bool(self.callbacks)

    def record_event(
        self,
        name: str,
        *,
        input: Any | None = None,
        output: Any | None = None,
        metadata: dict | None = None,
        level: str = "DEFAULT",
        status_message: str | None = None,
    ) -> None:
        if not self.event_recorder:
            return
        try:
            self.event_recorder(
                name=name,
                input=input,
                output=output,
                metadata=metadata,
                level=level,
                status_message=status_message,
            )
        except Exception:
            # Observability must never change runtime behavior.
            return


def build_langfuse_observability(enabled: bool | None = None) -> ObservabilityConfig:
    enabled = enabled if enabled is not None else os.getenv("LANGFUSE_ENABLED", "0") == "1"
    if not enabled:
        return ObservabilityConfig()

    try:
        from langfuse.langchain import CallbackHandler  # type: ignore
        from langfuse import Langfuse  # type: ignore
    except Exception as exc:
        raise RuntimeError("LANGFUSE_ENABLED=1 requires the langfuse package") from exc

    client = Langfuse()

    def record_event(**kwargs):
        trace_id = None
        try:
            trace_id = client.get_current_trace_id()
        except Exception:
            trace_id = None
        trace_context = {"trace_id": trace_id} if trace_id else None
        client.create_event(trace_context=trace_context, **kwargs)
        client.flush()

    return ObservabilityConfig(provider="langfuse", callbacks=[CallbackHandler()], event_recorder=record_event)
