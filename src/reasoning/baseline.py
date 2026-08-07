"""Baseline analysis for reasoning observations.

Aggregates ReasoningObservation objects into a SignalBaselineReport that
answers baseline questions about signal presence, combinations, and their
correlation with reasoning outcomes — without changing reasoning behavior.

Key distinction maintained throughout:
  - mean_reasoning_confidence: how confident was the ReasoningEngine?
  - structured signal confidence: how confident was the signal detector?
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

from src.reasoning.observation import ReasoningObservation


@dataclass(frozen=True)
class SignalConfidenceSummary:
    """Distribution of detector confidence for a structured signal type."""
    count: int
    mean_confidence: float
    min_confidence: float
    max_confidence: float


@dataclass(frozen=True)
class SignalOutcomeSummary:
    """Aggregate metrics for observations that share a signal characteristic."""
    count: int
    mean_reasoning_confidence: float
    blocked_rate: float
    mean_latency_ms: float
    latency_p50: float
    latency_p95: float
    latency_p99: float
    identified_problems: dict[str, int]


@dataclass(frozen=True)
class SignalBaselineReport:
    """Baseline statistics over a collection of reasoning observations."""
    total_observations: int
    signal_presence: dict[str, int]
    signal_combinations: dict[tuple[str, ...], int]
    no_signal_count: int
    by_signal: dict[str, SignalOutcomeSummary]
    signal_confidence_summary: dict[str, SignalConfidenceSummary]


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = max(0, min(len(sorted_vals) - 1, int(len(sorted_vals) * p / 100)))
    return sorted_vals[idx]


def _summarize(observations: list[ReasoningObservation]) -> SignalOutcomeSummary:
    n = len(observations)
    if n == 0:
        return SignalOutcomeSummary(
            count=0, mean_reasoning_confidence=0.0, blocked_rate=0.0,
            mean_latency_ms=0.0, latency_p50=0.0, latency_p95=0.0,
            latency_p99=0.0, identified_problems={},
        )
    confs = [o.confidence_score for o in observations]
    blockeds = [1 if o.readiness_blocked else 0 for o in observations]
    lats = [o.latency_ms for o in observations]
    problems: dict[str, int] = {}
    for o in observations:
        p = o.identified_problem or "(none)"
        problems[p] = problems.get(p, 0) + 1
    return SignalOutcomeSummary(
        count=n,
        mean_reasoning_confidence=(
            statistics.mean(confs) if len(confs) > 1 else confs[0]
        ),
        blocked_rate=sum(blockeds) / n,
        mean_latency_ms=statistics.mean(lats) if len(lats) > 1 else lats[0],
        latency_p50=_percentile(lats, 50),
        latency_p95=_percentile(lats, 95),
        latency_p99=_percentile(lats, 99),
        identified_problems=dict(sorted(problems.items(), key=lambda x: -x[1])),
    )


def _summarize_confidences(
    observations: list[ReasoningObservation],
    signal_type: str,
) -> SignalConfidenceSummary:
    confs = [
        o.structured_signal_confidences.get(signal_type, 0.0)
        for o in observations
        if signal_type in o.structured_signal_confidences
    ]
    n = len(confs)
    if n == 0:
        return SignalConfidenceSummary(
            count=0, mean_confidence=0.0, min_confidence=0.0, max_confidence=0.0,
        )
    return SignalConfidenceSummary(
        count=n,
        mean_confidence=statistics.mean(confs) if len(confs) > 1 else confs[0],
        min_confidence=min(confs),
        max_confidence=max(confs),
    )


def aggregate(
    observations: Iterable[ReasoningObservation],
) -> SignalBaselineReport:
    """Aggregate observations into a baseline report.

    Pure function — no side effects, no global state.
    """
    all_obs = list(observations)
    total = len(all_obs)

    if total == 0:
        return SignalBaselineReport(
            total_observations=0,
            signal_presence={},
            signal_combinations={},
            no_signal_count=0,
            by_signal={},
            signal_confidence_summary={},
        )

    presence: Counter[str] = Counter()
    combos: Counter[tuple[str, ...]] = Counter()
    no_signal = 0

    for obs in all_obs:
        types = tuple(sorted(obs.structured_signal_types))
        if types:
            for t in types:
                presence[t] += 1
            combos[types] += 1
        else:
            no_signal += 1

    by_signal: dict[str, list[ReasoningObservation]] = {}
    for obs in all_obs:
        for t in obs.structured_signal_types:
            by_signal.setdefault(t, []).append(obs)

    seen_signals = set(presence.keys())
    signal_confidence_summary = {
        s: _summarize_confidences(by_signal.get(s, []), s)
        for s in seen_signals
    }

    return SignalBaselineReport(
        total_observations=total,
        signal_presence=dict(presence.most_common()),
        signal_combinations=dict(combos.most_common()),
        no_signal_count=no_signal,
        by_signal={k: _summarize(v) for k, v in by_signal.items()},
        signal_confidence_summary=signal_confidence_summary,
    )
