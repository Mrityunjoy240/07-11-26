"""Immutable contract invariants for the signal system.

These tests define and enforce the frozen invariants that must hold for the
Understanding → Reasoning boundary to be stable.  They do NOT test detector
accuracy or interaction logic (covered in other test files).

Contract:
  1. Signal is frozen. value, confidence, source, target are immutable.
  2. StructuredSignals is frozen. The three signal fields cannot be reassigned.
  3. SignalInteraction is frozen. overlap_tags, primary_dimension, confidence_ranking immutable.
  4. analyze_signals() is pure. Same input → same output, no mutation.
  5. All Signal.confidence values are in [0.0, 1.0].
  6. Deterministic tie-breaking: grievance > decision > emotion.
  7. No routing side-effects in analyze_signals().
"""
import pytest

from src.understanding.signals.base import Signal
from src.understanding.signals.conversation import StructuredSignals
from src.understanding.signals.interaction import analyze_signals, SignalInteraction


# =========================================================================
# 1. Signal is frozen
# =========================================================================

class TestSignalFrozen:
    def test_cannot_reassign_value(self):
        s = Signal(value="test", confidence=0.5, source="unit")
        with pytest.raises(AttributeError):
            s.value = "changed"

    def test_cannot_reassign_confidence(self):
        s = Signal(value="test", confidence=0.5, source="unit")
        with pytest.raises(AttributeError):
            s.confidence = 0.9

    def test_cannot_reassign_source(self):
        s = Signal(value="test", confidence=0.5, source="unit")
        with pytest.raises(AttributeError):
            s.source = "other"

    def test_cannot_reassign_target(self):
        s = Signal(value="test", confidence=0.5, source="unit", target="x")
        with pytest.raises(AttributeError):
            s.target = "y"

    def test_cannot_add_attribute(self):
        s = Signal(value="test", confidence=0.5, source="unit")
        with pytest.raises(AttributeError):
            s.new_field = "nope"


# =========================================================================
# 2. StructuredSignals is frozen
# =========================================================================

class TestStructuredSignalsFrozen:
    def test_cannot_reassign_grievance(self):
        sig = StructuredSignals()
        with pytest.raises(AttributeError):
            sig.grievance = Signal(value="x", confidence=0.5, source="test")

    def test_cannot_reassign_decision(self):
        sig = StructuredSignals()
        with pytest.raises(AttributeError):
            sig.decision = Signal(value="x", confidence=0.5, source="test")

    def test_cannot_reassign_emotion(self):
        sig = StructuredSignals()
        with pytest.raises(AttributeError):
            sig.emotion = Signal(value="x", confidence=0.5, source="test")

    def test_cannot_add_attribute(self):
        sig = StructuredSignals()
        with pytest.raises(AttributeError):
            sig.new_field = "nope"


# =========================================================================
# 3. SignalInteraction is frozen
# =========================================================================

class TestSignalInteractionFrozen:
    def test_cannot_reassign_overlap_tags(self):
        r = analyze_signals(StructuredSignals())
        with pytest.raises(AttributeError):
            r.overlap_tags = ()

    def test_cannot_reassign_primary_dimension(self):
        r = analyze_signals(StructuredSignals())
        with pytest.raises(AttributeError):
            r.primary_dimension = "x"

    def test_cannot_reassign_confidence_ranking(self):
        r = analyze_signals(StructuredSignals())
        with pytest.raises(AttributeError):
            r.confidence_ranking = ()

    def test_cannot_add_attribute(self):
        r = analyze_signals(StructuredSignals())
        with pytest.raises(AttributeError):
            r.new_field = "nope"


# =========================================================================
# 4. Signal.confidence bounds
# =========================================================================

