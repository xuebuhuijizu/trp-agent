import os
from dataclasses import dataclass, field
from typing import Any, Callable


EventRecorder = Callable[..., None]


@dataclass
class ObservabilityConfig:
    provider: str = "none"
    callbacks: list[Any] = field(default_factory=list)
    event_recorder: EventRecorder | None = None
    session_id: str | None = None
    user_id: str | None = None
    base_tags: list[str] = field(default_factory=list)

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
        tags: list[str] | None = None,
    ) -> None:
        if not self.event_recorder:
            return
        try:
            kwargs: dict[str, Any] = {
                "name": name,
                "input": input,
                "output": output,
                "metadata": metadata,
                "level": level,
                "status_message": status_message,
            }
            # Forward ``tags`` only when there is something meaningful to send
            # (either ``base_tags`` or a non-empty ``tags`` argument). Calling
            # recorders with ``tags=[]`` would break legacy contract tests
            # that expect the original call shape.
            merged_tags: list[str] | None = None
            if self.base_tags or tags:
                merged_tags = list(self.base_tags)
                if tags:
                    merged_tags.extend(tags)
                kwargs["tags"] = merged_tags
            try:
                self.event_recorder(**kwargs)
            except TypeError:
                # Recorder signature does not accept ``tags``; retry without it.
                kwargs.pop("tags", None)
                self.event_recorder(**kwargs)
        except Exception:
            # Observability must never change runtime behavior.
            return

    def record_skill_invocation(
        self,
        skill_name: str,
        file_path: str,
        *,
        session_id: str | None = None,
        trace_id: str | None = None,
        thread_id: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Forward a single ``skill.invocation`` event to the recorder.

        Tags applied to the event:
            - ``skill_invocation=true``
            - ``skill_name=<skill_name>``
            - everything in ``base_tags`` (e.g. ``tax-agent``)
        """
        if not self.event_recorder:
            return
        tags = [
            "skill_invocation=true",
            f"skill_name={skill_name}",
        ]
        metadata: dict[str, Any] = {
            "skill_name": skill_name,
            "file_path": file_path,
            "session_id": session_id or self.session_id,
            "trace_id": trace_id,
            "thread_id": thread_id,
        }
        if duration_ms is not None:
            metadata["duration_ms"] = duration_ms
        self.record_event(
            name="skill.invocation",
            metadata=metadata,
            tags=tags,
            level="DEFAULT",
            status_message=f"Skill '{skill_name}' invoked via {file_path}",
        )


def build_langfuse_observability(
    enabled: bool | None = None,
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    base_tags: list[str] | None = None,
) -> ObservabilityConfig:
    enabled = enabled if enabled is not None else os.getenv("LANGFUSE_ENABLED", "0") == "1"
    if not enabled:
        return ObservabilityConfig(
            session_id=session_id,
            user_id=user_id,
            base_tags=list(base_tags or []),
        )

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

    handler_kwargs: dict[str, Any] = {}
    if session_id is not None:
        handler_kwargs["session_id"] = session_id
    if user_id is not None:
        handler_kwargs["user_id"] = user_id
    if base_tags:
        handler_kwargs["tags"] = list(base_tags)

    return ObservabilityConfig(
        provider="langfuse",
        callbacks=[CallbackHandler(**handler_kwargs)],
        event_recorder=record_event,
        session_id=session_id,
        user_id=user_id,
        base_tags=list(base_tags or []),
    )
