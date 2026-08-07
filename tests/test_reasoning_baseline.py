"""Tests for the baseline aggregation layer.

Tests verify aggregator correctness with synthetic observations —
they are NOT behavioral baselines for reasoning itself.
"""
import pytest

from src.reasoning.observation import ReasoningObservation, OBSERVATION_SCHEMA_VERSION
from src.reasoning.baseline import (
    aggregate, SignalBaselineReport, SignalOutcomeSummary,
    SignalConfidenceSummary,
)


def _obs(
    structured_types: tuple[str, ...] = (),
    confidences: dict[str, float] | None = None,
    confidence: float = 0.0,
    blocked: bool = False,
    latency: float = 0.0,
    problem: str = "",
) -> ReasoningObservation:
    return ReasoningObservation(
        reasoning_stage="evaluation",
        identified_problem=problem,
        confidence_score=confidence,
        readiness_domain="regular",
        readiness_ready=not blocked,
        readiness_blocked=blocked,
        missing_critical_fields=(),
        completeness=0.8,
        intent_primary="fee",
        intent_confidence=0.75,
        dominant_signal_name=None,
        dominant_signal_score=0.0,
        structured_signal_types=structured_types,
        structured_signal_confidences=confidences or {},
        latency_ms=latency,
        observation_id="test",
    )


class TestAggregateEmpty:
    def test_empty_input(self):
        report = aggregate([])
        assert report.total_observations == 0
        assert report.signal_presence == {}
        assert report.signal_combinations == {}
        assert report.no_signal_count == 0
        assert report.by_signal == {}
        assert report.signal_confidence_summary == {}


class TestAggregateNoSignals:
    def test_no_signal_observation(self):
        obs = _obs()
        report = aggregate([obs])
        assert report.total_observations == 1
        assert report.signal_presence == {}
        assert report.no_signal_count == 1

    def test_multiple_no_signal_observations(self):
        obs = _obs()
        report = aggregate([obs, obs, obs])
        assert report.total_observations == 3
        assert report.no_signal_count == 3
        assert report.signal_presence == {}


class TestAggregateSingleSignal:
    def test_grievance_only(self):
        obs = _obs(structured_types=("grievance",), confidences={"grievance": 0.8})
        report = aggregate([obs])
        assert report.total_observations == 1
        assert report.signal_presence == {"grievance": 1}
        assert report.signal_combinations == {("grievance",): 1}
        assert report.by_signal["grievance"].count == 1

    def test_decision_only(self):
        obs = _obs(structured_types=("decision",), confidences={"decision": 0.9})
        report = aggregate([obs])
        assert report.signal_presence == {"decision": 1}
        assert report.signal_combinations == {("decision",): 1}

    def test_emotion_only(self):
        obs = _obs(structured_types=("emotion",), confidences={"emotion": 0.6})
        report = aggregate([obs])
        assert report.signal_presence == {"emotion": 1}
        assert report.signal_combinations == {("emotion",): 1}


class TestAggregateCombinations:
    def test_two_signals(self):
        obs = _obs(
            structured_types=("grievance", "decision"),
            confidences={"grievance": 0.7, "decision": 0.8},
        )
        report = aggregate([obs])
        assert report.signal_combinations == {("decision", "grievance"): 1}

    def test_three_signals(self):
        obs = _obs(
            structured_types=("grievance", "decision", "emotion"),
            confidences={"grievance": 0.7, "decision": 0.8, "emotion": 0.6},
        )
        report = aggregate([obs])
        assert report.signal_combinations == {("decision", "emotion", "grievance"): 1}

    def test_multiple_combinations(self):
        obs1 = _obs(structured_types=("grievance",))
        obs2 = _obs(structured_types=("decision",))
        obs3 = _obs(structured_types=("grievance", "decision"))
        report = aggregate([obs1, obs2, obs3, obs1])
        assert report.total_observations == 4
        assert report.signal_presence["grievance"] == 3
        assert report.signal_presence["decision"] == 2
        assert report.signal_combinations[("grievance",)] == 2
        assert report.signal_combinations[("decision",)] == 1
        assert report.signal_combinations[("decision", "grievance")] == 1

    def test_mixed_signals_and_no_signals(self):
        obs1 = _obs(structured_types=("grievance",))
        obs2 = _obs()
        obs3 = _obs(structured_types=("decision",))
        obs4 = _obs()
        report = aggregate([obs1, obs2, obs3, obs4])
        assert report.total_observations == 4
        assert report.no_signal_count == 2
        assert report.signal_presence["grievance"] == 1
        assert report.signal_presence["decision"] == 1


