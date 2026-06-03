"""Compatibility import for the pre-migration batch IO path."""

from tax_agent.delivery.batch_io.question_extractor import (
    MAX_FALLBACK_QUESTION_CHARS,
    QUESTION_MARKS,
    _cap_question,
    _split_questions,
    extract_questions,
)

__all__ = [
    "MAX_FALLBACK_QUESTION_CHARS",
    "QUESTION_MARKS",
    "_cap_question",
    "_split_questions",
    "extract_questions",
]
