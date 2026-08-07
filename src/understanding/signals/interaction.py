"""Descriptive signal interaction analysis.

This module analyzes which structured signals co-occur in a single
utterance and describes their relationship.  It is purely descriptive —
it does not suppress signals, make routing decisions, or modify
detector outputs.

Usage:
    from src.understanding.signals.interaction import analyze_signals

    signals = StructuredSignals(grievance=g, decision=d, emotion=e)
    interaction = analyze_signals(signals)
    print(interaction.overlap_tags)       # ("grievance+decision+emotion",)
    print(interaction.primary_dimension)  # "grievance"
    print(interaction.confidence_ranking) # ("grievance", "decision", "emotion")
"""
from __future__ import annotations

from dataclasses import dataclass

from src.understanding.signals.conversation import StructuredSignals


# Deterministic ordering for tie-breaking: grievance > decision > emotion.
_DIMENSION_ORDER: tuple[str, ...] = ("grievance", "decision", "emotion")


@dataclass(frozen=True)
class SignalInteraction:
    """Describes how detected signals co-occur in one utterance.

    Attributes:
        overlap_tags: Tuple of overlap tag strings.  Empty when zero or
                      one signal is present.  For multiple signals, each
                      tag names the co-occurring dimensions in
                      alphabetical order, joined by '+'.
        primary_dimension: The dimension with the highest confidence.
                           "none" when no signals are present.
        confidence_ranking: Active signal dimensions ordered by
                            descending confidence.  Ties broken by
                            _DIMENSION_ORDER (grievance > decision > emotion).
    """
    overlap_tags: tuple[str, ...]
    primary_dimension: str
    confidence_ranking: tuple[str, ...]


def _active_dimensions(signals: StructuredSignals) -> list[tuple[str, float]]:
    """Return list of (dimension_name, confidence) for non-None signals."""
    dims: list[tuple[str, float]] = []
    if signals.grievance is not None:
        dims.append(("grievance", signals.grievance.confidence))
    if signals.decision is not None:
        dims.append(("decision", signals.decision.confidence))
    if signals.emotion is not None:
        dims.append(("emotion", signals.emotion.confidence))
    return dims


def _compute_overlap_tags(active: list[tuple[str, float]]) -> tuple[str, ...]:
    """Compute overlap tags from the list of active dimensions.

    For 0 or 1 signals: no tags.
    For 2+ signals: one tag naming all dimensions, sorted alphabetically.
    """
    if len(active) < 2:
        return ()
    names = sorted(dim for dim, _ in active)
    return ("+".join(names),)


def _compute_confidence_ranking(active: list[tuple[str, float]]) -> tuple[str, ...]:
    """Rank active dimensions by descending confidence.

    Ties broken by _DIMENSION_ORDER (grievance > decision > emotion).
    """
    if not active:
        return ()
    # Sort by: confidence descending, then dimension order ascending for ties.
    # _DIMENSION_ORDER index gives the deterministic tie-break.
    order_index = {name: i for i, name in enumerate(_DIMENSION_ORDER)}
    ranked = sorted(
        active,
        key=lambda item: (-item[1], order_index.get(item[0], 99)),
    )
    return tuple(dim for dim, _ in ranked)


def _compute_primary(active: list[tuple[str, float]]) -> str:
    """Return the dimension with highest confidence.

    Ties broken by _DIMENSION_ORDER.
    """
    if not active:
        return "none"
    ranking = _compute_confidence_ranking(active)
    return ranking[0]


def analyze_signals(signals: StructuredSignals) -> SignalInteraction:
    """Analyze which signals co-occur and describe their relationship.

    This is a pure function with no side effects.  It does not modify
    the input StructuredSignals or any detector outputs.

    Args:
        signals: The structured signals container from the understanding
                 engine.

    Returns:
        A frozen SignalInteraction describing the signal combination.
    """
    active = _active_dimensions(signals)

    return SignalInteraction(
        overlap_tags=_compute_overlap_tags(active),
        primary_dimension=_compute_primary(active),
        confidence_ranking=_compute_confidence_ranking(active),
    )
