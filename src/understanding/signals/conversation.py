"""Extensible conversation signal container.

This replaces the flat-float ConversationSignals model with a
structured-signal model that carries provenance and confidence.
Grievance and decision intent are implemented; others follow the
same interface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.understanding.signals.base import Signal


@dataclass(frozen=True)
class StructuredSignals:
    """Container for all structured conversation signals.

    Each field is Optional[Signal].  Future detectors (emotion,
    confusion, urgency) follow the same pattern:
    detect -> produce Signal -> set field.
    """
    grievance: Optional[Signal] = None
    decision: Optional[Signal] = None
    emotion: Optional[Signal] = None

    def has_grievance(self) -> bool:
        return self.grievance is not None and self.grievance.confidence >= 0.5

    def has_decision_intent(self) -> bool:
        return self.decision is not None and self.decision.confidence >= 0.5

    def has_emotion(self) -> bool:
        return self.emotion is not None and self.emotion.confidence >= 0.5

    def as_dict(self) -> dict[str, dict]:
        """Serialize non-None signals for metadata/debug."""
        d: dict[str, dict] = {}
        if self.grievance is not None:
            d["grievance"] = {
                "value": self.grievance.value,
                "confidence": self.grievance.confidence,
                "source": self.grievance.source,
            }
        if self.decision is not None:
            entry: dict = {
                "value": self.decision.value,
                "confidence": self.decision.confidence,
                "source": self.decision.source,
            }
            if self.decision.target is not None:
                entry["target"] = self.decision.target
            d["decision"] = entry
        if self.emotion is not None:
            d["emotion"] = {
                "value": self.emotion.value,
                "confidence": self.emotion.confidence,
                "source": self.emotion.source,
            }
        return d
