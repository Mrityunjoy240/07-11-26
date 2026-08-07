"""Reusable signal interface for understanding signals.

A Signal represents a detected conversational signal with provenance.
It is intentionally minimal — future detectors (emotion, confusion,
urgency) reuse the same structure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Signal:
    """A detected signal with value, confidence, and provenance.

    Attributes:
        value: The detected signal value (e.g. "waiting", "ignored",
               "anxiety", "compare").
        confidence: Detection confidence in [0.0, 1.0].
        source: Detector that produced this signal
                (e.g. "understanding.grievance_detector").
        target: Optional extracted subject for structured detectors
                (e.g. "CSE" for a compare signal).
    """
    value: str
    confidence: float
    source: str
    target: Optional[str] = field(default=None)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be in [0.0, 1.0], got {self.confidence}"
            )
        if not self.value:
            raise ValueError("value must be non-empty")
