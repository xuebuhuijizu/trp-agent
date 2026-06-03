"""Compatibility import for the pre-migration intent classifier path."""

from tax_agent.business.analysis.intent_classifier import (
    INTENT_CLASSIFICATION_PROMPT,
    INTENT_LABELS,
    ClassifiedQuestion,
    IntentClassifier,
)

__all__ = ["ClassifiedQuestion", "INTENT_CLASSIFICATION_PROMPT", "INTENT_LABELS", "IntentClassifier"]
