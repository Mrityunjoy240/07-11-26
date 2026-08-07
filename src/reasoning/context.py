"""Immutable adapter between UnderstandingResult and ReasoningEngine.

ReasoningContext is a frozen snapshot of the fields that ReasoningEngine
reads from UnderstandingResult.  It exists to:

  1. Make the Understanding → Reasoning boundary explicit and immutable.
  2. Carry StructuredSignals and SignalInteraction to future reasoning
     logic without modifying the current engine.
  3. Prove (via tests) that the contract is sound before migration.

This module does NOT modify ReasoningEngine behavior.  It is a read-only
contract definition.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.understanding.models import (
    ConversationSignals,
    UnderstandingResult,
)
from src.understanding.profile import StudentProfile
from src.understanding.signals.conversation import StructuredSignals
from src.understanding.signals.interaction import SignalInteraction


@dataclass(frozen=True)
class ReasoningContext:
    """Immutable snapshot of UnderstandingResult fields for reasoning.

    Frozen invariants:
      - All scalar fields (str, float) are immutable by nature.
      - tuple fields (intent_all_scores_items, missing_info_items,
        overlap_tags, confidence_ranking) are immutable.
      - StructuredSignals and SignalInteraction are frozen dataclasses.
      - profile and signals are shared references (not deep-copied)
        because they are read-only within reasoning.  Callers must not
        mutate them after constructing a ReasoningContext.
    """

    # ── Intent ────────────────────────────────────────────────────────
    intent_primary: str
    intent_confidence: float
    intent_all_scores_items: tuple[tuple[str, float], ...]

    # ── Utterance ─────────────────────────────────────────────────────
    text: str
    understanding_confidence: float

    # ── Profile (shared reference, not deep-copied) ───────────────────
    profile: StudentProfile

    # ── Flat conversation signals (shared reference) ──────────────────
    signals: ConversationSignals

    # ── Structured signals (frozen, safe to share) ────────────────────
    structured_signals: StructuredSignals
    signal_interaction: SignalInteraction

    # ── Missing information (immutable copy) ──────────────────────────
    missing_info_items: tuple[str, ...]

    # ── Domain interpretation ─────────────────────────────────────────
    domain_pathway: str
    domain_student_type: str
    domain_qualification: str
    domain_primary_intent: str

    @classmethod
    def from_understanding_result(
        cls, result: UnderstandingResult,
    ) -> ReasoningContext:
        """Create an immutable context from a UnderstandingResult.

        Defensive copies:
          - intent.all_scores → tuple of (key, value) pairs
          - missing_info.items → tuple of strings

        Shared references (not copied):
          - profile (StudentProfile)
          - signals (ConversationSignals)
          - structured_signals (frozen)
          - signal_interaction (frozen)
        """
        return cls(
            intent_primary=result.intent.primary,
            intent_confidence=result.intent.confidence,
            intent_all_scores_items=tuple(result.intent.all_scores.items()),
            text=result.text,
            understanding_confidence=result.confidence,
            profile=result.profile,
            signals=result.signals,
            structured_signals=result.structured_signals,
            signal_interaction=result.signal_interaction,
            missing_info_items=tuple(result.missing_info.items),
            domain_pathway=result.domain.pathway,
            domain_student_type=result.domain.student_type,
            domain_qualification=result.domain.qualification,
            domain_primary_intent=result.domain.primary_intent,
        )