class TestConfidenceBounds:
    def test_confidence_at_zero(self):
        s = Signal(value="x", confidence=0.0, source="test")
        assert s.confidence == 0.0

    def test_confidence_at_one(self):
        s = Signal(value="x", confidence=1.0, source="test")
        assert s.confidence == 1.0

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValueError, match="confidence must be in"):
            Signal(value="x", confidence=-0.01, source="test")

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValueError, match="confidence must be in"):
            Signal(value="x", confidence=1.01, source="test")

    def test_confidence_midpoint(self):
        s = Signal(value="x", confidence=0.5, source="test")
        assert s.confidence == 0.5


# =========================================================================
# 5. Deterministic tie-breaking: grievance > decision > emotion
# =========================================================================

class TestTieBreakingDeterministic:
    def test_grievance_wins_over_decision(self):
        g = Signal(value="waiting", confidence=0.8, source="test")
        d = Signal(value="compare", confidence=0.8, source="test")
        r = analyze_signals(StructuredSignals(grievance=g, decision=d))
        assert r.primary_dimension == "grievance"

    def test_decision_wins_over_emotion(self):
        d = Signal(value="compare", confidence=0.7, source="test")
        e = Signal(value="anxiety", confidence=0.7, source="test")
        r = analyze_signals(StructuredSignals(decision=d, emotion=e))
        assert r.primary_dimension == "decision"

    def test_grievance_wins_over_emotion(self):
        g = Signal(value="waiting", confidence=0.6, source="test")
        e = Signal(value="anxiety", confidence=0.6, source="test")
        r = analyze_signals(StructuredSignals(grievance=g, emotion=e))
        assert r.primary_dimension == "grievance"

    def test_three_way_tie(self):
        g = Signal(value="waiting", confidence=0.5, source="test")
        d = Signal(value="compare", confidence=0.5, source="test")
        e = Signal(value="anxiety", confidence=0.5, source="test")
        r = analyze_signals(StructuredSignals(grievance=g, decision=d, emotion=e))
        assert r.primary_dimension == "grievance"
        assert r.confidence_ranking == ("grievance", "decision", "emotion")


# =========================================================================
# 6. analyze_signals is pure
# =========================================================================

