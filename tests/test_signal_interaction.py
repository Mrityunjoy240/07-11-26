"""Tests for the signal interaction analysis layer (v1.1.4)."""
import pytest

from src.understanding.signals.base import Signal
from src.understanding.signals.conversation import StructuredSignals
from src.understanding.signals.interaction import analyze_signals, SignalInteraction


# =========================================================================
# 1. No signals
# =========================================================================

class TestNoSignals:
    def test_empty_signals(self):
        sig = StructuredSignals()
        result = analyze_signals(sig)
        assert result.overlap_tags == ()
        assert result.primary_dimension == "none"
        assert result.confidence_ranking == ()

    def test_empty_signals_returns_frozen(self):
        result = analyze_signals(StructuredSignals())
        assert isinstance(result, SignalInteraction)
        with pytest.raises(AttributeError):
            result.primary_dimension = "x"


# =========================================================================
# 2. Single signal — grievance only
# =========================================================================

class TestGrievanceOnly:
    def test_grievance_only(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        result = analyze_signals(StructuredSignals(grievance=g))
        assert result.overlap_tags == ()
        assert result.primary_dimension == "grievance"
        assert result.confidence_ranking == ("grievance",)

    def test_grievance_low_confidence(self):
        g = Signal(value="ignored", confidence=0.3, source="test")
        result = analyze_signals(StructuredSignals(grievance=g))
        assert result.overlap_tags == ()
        assert result.primary_dimension == "grievance"
        assert result.confidence_ranking == ("grievance",)


# =========================================================================
# 3. Single signal — decision only
# =========================================================================

class TestDecisionOnly:
    def test_decision_only(self):
        d = Signal(value="compare", confidence=0.85, source="test")
        result = analyze_signals(StructuredSignals(decision=d))
        assert result.overlap_tags == ()
        assert result.primary_dimension == "decision"
        assert result.confidence_ranking == ("decision",)

    def test_decision_with_target(self):
        d = Signal(value="compare", confidence=0.9, source="test", target="CSE vs ECE")
        result = analyze_signals(StructuredSignals(decision=d))
        assert result.overlap_tags == ()
        assert result.primary_dimension == "decision"
        assert result.confidence_ranking == ("decision",)


# =========================================================================
# 4. Single signal — emotion only
# =========================================================================

class TestEmotionOnly:
    def test_emotion_only(self):
        e = Signal(value="anxiety", confidence=0.75, source="test")
        result = analyze_signals(StructuredSignals(emotion=e))
        assert result.overlap_tags == ()
        assert result.primary_dimension == "emotion"
        assert result.confidence_ranking == ("emotion",)

    def test_emotion_frustration(self):
        e = Signal(value="frustration", confidence=0.85, source="test")
        result = analyze_signals(StructuredSignals(emotion=e))
        assert result.overlap_tags == ()
        assert result.primary_dimension == "emotion"
        assert result.confidence_ranking == ("emotion",)


# =========================================================================
# 5. Two signals — grievance + decision
# =========================================================================

class TestGrievanceDecision:
    def test_grievance_and_decision(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        d = Signal(value="compare", confidence=0.85, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, decision=d))
        assert result.overlap_tags == ("decision+grievance",)
        assert result.primary_dimension == "grievance"
        assert result.confidence_ranking == ("grievance", "decision")

    def test_decision_higher_than_grievance(self):
        g = Signal(value="waiting", confidence=0.6, source="test")
        d = Signal(value="compare", confidence=0.95, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, decision=d))
        assert result.overlap_tags == ("decision+grievance",)
        assert result.primary_dimension == "decision"
        assert result.confidence_ranking == ("decision", "grievance")


# =========================================================================
# 6. Two signals — grievance + emotion
# =========================================================================

class TestGrievanceEmotion:
    def test_grievance_and_emotion(self):
        g = Signal(value="ignored", confidence=0.9, source="test")
        e = Signal(value="anxiety", confidence=0.8, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, emotion=e))
        assert result.overlap_tags == ("emotion+grievance",)
        assert result.primary_dimension == "grievance"
        assert result.confidence_ranking == ("grievance", "emotion")

    def test_emotion_higher_than_grievance(self):
        g = Signal(value="waiting", confidence=0.5, source="test")
        e = Signal(value="frustration", confidence=0.85, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, emotion=e))
        assert result.overlap_tags == ("emotion+grievance",)
        assert result.primary_dimension == "emotion"
        assert result.confidence_ranking == ("emotion", "grievance")