class TestAggregateOutcomeSummary:
    def test_mean_reasoning_confidence(self):
        obs1 = _obs(structured_types=("grievance",), confidence=0.5)
        obs2 = _obs(structured_types=("grievance",), confidence=0.7)
        report = aggregate([obs1, obs2])
        summary = report.by_signal["grievance"]
        assert summary.mean_reasoning_confidence == 0.6

    def test_blocked_rate(self):
        obs1 = _obs(structured_types=("grievance",), blocked=True)
        obs2 = _obs(structured_types=("grievance",), blocked=False)
        obs3 = _obs(structured_types=("grievance",), blocked=True)
        report = aggregate([obs1, obs2, obs3])
        summary = report.by_signal["grievance"]
        assert summary.count == 3
        assert summary.blocked_rate == 2 / 3

    def test_mean_latency(self):
        obs1 = _obs(structured_types=("grievance",), latency=10.0)
        obs2 = _obs(structured_types=("grievance",), latency=20.0)
        report = aggregate([obs1, obs2])
        summary = report.by_signal["grievance"]
        assert summary.mean_latency_ms == 15.0

    def test_latency_percentiles(self):
        obs1 = _obs(structured_types=("grievance",), latency=1.0)
        obs2 = _obs(structured_types=("grievance",), latency=2.0)
        obs3 = _obs(structured_types=("grievance",), latency=5.0)
        obs4 = _obs(structured_types=("grievance",), latency=10.0)
        obs5 = _obs(structured_types=("grievance",), latency=20.0)
        report = aggregate([obs1, obs2, obs3, obs4, obs5])
        summary = report.by_signal["grievance"]
        assert summary.latency_p50 == 5.0
        assert summary.latency_p95 == 20.0
        assert summary.latency_p99 == 20.0

    def test_identified_problems(self):
        obs1 = _obs(structured_types=("grievance",), problem="needs_reassurance")
        obs2 = _obs(structured_types=("grievance",), problem="needs_reassurance")
        obs3 = _obs(structured_types=("grievance",), problem="needs_clarification")
        report = aggregate([obs1, obs2, obs3])
        summary = report.by_signal["grievance"]
        assert summary.identified_problems == {
            "needs_reassurance": 2,
            "needs_clarification": 1,
        }

    def test_single_observation(self):
        obs = _obs(structured_types=("grievance",), confidence=0.9, latency=5.0)
        report = aggregate([obs])
        summary = report.by_signal["grievance"]
        assert summary.mean_reasoning_confidence == 0.9
        assert summary.mean_latency_ms == 5.0


class TestAggregateFromEnvelope:
    """Aggregator must work with observations deserialized from envelopes."""

    def test_round_trip_single_signal(self):
        obs = _obs(
            structured_types=("grievance",),
            confidences={"grievance": 0.8},
            confidence=0.75,
            blocked=True,
            latency=12.5,
            problem="needs_reassurance",
        )
        restored = ReasoningObservation.from_dict(obs.to_dict())
        report = aggregate([restored])
        assert report.total_observations == 1
        assert report.signal_presence == {"grievance": 1}
        summary = report.by_signal["grievance"]
        assert summary.count == 1
        assert summary.mean_reasoning_confidence == 0.75
        assert summary.blocked_rate == 1.0

    def test_round_trip_combination(self):
        obs = _obs(
            structured_types=("grievance", "emotion"),
            confidences={"grievance": 0.7, "emotion": 0.5},
        )
        restored = ReasoningObservation.from_dict(obs.to_dict())
        report = aggregate([restored])
        assert ("emotion", "grievance") in report.signal_combinations

    def test_round_trip_no_signal(self):
        obs = _obs()
        restored = ReasoningObservation.from_dict(obs.to_dict())
        report = aggregate([restored])
        assert report.no_signal_count == 1
        assert report.signal_presence == {}


