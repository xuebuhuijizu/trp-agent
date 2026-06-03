"""Deprecated interaction-mode compatibility module.

AG-UI made `/chat/stream` the sole streaming protocol. Delivery routes no longer
select behavior through InteractionMode; callers should use `/chat`,
`/chat/stream`, or `/batch` directly.
"""


class InvalidInteractionMode(ValueError):
    pass


def resolve_response_strategy(*_args, **_kwargs):
    raise InvalidInteractionMode(
        "InteractionMode has been removed from the architecture; use the explicit delivery route instead."
    )