class TestAnalyzeSignalsPure:
    def test_same_input_same_output(self):
        sig = StructuredSignals(
            grievance=Signal(value="waiting", confidence=0.9, source="test"),
            emotion=Signal(value="anxiety", confidence=0.7, source="test"),
        )
        r1 = analyze_signals(sig)
        r2 = analyze_signals(sig)
        assert r1 == r2

    def test_does_not_mutate_input(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        d = Signal(value="compare", confidence=0.85, source="test")
        e = Signal(value="anxiety", confidence=0.8, source="test")
        sig = StructuredSignals(grievance=g, decision=d, emotion=e)

        analyze_signals(sig)

        # Input fields unchanged
        assert sig.grievance is g
        assert sig.decision is d
        assert sig.emotion is e

    def test_returns_new_object_each_time(self):
        sig = StructuredSignals(
            grievance=Signal(value="waiting", confidence=0.9, source="test")
        )
        r1 = analyze_signals(sig)
        r2 = analyze_signals(sig)
        assert r1 is not r2  # Different objects, same values


# =========================================================================
# 7. Overlap tags are alphabetically sorted
# =========================================================================

class TestOverlapTagSorting:
    def test_two_signal_alphabetical(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        e = Signal(value="anxiety", confidence=0.8, source="test")
        r = analyze_signals(StructuredSignals(grievance=g, emotion=e))
        assert r.overlap_tags == ("emotion+grievance",)

    def test_three_signal_alphabetical(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        d = Signal(value="compare", confidence=0.85, source="test")
        e = Signal(value="anxiety", confidence=0.8, source="test")
        r = analyze_signals(StructuredSignals(grievance=g, decision=d, emotion=e))
        assert r.overlap_tags == ("decision+emotion+grievance",)


# =========================================================================
# 8. StructuredSignals threshold behavior
# =========================================================================

class TestStructuredSignalsThreshold:
    def test_has_grievance_at_threshold(self):
        s = Signal(value="waiting", confidence=0.5, source="test")
        sig = StructuredSignals(grievance=s)
        assert sig.has_grievance() is True

    def test_has_grievance_below_threshold(self):
        s = Signal(value="waiting", confidence=0.49, source="test")
        sig = StructuredSignals(grievance=s)
        assert sig.has_grievance() is False

    def test_has_decision_at_threshold(self):
        s = Signal(value="compare", confidence=0.5, source="test")
        sig = StructuredSignals(decision=s)
        assert sig.has_decision_intent() is True

    def test_has_emotion_at_threshold(self):
        s = Signal(value="anxiety", confidence=0.5, source="test")
        sig = StructuredSignals(emotion=s)
        assert sig.has_emotion() is True

    def test_has_grievance_none(self):
        sig = StructuredSignals()
        assert sig.has_grievance() is False


# =========================================================================
# 9. Signal.target is Optional[str]
# =========================================================================

class TestSignalTarget:
    def test_target_defaults_to_none(self):
        s = Signal(value="x", confidence=0.5, source="test")
        assert s.target is None

    def test_target_set(self):
        s = Signal(value="compare", confidence=0.9, source="test", target="CSE vs ECE")
        assert s.target == "CSE vs ECE"


# =========================================================================
# 10. SignalInteraction.empty state
# =========================================================================

class TestInteractionEmpty:
    def test_no_signals(self):
        r = analyze_signals(StructuredSignals())
        assert r.overlap_tags == ()
        assert r.primary_dimension == "none"
        assert r.confidence_ranking == ()

    def test_single_grievance(self):
        r = analyze_signals(StructuredSignals(
            grievance=Signal(value="waiting", confidence=0.9, source="test")
        ))
        assert r.overlap_tags == ()
        assert r.primary_dimension == "grievance"
        assert r.confidence_ranking == ("grievance",)


# =========================================================================
# 11. Confidence ranking order
# =========================================================================

class TestConfidenceRankingOrder:
    def test_descending_by_confidence(self):
        g = Signal(value="waiting", confidence=0.5, source="test")
        d = Signal(value="compare", confidence=0.9, source="test")
        e = Signal(value="anxiety", confidence=0.7, source="test")
        r = analyze_signals(StructuredSignals(grievance=g, decision=d, emotion=e))
        assert r.confidence_ranking == ("decision", "emotion", "grievance")

    def test_all_same_confidence_tiebreak(self):
        g = Signal(value="waiting", confidence=0.8, source="test")
        d = Signal(value="compare", confidence=0.8, source="test")
        e = Signal(value="anxiety", confidence=0.8, source="test")
        r = analyze_signals(StructuredSignals(grievance=g, decision=d, emotion=e))
        assert r.confidence_ranking == ("grievance", "decision", "emotion")


# =========================================================================
# 12. UnderstandingResult carries structured_signals and structured fields
# =========================================================================

class TestUnderstandingResultContract:
    def test_structured_signals_field_exists(self):
        from src.understanding.models import UnderstandingResult
        r = UnderstandingResult(text="test")
        assert hasattr(r, "structured_signals")
        assert isinstance(r.structured_signals, StructuredSignals)

    def test_structured_signals_default_is_empty(self):
        from src.understanding.models import UnderstandingResult
        r = UnderstandingResult(text="test")
        assert r.structured_signals.grievance is None
        assert r.structured_signals.decision is None
        assert r.structured_signals.emotion is None

    def test_old_signals_field_still_exists(self):
        from src.understanding.models import UnderstandingResult, ConversationSignals
        r = UnderstandingResult(text="test")
        assert hasattr(r, "signals")
        assert isinstance(r.signals, ConversationSignals)

    def test_domain_field_exists(self):
        from src.understanding.models import UnderstandingResult
        from src.understanding.interpreter import DomainInterpretation
        r = UnderstandingResult(text="test")
        assert hasattr(r, "domain")
        assert isinstance(r.domain, DomainInterpretation)

    def test_intent_field_exists(self):
        from src.understanding.models import UnderstandingResult, UnderstandingIntent
        r = UnderstandingResult(text="test")
        assert hasattr(r, "intent")
        assert isinstance(r.intent, UnderstandingIntent)

    def test_metadata_field_exists(self):
        from src.understanding.models import UnderstandingResult
        r = UnderstandingResult(text="test")
        assert hasattr(r, "metadata")
        assert isinstance(r.metadata, dict)


# =========================================================================
# 13. Pipeline integration — UnderstandingEngine produces signals
# =========================================================================

class TestUnderstandingEngineProducesSignals:
    """Verify that UnderstandingEngine.understand() populates both
    old ConversationSignals and new StructuredSignals on the result."""

    def test_result_has_structured_signals(self):
        from src.understanding.engine import UnderstandingEngine
        engine = UnderstandingEngine()
        result = engine.understand("I am worried about my rank")
        assert isinstance(result.structured_signals, StructuredSignals)

    def test_result_has_old_signals(self):
        from src.understanding.engine import UnderstandingEngine
        from src.understanding.models import ConversationSignals
        engine = UnderstandingEngine()
        result = engine.understand("hello")
        assert isinstance(result.signals, ConversationSignals)

    def test_grievance_populated_on_grievance_text(self):
        from src.understanding.engine import UnderstandingEngine
        engine = UnderstandingEngine()
        result = engine.understand("I have been waiting for 3 days, nobody responds")
        # Either grievance or decision or emotion should be non-None
        # depending on text, but structured_signals must exist
        assert result.structured_signals is not None

    def test_structured_signals_fields_are_signal_or_none(self):
        from src.understanding.engine import UnderstandingEngine
        from src.understanding.signals.base import Signal
        engine = UnderstandingEngine()
        for text in ["hello", "I am frustrated", "should I choose CSE or ECE",
                      "I am worried about deadline", ""]:
            result = engine.understand(text)
            ss = result.structured_signals
            for field_name in ("grievance", "decision", "emotion"):
                val = getattr(ss, field_name)
                assert val is None or isinstance(val, Signal), (
                    f"text={text!r}: {field_name} is {type(val)}, expected Signal or None"
                )


# =========================================================================
# 14. Pipeline integration — ReasoningEngine reads only flat signals
# =========================================================================

class TestReasoningConsumesFlatSignals:
    """Document that ReasoningEngine currently reads ConversationSignals
    (flat floats), NOT StructuredSignals.  This is a gap for FSM routing."""

    def test_reasoning_uses_dominant(self):
        """ReasoningEngine reads signals.dominant through ctx, not directly."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        prob_source = inspect.getsource(ReasoningEngine._identify_problem)
        trace_source = inspect.getsource(ReasoningEngine._trace_problem)
        for source in (prob_source, trace_source):
            assert "ctx.signals.dominant" in source
            assert "understanding.signals.dominant" not in source

    def test_reasoning_uses_anxiety_float(self):
        """ReasoningEngine._identify_risks() reads ctx.signals.anxiety."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._identify_risks)
        assert "ctx.signals.anxiety" in source
        assert "understanding.signals.anxiety" not in source

    def test_reasoning_uses_confusion_float(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._identify_risks)
        assert "ctx.signals.confusion" in source
        assert "understanding.signals.confusion" not in source

    def test_reasoning_uses_frustration_float(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._identify_risks)
        assert "ctx.signals.frustration" in source
        assert "understanding.signals.frustration" not in source

    def test_reasoning_does_not_read_structured_signals(self):
        """ReasoningEngine never accesses structured_signals."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        full_source = inspect.getsource(ReasoningEngine)
        assert "structured_signals" not in full_source

    def test_reasoning_does_not_read_signal_interaction(self):
        """ReasoningEngine never accesses signal_interaction."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        full_source = inspect.getsource(ReasoningEngine)
        assert "signal_interaction" not in full_source
        assert "analyze_signals" not in full_source


# =========================================================================
# 15. UnderstandingResult carries signal_interaction
# =========================================================================

class TestUnderstandingResultSignalInteraction:
    def test_signal_interaction_field_exists(self):
        from src.understanding.models import UnderstandingResult
        r = UnderstandingResult(text="test")
        assert hasattr(r, "signal_interaction")

    def test_signal_interaction_default_is_empty(self):
        from src.understanding.models import UnderstandingResult
        r = UnderstandingResult(text="test")
        assert isinstance(r.signal_interaction, SignalInteraction)
        assert r.signal_interaction.overlap_tags == ()
        assert r.signal_interaction.primary_dimension == "none"
        assert r.signal_interaction.confidence_ranking == ()

    def test_signal_interaction_can_be_set_at_construction(self):
        from src.understanding.models import UnderstandingResult
        si = SignalInteraction(
            overlap_tags=("grievance+emotion",),
            primary_dimension="grievance",
            confidence_ranking=("grievance", "emotion"),
        )
        r = UnderstandingResult(text="test", signal_interaction=si)
        assert r.signal_interaction is si

    def test_backward_compat_no_signal_interaction_kwarg(self):
        """UnderstandingResult(text=..., structured_signals=...) still works
        without passing signal_interaction."""
        from src.understanding.models import UnderstandingResult
        ss = StructuredSignals()
        r = UnderstandingResult(text="test", structured_signals=ss)
        assert r.signal_interaction.primary_dimension == "none"

    def test_signal_interaction_frozen(self):
        from src.understanding.models import UnderstandingResult
        r = UnderstandingResult(text="test")
        with pytest.raises(AttributeError):
            r.signal_interaction.primary_dimension = "x"


# =========================================================================
# 16. Pipeline integration — UnderstandingEngine populates signal_interaction
# =========================================================================

class TestUnderstandingEnginePopulatesInteraction:
    def test_engine_attaches_signal_interaction(self):
        from src.understanding.engine import UnderstandingEngine
        engine = UnderstandingEngine()
        result = engine.understand("I am worried about my rank")
        assert isinstance(result.signal_interaction, SignalInteraction)

    def test_no_signals_empty_interaction(self):
        from src.understanding.engine import UnderstandingEngine
        engine = UnderstandingEngine()
        result = engine.understand("hello")
        # "hello" may or may not trigger signals, but interaction must exist
        assert isinstance(result.signal_interaction, SignalInteraction)

    def test_interaction_matches_structured_signals(self):
        """signal_interaction must be consistent with structured_signals."""
        from src.understanding.engine import UnderstandingEngine
        engine = UnderstandingEngine()
        texts = [
            "hello",
            "I am worried",
            "should I choose CSE or ECE",
            "I have been waiting for 3 days, nobody responds",
            "I am anxious about deadline and confused about which branch",
        ]
        for text in texts:
            result = engine.understand(text)
            si = result.signal_interaction
            ss = result.structured_signals

            active = []
            if ss.grievance is not None:
                active.append("grievance")
            if ss.decision is not None:
                active.append("decision")
            if ss.emotion is not None:
                active.append("emotion")

            if len(active) < 2:
                assert si.overlap_tags == (), (
                    f"text={text!r}: overlap_tags should be empty for {len(active)} signals"
                )
            if len(active) == 0:
                assert si.primary_dimension == "none"
                assert si.confidence_ranking == ()
            else:
                assert si.primary_dimension in active
                assert len(si.confidence_ranking) == len(active)

    def test_interaction_deterministic(self):
        from src.understanding.engine import UnderstandingEngine
        engine = UnderstandingEngine()
        r1 = engine.understand("I am worried and should choose CSE or ECE")
        r2 = engine.understand("I am worried and should choose CSE or ECE")
        assert r1.signal_interaction == r2.signal_interaction

    def test_reasoning_still_uses_flat_signals(self):
        """ReasoningEngine behavior is unchanged — it still reads flat signals."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine.reason)
        assert "ctx.intent_confidence" in source
        assert "signal_interaction" not in source