# =========================================================================
# 7. Two signals — decision + emotion
# =========================================================================

class TestDecisionEmotion:
    def test_decision_and_emotion(self):
        d = Signal(value="choose", confidence=0.85, source="test")
        e = Signal(value="confusion", confidence=0.8, source="test")
        result = analyze_signals(StructuredSignals(decision=d, emotion=e))
        assert result.overlap_tags == ("decision+emotion",)
        assert result.primary_dimension == "decision"
        assert result.confidence_ranking == ("decision", "emotion")

    def test_emotion_higher_than_decision(self):
        d = Signal(value="recommend", confidence=0.6, source="test")
        e = Signal(value="anxiety", confidence=0.85, source="test")
        result = analyze_signals(StructuredSignals(decision=d, emotion=e))
        assert result.overlap_tags == ("decision+emotion",)
        assert result.primary_dimension == "emotion"
        assert result.confidence_ranking == ("emotion", "decision")


# =========================================================================
# 8. Three signals
# =========================================================================

class TestAllThree:
    def test_all_three_grievance_highest(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        d = Signal(value="compare", confidence=0.85, source="test")
        e = Signal(value="anxiety", confidence=0.8, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, decision=d, emotion=e))
        assert result.overlap_tags == ("decision+emotion+grievance",)
        assert result.primary_dimension == "grievance"
        assert result.confidence_ranking == ("grievance", "decision", "emotion")

    def test_all_three_emotion_highest(self):
        g = Signal(value="waiting", confidence=0.6, source="test")
        d = Signal(value="compare", confidence=0.7, source="test")
        e = Signal(value="frustration", confidence=0.9, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, decision=d, emotion=e))
        assert result.overlap_tags == ("decision+emotion+grievance",)
        assert result.primary_dimension == "emotion"
        assert result.confidence_ranking == ("emotion", "decision", "grievance")

    def test_all_three_decision_highest(self):
        g = Signal(value="waiting", confidence=0.5, source="test")
        d = Signal(value="tradeoff", confidence=0.95, source="test")
        e = Signal(value="anxiety", confidence=0.6, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, decision=d, emotion=e))
        assert result.overlap_tags == ("decision+emotion+grievance",)
        assert result.primary_dimension == "decision"
        assert result.confidence_ranking == ("decision", "emotion", "grievance")


# =========================================================================
# 9. Confidence ranking
# =========================================================================

class TestConfidenceRanking:
    def test_ranking_descending(self):
        g = Signal(value="waiting", confidence=0.5, source="test")
        d = Signal(value="compare", confidence=0.9, source="test")
        e = Signal(value="anxiety", confidence=0.7, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, decision=d, emotion=e))
        assert result.confidence_ranking == ("decision", "emotion", "grievance")

    def test_ranking_all_same_confidence(self):
        g = Signal(value="waiting", confidence=0.8, source="test")
        d = Signal(value="compare", confidence=0.8, source="test")
        e = Signal(value="anxiety", confidence=0.8, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, decision=d, emotion=e))
        # Tie-breaking: grievance > decision > emotion
        assert result.confidence_ranking == ("grievance", "decision", "emotion")
        assert result.primary_dimension == "grievance"


# =========================================================================
# 10. Deterministic tie-breaking
# =========================================================================

class TestTieBreaking:
    def test_grievance_wins_tie_over_decision(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        d = Signal(value="compare", confidence=0.9, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, decision=d))
        assert result.primary_dimension == "grievance"
        assert result.confidence_ranking == ("grievance", "decision")

    def test_decision_wins_tie_over_emotion(self):
        d = Signal(value="compare", confidence=0.85, source="test")
        e = Signal(value="anxiety", confidence=0.85, source="test")
        result = analyze_signals(StructuredSignals(decision=d, emotion=e))
        assert result.primary_dimension == "decision"
        assert result.confidence_ranking == ("decision", "emotion")

    def test_grievance_wins_tie_over_emotion(self):
        g = Signal(value="waiting", confidence=0.7, source="test")
        e = Signal(value="anxiety", confidence=0.7, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, emotion=e))
        assert result.primary_dimension == "grievance"
        assert result.confidence_ranking == ("grievance", "emotion")

    def test_three_way_tie_grievance_wins(self):
        g = Signal(value="waiting", confidence=0.8, source="test")
        d = Signal(value="compare", confidence=0.8, source="test")
        e = Signal(value="anxiety", confidence=0.8, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, decision=d, emotion=e))
        assert result.primary_dimension == "grievance"
        assert result.confidence_ranking == ("grievance", "decision", "emotion")