class TestAggregateSignalConfidenceSummary:
    """signal_confidence_summary aggregates detector confidence per type."""

    def test_single_observation_single_signal(self):
        obs = _obs(structured_types=("grievance",), confidences={"grievance": 0.8})
        report = aggregate([obs])
        scs = report.signal_confidence_summary["grievance"]
        assert scs.count == 1
        assert scs.mean_confidence == 0.8
        assert scs.min_confidence == 0.8
        assert scs.max_confidence == 0.8

    def test_multiple_observations(self):
        obs1 = _obs(structured_types=("grievance",), confidences={"grievance": 0.6})
        obs2 = _obs(structured_types=("grievance",), confidences={"grievance": 0.9})
        report = aggregate([obs1, obs2])
        scs = report.signal_confidence_summary["grievance"]
        assert scs.count == 2
        assert scs.mean_confidence == 0.75
        assert scs.min_confidence == 0.6
        assert scs.max_confidence == 0.9

    def test_multiple_signals_separate_summaries(self):
        obs = _obs(
            structured_types=("grievance", "emotion"),
            confidences={"grievance": 0.8, "emotion": 0.5},
        )
        report = aggregate([obs])
        assert report.signal_confidence_summary["grievance"].mean_confidence == 0.8
        assert report.signal_confidence_summary["emotion"].mean_confidence == 0.5

    def test_signal_without_confidence_has_zero(self):
        obs = _obs(structured_types=("grievance",))
        report = aggregate([obs])
        scs = report.signal_confidence_summary["grievance"]
        assert scs.mean_confidence == 0.0
        assert scs.count == 0

    def test_confidence_summary_is_frozen(self):
        scs = SignalConfidenceSummary(count=1, mean_confidence=0.5, min_confidence=0.3, max_confidence=0.7)
        with pytest.raises((AttributeError, TypeError)):
            scs.count = 2  # type: ignore[misc]


class TestReportShape:
    """SignalBaselineReport has the expected shape and field types."""

    def test_report_is_frozen(self):
        report = aggregate([])
        with pytest.raises((AttributeError, TypeError)):
            report.total_observations = 42  # type: ignore[misc]

    def test_summary_is_frozen(self):
        summary = SignalOutcomeSummary(
            count=1, mean_reasoning_confidence=0.5, blocked_rate=0.0,
            mean_latency_ms=10.0, latency_p50=5.0, latency_p95=20.0,
            latency_p99=30.0, identified_problems={"test": 1},
        )
        with pytest.raises((AttributeError, TypeError)):
            summary.count = 2  # type: ignore[misc]

    def test_problems_sorted_by_frequency(self):
        obs1 = _obs(structured_types=("grievance",), problem="a")
        obs2 = _obs(structured_types=("grievance",), problem="a")
        obs3 = _obs(structured_types=("grievance",), problem="b")
        report = aggregate([obs1, obs2, obs3])
        problems = report.by_signal["grievance"].identified_problems
        keys = list(problems.keys())
        assert keys == ["a", "b"]

    def test_by_signal_only_contains_seen_signals(self):
        obs = _obs(structured_types=("emotion",))
        report = aggregate([obs])
        assert "grievance" not in report.by_signal
        assert "decision" not in report.by_signal
        assert "emotion" in report.by_signal

    def test_signal_confidence_summary_only_contains_seen(self):
        obs = _obs(structured_types=("emotion",))
        report = aggregate([obs])
        assert "grievance" not in report.signal_confidence_summary
        assert "emotion" in report.signal_confidence_summary
