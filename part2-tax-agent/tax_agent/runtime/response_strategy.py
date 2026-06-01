from typing import Literal

from pydantic import BaseModel

from tax_agent.runtime.conversation import InteractionMode


RouteKind = Literal["chat", "stream", "batch"]
FinalShape = Literal["text", "structured", "batch"]


class InvalidInteractionMode(ValueError):
    pass


class ResponseStrategy(BaseModel):
    mode: InteractionMode
    route_kind: RouteKind
    emit_sse: bool
    include_answer_delta: bool
    final_shape: FinalShape


def resolve_response_strategy(route_kind: RouteKind, requested_mode: InteractionMode | None) -> ResponseStrategy:
    mode = requested_mode or _default_mode(route_kind)
    allowed = _allowed_modes(route_kind)
    if mode not in allowed:
        allowed_text = ", ".join(allowed)
        raise InvalidInteractionMode(
            f"interaction_mode={mode!r} is not allowed for {route_kind}; allowed: {allowed_text}"
        )
    if mode == "direct_text":
        return ResponseStrategy(
            mode=mode,
            route_kind=route_kind,
            emit_sse=False,
            include_answer_delta=False,
            final_shape="text",
        )
    if mode == "structured_final":
        return ResponseStrategy(
            mode=mode,
            route_kind=route_kind,
            emit_sse=False,
            include_answer_delta=False,
            final_shape="structured",
        )
    if mode == "progress_stream":
        return ResponseStrategy(
            mode=mode,
            route_kind=route_kind,
            emit_sse=True,
            include_answer_delta=False,
            final_shape="text",
        )
    if mode == "answer_stream":
        return ResponseStrategy(
            mode=mode,
            route_kind=route_kind,
            emit_sse=True,
            include_answer_delta=True,
            final_shape="text",
        )
    return ResponseStrategy(
        mode=mode,
        route_kind=route_kind,
        emit_sse=False,
        include_answer_delta=False,
        final_shape="batch",
    )


def _default_mode(route_kind: RouteKind) -> InteractionMode:
    if route_kind == "chat":
        return "direct_text"
    if route_kind == "stream":
        return "answer_stream"
    return "batch"


def _allowed_modes(route_kind: RouteKind) -> tuple[InteractionMode, ...]:
    if route_kind == "chat":
        return ("direct_text", "structured_final")
    if route_kind == "stream":
        return ("progress_stream", "answer_stream")
    return ("batch",)