# =========================================================================
# 11. Frozen dataclass behavior
# =========================================================================

class TestFrozenBehavior:
    def test_result_is_frozen(self):
        result = analyze_signals(StructuredSignals())
        assert isinstance(result, SignalInteraction)
        with pytest.raises(AttributeError):
            result.overlap_tags = ()

    def test_result_is_frozen_with_signals(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        result = analyze_signals(StructuredSignals(grievance=g))
        with pytest.raises(AttributeError):
            result.primary_dimension = "x"

    def test_overlap_tags_is_tuple(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        d = Signal(value="compare", confidence=0.85, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, decision=d))
        assert isinstance(result.overlap_tags, tuple)

    def test_confidence_ranking_is_tuple(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        result = analyze_signals(StructuredSignals(grievance=g))
        assert isinstance(result.confidence_ranking, tuple)


# =========================================================================
# 12. Pure-function behavior
# =========================================================================

class TestPureFunction:
    def test_does_not_modify_input_signals(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        d = Signal(value="compare", confidence=0.85, source="test")
        e = Signal(value="anxiety", confidence=0.8, source="test")
        sig = StructuredSignals(grievance=g, decision=d, emotion=e)

        result1 = analyze_signals(sig)
        result2 = analyze_signals(sig)

        # Same results both times
        assert result1 == result2
        # Input unchanged
        assert sig.grievance is g
        assert sig.decision is d
        assert sig.emotion is e

    def test_same_input_same_output(self):
        sig = StructuredSignals(
            grievance=Signal(value="waiting", confidence=0.9, source="test")
        )
        r1 = analyze_signals(sig)
        r2 = analyze_signals(sig)
        assert r1.overlap_tags == r2.overlap_tags
        assert r1.primary_dimension == r2.primary_dimension
        assert r1.confidence_ranking == r2.confidence_ranking

    def test_different_inputs_different_outputs(self):
        sig1 = StructuredSignals(
            grievance=Signal(value="waiting", confidence=0.9, source="test")
        )
        sig2 = StructuredSignals(
            decision=Signal(value="compare", confidence=0.9, source="test")
        )
        r1 = analyze_signals(sig1)
        r2 = analyze_signals(sig2)
        assert r1.primary_dimension != r2.primary_dimension


# =========================================================================
# 13. Overlap tag alphabetical ordering
# =========================================================================

class TestOverlapTagOrdering:
    def test_two_signal_tag_alphabetical(self):
        """Tags are sorted alphabetically, not by confidence."""
        g = Signal(value="waiting", confidence=0.9, source="test")
        e = Signal(value="anxiety", confidence=0.5, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, emotion=e))
        # "grievance+emotion" not "emotion+grievance"
        assert result.overlap_tags == ("emotion+grievance",)

    def test_three_signal_tag_alphabetical(self):
        g = Signal(value="waiting", confidence=0.5, source="test")
        d = Signal(value="compare", confidence=0.9, source="test")
        e = Signal(value="anxiety", confidence=0.7, source="test")
        result = analyze_signals(StructuredSignals(grievance=g, decision=d, emotion=e))
        # Alphabetical: decision, emotion, grievance → sorted
        assert result.overlap_tags == ("decision+emotion+grievance",)


# =========================================================================
# 14. Edge cases
# =========================================================================

class TestEdgeCases:
    def test_all_none_fields(self):
        sig = StructuredSignals(grievance=None, decision=None, emotion=None)
        result = analyze_signals(sig)
        assert result.overlap_tags == ()
        assert result.primary_dimension == "none"
        assert result.confidence_ranking == ()

    def test_zero_confidence_signals(self):
        g = Signal(value="waiting", confidence=0.0, source="test")
        result = analyze_signals(StructuredSignals(grievance=g))
        # Signal is present (not None), even if confidence is 0
        assert result.overlap_tags == ()
        assert result.primary_dimension == "grievance"
        assert result.confidence_ranking == ("grievance",)

    def test_max_confidence(self):
        g = Signal(value="waiting", confidence=1.0, source="test")
        result = analyze_signals(StructuredSignals(grievance=g))
        assert result.primary_dimension == "grievance"
        assert result.confidence_ranking == ("grievance",)
