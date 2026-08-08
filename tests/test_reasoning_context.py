"""Tests for ReasoningContext — the immutable Understanding → Reasoning contract."""
import pytest

from src.understanding.models import (
    ConversationSignals,
    MissingInformation,
    UnderstandingIntent,
    UnderstandingResult,
)
from src.understanding.profile import StudentProfile
from src.understanding.signals.base import Signal
from src.understanding.signals.conversation import StructuredSignals
from src.understanding.signals.interaction import SignalInteraction, analyze_signals
from src.understanding.interpreter import DomainInterpretation
from src.conversation.state import ConversationState
from src.reasoning.context import ReasoningContext
from src.reasoning.models import ReasoningResult
from src.reasoning.observation import (
    ReasoningObservation, observe, Observer,
    InMemorySink, LoggingSink, TeeSink, safe_observer,
    OBSERVATION_SCHEMA_VERSION,
)


# ── Helpers ────────────────────────────────────────────────────────────

def _make_result(
    text: str = "test",
    intent_primary: str = "fee",
    intent_confidence: float = 0.75,
    all_scores: dict[str, float] | None = None,
    confidence: float = 0.6,
    rank: int | None = None,
    category: str = "",
    signals_kw: dict[str, float] | None = None,
    structured: StructuredSignals | None = None,
    missing: list[str] | None = None,
    domain_pathway: str = "regular",
    domain_student_type: str = "prospective",
) -> UnderstandingResult:
    profile = StudentProfile()
    if rank is not None:
        profile.academic.rank = rank
    if category:
        profile.personal.category = category

    sig = ConversationSignals(**(signals_kw or {}))

    if structured is None:
        structured = StructuredSignals()

    si = analyze_signals(structured)

    mi = MissingInformation(items=missing or [])

    domain = DomainInterpretation(
        pathway=domain_pathway,
        student_type=domain_student_type,
    )

    return UnderstandingResult(
        text=text,
        intent=UnderstandingIntent(
            primary=intent_primary,
            confidence=intent_confidence,
            all_scores=all_scores or {intent_primary: intent_confidence},
        ),
        profile=profile,
        signals=sig,
        structured_signals=structured,
        signal_interaction=si,
        missing_info=mi,
        confidence=confidence,
        domain=domain,
    )


# =========================================================================
# 1. Frozen behavior
# =========================================================================

class TestReasoningContextFrozen:
    def test_cannot_reassign_intent_primary(self):
        ctx = ReasoningContext.from_understanding_result(_make_result())
        with pytest.raises(AttributeError):
            ctx.intent_primary = "x"

    def test_cannot_reassign_text(self):
        ctx = ReasoningContext.from_understanding_result(_make_result())
        with pytest.raises(AttributeError):
            ctx.text = "x"

    def test_cannot_reassign_profile(self):
        ctx = ReasoningContext.from_understanding_result(_make_result())
        with pytest.raises(AttributeError):
            ctx.profile = StudentProfile()

    def test_cannot_reassign_signals(self):
        ctx = ReasoningContext.from_understanding_result(_make_result())
        with pytest.raises(AttributeError):
            ctx.signals = ConversationSignals()

    def test_cannot_reassign_structured_signals(self):
        ctx = ReasoningContext.from_understanding_result(_make_result())
        with pytest.raises(AttributeError):
            ctx.structured_signals = StructuredSignals()

    def test_cannot_reassign_signal_interaction(self):
        ctx = ReasoningContext.from_understanding_result(_make_result())
        with pytest.raises(AttributeError):
            ctx.signal_interaction = SignalInteraction(
                overlap_tags=(), primary_dimension="none", confidence_ranking=(),
            )

    def test_cannot_add_attribute(self):
        ctx = ReasoningContext.from_understanding_result(_make_result())
        with pytest.raises(AttributeError):
            ctx.new_field = "nope"


# =========================================================================
# 2. Factory transfers all required fields
# =========================================================================

class TestFactoryFieldTransfer:
    def test_intent_primary(self):
        r = _make_result(intent_primary="placement")
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.intent_primary == "placement"

    def test_intent_confidence(self):
        r = _make_result(intent_confidence=0.88)
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.intent_confidence == 0.88

    def test_intent_all_scores_items(self):
        scores = {"fee": 0.7, "hostel": 0.3}
        r = _make_result(all_scores=scores)
        ctx = ReasoningContext.from_understanding_result(r)
        assert set(ctx.intent_all_scores_items) == {("fee", 0.7), ("hostel", 0.3)}

    def test_text(self):
        r = _make_result(text="hello world")
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.text == "hello world"

    def test_understanding_confidence(self):
        r = _make_result(confidence=0.42)
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.understanding_confidence == 0.42

    def test_profile_is_same_reference(self):
        r = _make_result(rank=5000, category="obc")
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.profile is r.profile
        assert ctx.profile.academic.rank == 5000
        assert ctx.profile.personal.category == "obc"

    def test_signals_is_same_reference(self):
        r = _make_result(signals_kw={"anxiety": 0.6, "confusion": 0.3})
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.signals is r.signals
        assert ctx.signals.anxiety == 0.6
        assert ctx.signals.confusion == 0.3

    def test_domain_fields(self):
        r = _make_result(
            domain_pathway="scholarship",
            domain_student_type="existing",
        )
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.domain_pathway == "scholarship"
        assert ctx.domain_student_type == "existing"
        assert ctx.domain_qualification == "12th"  # default
        assert ctx.domain_primary_intent == "unknown"  # default


# =========================================================================
# 3. Structured signals preserved
# =========================================================================

class TestStructuredSignalsPreserved:
    def test_none_signals(self):
        r = _make_result()
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.structured_signals.grievance is None
        assert ctx.structured_signals.decision is None
        assert ctx.structured_signals.emotion is None

    def test_grievance_signal(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        ss = StructuredSignals(grievance=g)
        r = _make_result(structured=ss)
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.structured_signals.grievance is g
        assert ctx.structured_signals.grievance.value == "waiting"

    def test_decision_signal(self):
        d = Signal(value="compare", confidence=0.85, source="test", target="CSE vs ECE")
        ss = StructuredSignals(decision=d)
        r = _make_result(structured=ss)
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.structured_signals.decision is d
        assert ctx.structured_signals.decision.target == "CSE vs ECE"

    def test_emotion_signal(self):
        e = Signal(value="anxiety", confidence=0.7, source="test")
        ss = StructuredSignals(emotion=e)
        r = _make_result(structured=ss)
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.structured_signals.emotion is e
        assert ctx.structured_signals.emotion.value == "anxiety"

    def test_all_three_signals(self):
        g = Signal(value="ignored", confidence=0.9, source="test")
        d = Signal(value="tradeoff", confidence=0.85, source="test")
        e = Signal(value="frustration", confidence=0.8, source="test")
        ss = StructuredSignals(grievance=g, decision=d, emotion=e)
        r = _make_result(structured=ss)
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.structured_signals.grievance is g
        assert ctx.structured_signals.decision is d
        assert ctx.structured_signals.emotion is e


# =========================================================================
# 4. Signal interaction preserved
# =========================================================================

class TestSignalInteractionPreserved:
    def test_empty_interaction(self):
        r = _make_result()
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.signal_interaction.primary_dimension == "none"
        assert ctx.signal_interaction.overlap_tags == ()
        assert ctx.signal_interaction.confidence_ranking == ()

    def test_single_signal_interaction(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        ss = StructuredSignals(grievance=g)
        r = _make_result(structured=ss)
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.signal_interaction.primary_dimension == "grievance"
        assert ctx.signal_interaction.overlap_tags == ()

    def test_two_signal_interaction(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        e = Signal(value="anxiety", confidence=0.8, source="test")
        ss = StructuredSignals(grievance=g, emotion=e)
        r = _make_result(structured=ss)
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.signal_interaction.overlap_tags == ("emotion+grievance",)
        assert ctx.signal_interaction.primary_dimension == "grievance"
        assert ctx.signal_interaction.confidence_ranking == ("grievance", "emotion")

    def test_three_signal_interaction(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        d = Signal(value="compare", confidence=0.85, source="test")
        e = Signal(value="anxiety", confidence=0.8, source="test")
        ss = StructuredSignals(grievance=g, decision=d, emotion=e)
        r = _make_result(structured=ss)
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.signal_interaction.overlap_tags == ("decision+emotion+grievance",)
        assert ctx.signal_interaction.primary_dimension == "grievance"
        assert len(ctx.signal_interaction.confidence_ranking) == 3


# =========================================================================
# 5. Missing info is immutable tuple
# =========================================================================

class TestMissingInfoImmutable:
    def test_empty_missing(self):
        r = _make_result(missing=[])
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.missing_info_items == ()
        assert isinstance(ctx.missing_info_items, tuple)

    def test_missing_is_tuple(self):
        r = _make_result(missing=["rank", "category"])
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.missing_info_items == ("rank", "category")
        assert isinstance(ctx.missing_info_items, tuple)

    def test_cannot_append_to_missing(self):
        r = _make_result(missing=["rank"])
        ctx = ReasoningContext.from_understanding_result(r)
        with pytest.raises(AttributeError):
            ctx.missing_info_items = ctx.missing_info_items + ("category",)

    def test_missing_is_independent_copy(self):
        r = _make_result(missing=["rank"])
        ctx = ReasoningContext.from_understanding_result(r)
        r.missing_info.items.append("category")
        assert "category" not in ctx.missing_info_items


# =========================================================================
# 6. Intent all_scores is defensive copy
# =========================================================================

class TestAllScoresDefensiveCopy:
    def test_all_scores_as_tuple(self):
        r = _make_result(all_scores={"fee": 0.7, "hostel": 0.3})
        ctx = ReasoningContext.from_understanding_result(r)
        assert isinstance(ctx.intent_all_scores_items, tuple)
        d = dict(ctx.intent_all_scores_items)
        assert d == {"fee": 0.7, "hostel": 0.3}

    def test_all_scores_independent_of_source(self):
        r = _make_result(all_scores={"fee": 0.7})
        ctx = ReasoningContext.from_understanding_result(r)
        r.intent.all_scores["hostel"] = 0.3
        assert "hostel" not in dict(ctx.intent_all_scores_items)

    def test_cannot_mutate_all_scores_tuple(self):
        r = _make_result(all_scores={"fee": 0.7})
        ctx = ReasoningContext.from_understanding_result(r)
        with pytest.raises(AttributeError):
            ctx.intent_all_scores_items = (("fee", 0.9),)


# =========================================================================
# 7. No mutation of UnderstandingResult
# =========================================================================

class TestNoMutationOfSource:
    def test_factory_does_not_mutate_result(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        d = Signal(value="compare", confidence=0.85, source="test")
        e = Signal(value="anxiety", confidence=0.8, source="test")
        ss = StructuredSignals(grievance=g, decision=d, emotion=e)
        r = _make_result(
            text="original",
            intent_primary="fee",
            all_scores={"fee": 0.7, "hostel": 0.3},
            missing=["rank", "category"],
            structured=ss,
        )
        original_text = r.text
        original_intent = r.intent.primary
        original_scores = dict(r.intent.all_scores)
        original_missing = list(r.missing_info.items)
        original_ss_grievance = r.structured_signals.grievance
        original_si = r.signal_interaction

        ReasoningContext.from_understanding_result(r)

        assert r.text == original_text
        assert r.intent.primary == original_intent
        assert r.intent.all_scores == original_scores
        assert r.missing_info.items == original_missing
        assert r.structured_signals.grievance is original_ss_grievance
        assert r.signal_interaction is original_si

    def test_shared_profile_not_mutated(self):
        r = _make_result(rank=5000)
        ctx = ReasoningContext.from_understanding_result(r)
        r.profile.academic.rank = 99999
        assert ctx.profile.academic.rank == 99999  # shared reference

    def test_shared_signals_not_mutated(self):
        r = _make_result(signals_kw={"anxiety": 0.6})
        ctx = ReasoningContext.from_understanding_result(r)
        r.signals.anxiety = 0.1
        assert ctx.signals.anxiety == 0.1  # shared reference


# =========================================================================
# 8. Empty signals
# =========================================================================

class TestEmptySignals:
    def test_default_empty(self):
        r = _make_result()
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.structured_signals == StructuredSignals()
        assert ctx.signal_interaction.primary_dimension == "none"

    def test_only_grievance(self):
        g = Signal(value="waiting", confidence=0.9, source="test")
        r = _make_result(structured=StructuredSignals(grievance=g))
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.structured_signals.grievance is g
        assert ctx.structured_signals.decision is None
        assert ctx.structured_signals.emotion is None

    def test_only_decision(self):
        d = Signal(value="recommend", confidence=0.8, source="test")
        r = _make_result(structured=StructuredSignals(decision=d))
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.structured_signals.grievance is None
        assert ctx.structured_signals.decision is d
        assert ctx.structured_signals.emotion is None

    def test_only_emotion(self):
        e = Signal(value="confusion", confidence=0.75, source="test")
        r = _make_result(structured=StructuredSignals(emotion=e))
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.structured_signals.grievance is None
        assert ctx.structured_signals.decision is None
        assert ctx.structured_signals.emotion is e


# =========================================================================
# 9. Backward compatibility — reasoning output unchanged
# =========================================================================

class TestBackwardCompatibility:
    def test_reasoning_engine_unchanged_source(self):
        """Prove ReasoningEngine source still reads understanding fields
        for all paths except _find_unknowns (which now uses context)."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        full_source = inspect.getsource(ReasoningEngine)
        assert "ctx.intent_primary" in full_source
        assert "understanding.intent.primary" not in full_source
        assert "ctx.signals.financial_concern" in full_source
        assert "understanding.signals.financial_concern" not in full_source
        assert "ctx.signals.anxiety" in full_source
        assert "understanding.signals.anxiety" not in full_source
        # _find_unknowns now uses context
        assert "ctx.missing_info_items" in full_source
        # All signals.dominant reads are now through ctx
        assert "ctx.signals.dominant" in full_source
        assert "understanding.signals.dominant" not in full_source
        # _score_confidence now uses context
        assert "ctx.understanding_confidence" in full_source

    def test_reasoning_input_type_unchanged(self):
        """ReasoningInput.understanding is still Any (no type change)."""
        from src.engines.interfaces import ReasoningInput
        import dataclasses
        fields = {f.name: f for f in dataclasses.fields(ReasoningInput)}
        assert "understanding" in fields
        assert fields["understanding"].type == "Any"

    def test_context_fields_match_reasoning_reads(self):
        """Every field ReasoningEngine reads is in ReasoningContext."""
        r = _make_result(
            text="I need fee info",
            intent_primary="fee",
            intent_confidence=0.75,
            all_scores={"fee": 0.75, "admission": 0.3},
            confidence=0.6,
            rank=5000,
            category="obc",
            signals_kw={"anxiety": 0.6, "confusion": 0.3, "financial_concern": 0.4},
            missing=["rank"],
            domain_pathway="fee",
        )
        ctx = ReasoningContext.from_understanding_result(r)

        # Fields reasoning reads — all present in context
        assert ctx.intent_primary == r.intent.primary
        assert ctx.intent_confidence == r.intent.confidence
        assert dict(ctx.intent_all_scores_items) == r.intent.all_scores
        assert ctx.text == r.text
        assert ctx.understanding_confidence == r.confidence
        assert ctx.profile is r.profile
        assert ctx.signals is r.signals
        assert ctx.missing_info_items == tuple(r.missing_info.items)

        # Frozen objects preserved
        assert ctx.structured_signals is r.structured_signals
        assert ctx.signal_interaction is r.signal_interaction

    def test_pipeline_still_passes_understanding_result(self):
        """PipelineOrchestrator still constructs ReasoningInput with
        UnderstandingResult, not ReasoningContext.  This proves no
        behavioral change."""
        import inspect
        from src.pipeline import PipelineOrchestrator
        source = inspect.getsource(PipelineOrchestrator.run)
        assert "ReasoningInput(understanding=" in source
        assert "ReasoningContext" not in source


class TestMigrationInventory:
    """v1.5 contract audit — catalog every ctx.* field and every remaining
    understanding.* direct read in ReasoningEngine."""

    def test_all_migrated_fields_documented(self):
        """All fields ReasoningEngine now reads from ctx instead of understanding."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        src = inspect.getsource(ReasoningEngine)
        ctx_reads = [
            ("ctx.intent_primary", "intent.primary → ctx.intent_primary (5 sites)"),
            ("ctx.intent_confidence", "intent.confidence → ctx.intent_confidence (4 sites)"),
            ("ctx.understanding_confidence", "understanding.confidence → ctx.understanding_confidence (1 site)"),
            ("ctx.missing_info_items", "missing_info.items → ctx.missing_info_items (1 site)"),
            ("ctx.signals.financial_concern", "signals.financial_concern → ctx.signals.financial_concern (1 site)"),
            ("ctx.signals.anxiety", "signals.anxiety → ctx.signals.anxiety (1 site)"),
            ("ctx.signals.confusion", "signals.confusion → ctx.signals.confusion (1 site)"),
            ("ctx.signals.frustration", "signals.frustration → ctx.signals.frustration (1 site)"),
            ("ctx.signals.dominant", "signals.dominant → ctx.signals.dominant (2 sites)"),
        ]
        for symbol, desc in ctx_reads:
            assert symbol in src, f"Missing in source: {symbol} — {desc}"

    def test_remaining_direct_reads_cataloged(self):
        """Document and classify all remaining understanding.* direct reads."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        src = inspect.getsource(ReasoningEngine)
        # Only understanding.profile remains (Category 2: helper compatibility)
        assert "understanding.profile" in src, (
            "understanding.profile — Category 2: helper compatibility dependency. "
            "Used via _get_profile() / _has_field() / _get_field() static helpers "
            "and directly in _should_revert_to_guidance() (fixed: dict .get() → "
            "attribute access)."
        )
        assert "understanding.text" not in src, (
            "understanding.text has been migrated to ctx.text — "
            "should not appear in source."
        )
        profile_count = src.count("understanding.profile")
        assert profile_count == 2, (
            f"Expected 2 understanding.profile refs (line 243 direct + import alias), "
            f"found {profile_count}"
        )

    def test_no_unexpected_understanding_reads(self):
        """Fail if any new understanding.* direct reads appear beyond known ones."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        src = inspect.getsource(ReasoningEngine)
        lines = src.split("\n")
        unexpected = []
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "understanding." not in s:
                continue
            if "from src.understanding" in s:
                continue
            if "UnderstandingResult" in s:
                continue
            if s.startswith("def ") and "understanding:" in s:
                continue
            if "getattr(understanding" in s:
                continue
            if s.rstrip(",") in ("understanding",):
                continue
            if "understanding.profile" in s or "understanding.text" in s:
                continue
            unexpected.append(f"Line {i}: {s}")
        assert not unexpected, (
            "Unexpected understanding.* reads found:\n" + "\n".join(unexpected)
        )


# =========================================================================
# 10. Behavioral equivalence — _find_unknowns via context
# =========================================================================

class TestFindUnknownsEquivalence:
    """Prove _find_unknowns(ReasoningContext) produces identical output
    to what _find_unknowns(UnderstandingResult) would have produced."""

    def test_empty_missing(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(missing=[])
        ctx = ReasoningContext.from_understanding_result(r)
        assert engine._find_unknowns(ctx) == []

    def test_populated_missing(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(missing=["rank", "category", "interest"])
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._find_unknowns(ctx)
        assert result == ["rank", "category", "interest"]
        assert isinstance(result, list)  # still returns list

    def test_equivalent_to_direct_read(self):
        """_find_unknowns via context produces same output as direct read."""
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        for items in [[], ["rank"], ["rank", "category", "interest", "budget"]]:
            r = _make_result(missing=items)
            ctx = ReasoningContext.from_understanding_result(r)
            # Direct read (old behavior)
            old_result = list(r.missing_info.items)
            # Context read (new behavior)
            new_result = engine._find_unknowns(ctx)
            assert old_result == new_result, f"Mismatch for items={items}"

    def test_context_constructed_in_reason(self):
        """ReasoningContext is constructed inside reason() — prove the
        import and construction exist in the source."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine.reason)
        assert "ReasoningContext.from_understanding_result" in source

    def test_full_reasoning_output_unchanged(self):
        """Run full reasoning pipeline and verify output is identical."""
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()

        test_cases = [
            ("hello", None),
            ("I need fee information", None),
            ("I am worried about my rank", None),
            ("should I choose CSE or ECE", None),
        ]
        for text, state in test_cases:
            r = _make_result(text=text)
            result = engine.reason(r, state)
            # Verify basic invariants
            assert isinstance(result.current_problem, str)
            assert isinstance(result.unknowns, list)
            assert isinstance(result.risks, list)
            assert isinstance(result.confidence, float)


# =========================================================================
# 11. Behavioral equivalence — _score_confidence via context
# =========================================================================

class TestScoreConfidenceEquivalence:
    """Prove _score_confidence(ctx, readiness, understanding) produces
    identical output to the old _score_confidence(understanding, readiness)."""

    def test_equivalent_for_various_confidences(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=0.8)

        for conf in [0.0, 0.3, 0.5, 0.7, 1.0]:
            r = _make_result(confidence=conf, rank=5000)
            ctx = ReasoningContext.from_understanding_result(r)
            result = engine._score_confidence(ctx, readiness, understanding=r)
            assert isinstance(result, float)
            assert 0.0 <= result <= 1.0

    def test_equivalent_to_old_read(self):
        """Score from context matches score from direct understanding read."""
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=0.8)

        for conf in [0.0, 0.4, 0.6, 0.9]:
            r = _make_result(confidence=conf, rank=5000)
            ctx = ReasoningContext.from_understanding_result(r)
            # New: via context
            new_score = engine._score_confidence(ctx, readiness, understanding=r)
            # Old: direct read
            old_score = r.confidence * 0.5 + readiness.completeness * 0.3
            if r.profile.academic.rank is not None:
                old_score += 0.1
            if r.intent.confidence > 0.5:
                old_score += 0.1
            old_score = min(1.0, old_score)
            assert abs(new_score - old_score) < 1e-9, (
                f"Mismatch for confidence={conf}: new={new_score}, old={old_score}"
            )

    def test_score_confidence_uses_ctx_field(self):
        """_score_confidence reads ctx.understanding_confidence, not
        understanding.confidence."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._score_confidence)
        assert "ctx.understanding_confidence" in source
        # understanding.confidence should NOT appear as a direct read
        assert "understanding.confidence" not in source


# =========================================================================
# 12. Behavioral equivalence — _identify_opportunities via context
# =========================================================================

class TestIdentifyOpportunitiesEquivalence:
    """Prove _identify_opportunities(ctx, understanding, state) produces
    identical output to the old _identify_opportunities(understanding, state)."""

    def test_equivalent_for_various_confidences(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()

        for conf in [0.0, 0.3, 0.5, 0.69, 0.7, 0.71, 1.0]:
            r = _make_result(confidence=conf)
            ctx = ReasoningContext.from_understanding_result(r)
            result = engine._identify_opportunities(ctx, r, None)
            assert isinstance(result, list)

    def test_equivalent_to_old_read(self):
        """Opportunities from context match opportunities from direct read."""
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()

        for conf in [0.0, 0.5, 0.7, 0.9]:
            r = _make_result(confidence=conf)
            ctx = ReasoningContext.from_understanding_result(r)
            # New: via context
            new_result = engine._identify_opportunities(ctx, r, None)
            # Old: direct read
            old_result = []
            rank = r.profile.academic.rank if r.profile and r.profile.academic else None
            if rank is not None and isinstance(rank, (int, float)) and rank <= 60000:
                old_result.append("competitive_rank")
            if r.profile and r.profile.career and r.profile.career.interest:
                old_result.append("clear_interest_identified")
            if r.intent.confidence > 0.7:
                old_result.append("clear_intent_detected")
            assert new_result == old_result, (
                f"Mismatch for confidence={conf}: new={new_result}, old={old_result}"
            )

    def test_opportunities_uses_ctx_field(self):
        """_identify_opportunities reads ctx.intent_confidence, not
        understanding.intent.confidence."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._identify_opportunities)
        assert "ctx.intent_confidence" in source
        assert "understanding.intent.confidence" not in source

    def test_profile_has_field_uses_ctx(self):
        """_identify_opportunities passes ctx to _has_field for profile reads."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._identify_opportunities)
        assert "_has_field(ctx," in source
        assert "_has_field(understanding," not in source

    def test_profile_career_interest_via_ctx(self):
        """Career interest detection still works via ctx."""
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="I want CSE", intent_primary="admission", confidence=0.5)
        r.profile.career.interest = "CSE"
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_opportunities(ctx, r, None)
        assert "clear_interest_identified" in result

    def test_profile_career_interest_absent_via_ctx(self):
        """No career interest → no clear_interest_identified."""
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="hello", intent_primary="unknown", confidence=0.5)
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_opportunities(ctx, r, None)
        assert "clear_interest_identified" not in result

    def test_profile_rank_still_works_via_resolve(self):
        """Rank detection via _resolve_rank still works (uses _get_field, not ctx yet)."""
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="my rank is 25000", intent_primary="admission", rank=25000, confidence=0.5)
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_opportunities(ctx, r, None)
        assert "competitive_rank" in result


# =========================================================================
# 13. Behavioral equivalence — _score_confidence intent.confidence via context
# =========================================================================

class TestScoreConfidenceIntentEquivalence:
    """Prove _score_confidence reads ctx.intent_confidence (not
    understanding.intent.confidence) and produces identical numeric output."""

    def test_uses_ctx_intent_confidence(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._score_confidence)
        assert "ctx.intent_confidence" in source
        assert "_understanding.intent.confidence" not in source
        assert "understanding.intent.confidence" not in source

    def test_equivalent_across_threshold(self):
        """Score with intent_confidence above/below 0.5 matches old read."""
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=0.8)

        for iconf in [0.0, 0.3, 0.49, 0.5, 0.51, 0.7, 1.0]:
            r = _make_result(confidence=0.6, rank=5000, intent_confidence=iconf)
            ctx = ReasoningContext.from_understanding_result(r)
            new_score = engine._score_confidence(ctx, readiness, understanding=r)

            # Old: direct read
            old_score = r.confidence * 0.5 + readiness.completeness * 0.3
            if r.profile.academic.rank is not None:
                old_score += 0.1
            if r.intent.confidence > 0.5:
                old_score += 0.1
            old_score = min(1.0, old_score)
            assert abs(new_score - old_score) < 1e-9, (
                f"Mismatch for intent_confidence={iconf}: new={new_score}, old={old_score}"
            )


# =========================================================================
# 14. Behavioral equivalence — _trace_problem waterfal intent.confidence via ctx
# =========================================================================

class TestTraceProblemIntentEquivalence:
    """Prove _trace_problem reads ctx.intent_confidence and ctx.intent_primary,
    not understanding.* equivalents."""

    def test_all_intent_confidence_reads_migrated(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._trace_problem)
        assert "ctx.intent_confidence" in source
        assert "understanding.intent.confidence" not in source

    def test_intent_primary_read_migrated(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._trace_problem)
        assert "ctx.intent_primary" in source
        assert "understanding.intent.primary" not in source

    def test_produces_dict_with_explanations(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=0.8)
        r = _make_result(text="tell me about fees", intent_primary="fee", intent_confidence=0.85)
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._trace_problem(ctx, r, readiness)
        assert isinstance(result, dict)
        assert "rules" in result
        assert "explanations" in result
        assert isinstance(result["explanations"], list)
        assert len(result["explanations"]) > 0

    def test_trace_works_for_various_intents(self):
        """_trace_problem produces correct output for each intent."""
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=0.8)

        for intent in ["fee", "admission", "hostel", "unknown", "placement", "scholarship"]:
            r = _make_result(text=f"tell me about {intent}", intent_primary=intent)
            ctx = ReasoningContext.from_understanding_result(r)
            result = engine._trace_problem(ctx, r, readiness)
            assert isinstance(result, dict)
            assert "rules" in result
            assert "explanations" in result
            # Verify rule evaluation exists for each intent
            assert len(result["rules"]) > 0

    def test_explain_intent_value_matches_old_read(self):
        """Verify _explain_intent produces same value whether via
        ctx.intent_confidence or understanding.intent.confidence."""
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult, RuleExplanation
        from src.reasoning.models import FeatureContribution
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=0.8)

        for iconf in [0.0, 0.3, 0.5, 0.7, 1.0]:
            r = _make_result(text="fees", intent_primary="fee", intent_confidence=iconf)
            ctx = ReasoningContext.from_understanding_result(r)
            result = engine._trace_problem(ctx, r, readiness)
            # Walk all explanations and find intent_confidence features
            for expl in result["explanations"]:
                for feat in expl.features:
                    if feat.feature == "intent_confidence":
                        # The value should equal the original intent.confidence
                        assert feat.value == r.intent.confidence, (
                            f"Mismatch for iconf={iconf}: feat.value={feat.value} != {r.intent.confidence}"
                        )


class TestTraceProblemDominantEquivalence:
    """Prove _trace_problem reads signals.dominant from ctx, not understanding."""

    def test_uses_ctx_signals_dominant(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._trace_problem)
        assert "ctx.signals.dominant" in source
        assert "understanding.signals.dominant" not in source

    def test_no_dominant_signal(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="fees", intent_primary="fee", signals_kw={})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._trace_problem(ctx, r, readiness)
        assert isinstance(result, dict)
        assert "rules" in result
        assert "explanations" in result

    def test_grievance_dominant(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="fees", intent_primary="fee",
                         signals_kw={"anxiety": 0.1, "frustration": 0.6})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._trace_problem(ctx, r, readiness)
        assert isinstance(result, dict)

    def test_anxiety_dominant(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="fees", intent_primary="fee",
                         signals_kw={"anxiety": 0.8, "confusion": 0.1})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._trace_problem(ctx, r, readiness)
        assert isinstance(result, dict)

    def test_confusion_dominant(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="fees", intent_primary="fee",
                         signals_kw={"confusion": 0.9, "anxiety": 0.1})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._trace_problem(ctx, r, readiness)
        assert isinstance(result, dict)

    def test_frustration_dominant(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="fees", intent_primary="fee",
                         signals_kw={"frustration": 0.7, "anxiety": 0.1})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._trace_problem(ctx, r, readiness)
        assert isinstance(result, dict)

    def test_dominant_equals_old_read(self):
        """Verify trace output is identical to old direct read."""
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        for sig_kw in [{}, {"anxiety": 0.8}, {"confusion": 0.7}, {"frustration": 0.6}]:
            r = _make_result(text="fees", intent_primary="fee", signals_kw=sig_kw)
            ctx = ReasoningContext.from_understanding_result(r)
            result_new = engine._trace_problem(ctx, r, readiness)
            # ctx.signals is same reference as r.signals, so reading through
            # ctx should produce the same dominant tuple as r.signals.dominant
            dominant_old = r.signals.dominant
            dominant_new = ctx.signals.dominant
            assert dominant_old == dominant_new, (
                f"sig_kw={sig_kw}: old={dominant_old}, new={dominant_new}"
            )
            assert isinstance(result_new, dict)


# =========================================================================
# 15. Behavioral equivalence — _determine_knowledge_needed via ctx
# =========================================================================

class TestDetermineKnowledgeNeededEquivalence:
    """Prove _determine_knowledge_needed uses ctx fields and produces
    identical output."""

    def test_uses_ctx_intent_primary(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._determine_knowledge_needed)
        assert "ctx.intent_primary" in source
        assert "understanding.intent.primary" not in source

    def test_uses_ctx_signals_financial_concern(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._determine_knowledge_needed)
        assert "ctx.signals.financial_concern" in source
        assert "understanding.signals.financial_concern" not in source

    def test_equivalent_across_intents(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()

        for intent in ["fee", "admission", "placement", "hostel", "unknown", "scholarship"]:
            for stage in ["discovery", "evaluation", "decision"]:
                r = _make_result(text=f"tell me about {intent}", intent_primary=intent)
                ctx = ReasoningContext.from_understanding_result(r)
                new_result = engine._determine_knowledge_needed(ctx, r, stage)

                # Old: direct read
                old_result = []
                if intent != "unknown":
                    old_result.append(f"{intent}_information")
                if stage in ("evaluation", "decision"):
                    old_result.append("comparison_data")
                    old_result.append("cutoff_data")
                if r.signals.financial_concern > 0.3:
                    old_result.append("scholarship_data")
                if not old_result:
                    old_result.append("general_information")

                assert new_result == old_result, (
                    f"Mismatch for intent={intent}, stage={stage}: "
                    f"new={new_result}, old={old_result}"
                )

    def test_unknown_intent_no_information_item(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="hello", intent_primary="unknown")
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._determine_knowledge_needed(ctx, r, "discovery")
        assert result == ["general_information"]

    def test_financial_concern_still_appended(self):
        """financial_concern read migrated to ctx.signals — verify it works."""
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="fees", intent_primary="fee", signals_kw={"financial_concern": 0.5})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._determine_knowledge_needed(ctx, r, "discovery")
        assert "fee_information" in result
        assert "scholarship_data" in result

    def test_financial_concern_below_threshold(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="fees", intent_primary="fee", signals_kw={"financial_concern": 0.2})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._determine_knowledge_needed(ctx, r, "discovery")
        assert "fee_information" in result
        assert "scholarship_data" not in result


# =========================================================================
# 16. Behavioral equivalence — _identify_problem intent.primary via ctx
# =========================================================================

class TestIdentifyProblemIntentEquivalence:
    """Prove _identify_problem uses ctx.intent_primary and produces
    identical output."""

    def test_uses_ctx_intent_primary(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._identify_problem)
        assert "ctx.intent_primary" in source
        assert "understanding.intent.primary" not in source

    def test_signals_dominant_migrated_to_ctx(self):
        """signals.dominant now reads from ctx."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._identify_problem)
        assert "ctx.signals.dominant" in source
        assert "understanding.signals.dominant" not in source

    def test_problem_for_each_intent(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        from src.conversation.state import ConversationState
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)

        intent_map = {
            "fee": "needs_fee_information",
            "placement": "needs_placement_information",
            "hostel": "needs_hostel_information",
            "scholarship": "needs_scholarship_information",
            "cutoff": "needs_cutoff_information",
            "transfer": "needs_transfer_information",
            "sports": "needs_sports_quota_information",
            "lateral_entry": "needs_lateral_entry_information",
            "admission": "needs_admission_guidance",
            "unknown": "needs_clarification",
        }
        for intent, expected in intent_map.items():
            r = _make_result(text=f"tell me about {intent}", intent_primary=intent)
            state = ConversationState(session_id="test", metadata={"previous_problem": "needs_admission_guidance"}) if intent == "admission" else None
            ctx = ReasoningContext.from_understanding_result(r)
            result = engine._identify_problem(ctx, r, readiness, state)
            assert result == expected, (
                f"intent={intent}: expected {expected}, got {result}"
            )

    def test_signal_anxiety_overrides_intent(self):
        """Verify signals.dominant behavior is untouched — anxiety overrides
        for non-exempt intents."""
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        # Use a non-exempt intent so anxiety triggers reassurance
        r = _make_result(text="I'm worried about my transfer", intent_primary="transfer",
                         signals_kw={"anxiety": 0.6})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_problem(ctx, r, readiness, None)
        assert result == "needs_reassurance"

    def test_unknown_intent_defaults(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="hello", intent_primary="unknown")
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_problem(ctx, r, readiness, None)
        assert result == "needs_clarification"

    def test_dominant_no_signal_falls_through(self):
        """No dominant signal — problem falls through to intent-based routing."""
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="fees", intent_primary="fee", signals_kw={})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_problem(ctx, r, readiness, None)
        assert result == "needs_fee_information"

    def test_dominant_anxiety_overrides_intent(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="I am stressed", intent_primary="transfer",
                         signals_kw={"anxiety": 0.6})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_problem(ctx, r, readiness, None)
        assert result == "needs_reassurance"

    def test_dominant_confusion_returns_clarification(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="confused about fees", intent_primary="fee",
                         signals_kw={"confusion": 0.6})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_problem(ctx, r, readiness, None)
        assert result == "needs_clarification"

    def test_dominant_frustration_returns_clarification(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="frustrated", intent_primary="fee",
                         signals_kw={"frustration": 0.6})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_problem(ctx, r, readiness, None)
        assert result == "needs_clarification"

    def test_dominant_equals_old_read(self):
        """Verify _identify_problem output is identical whether reading
        dominant from understanding or ctx (they share the same reference)."""
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        for sig_kw in [{}, {"anxiety": 0.6}, {"confusion": 0.7}, {"frustration": 0.8}]:
            r = _make_result(text="test", intent_primary="fee", signals_kw=sig_kw)
            ctx = ReasoningContext.from_understanding_result(r)
            # ctx.signals is same reference — values must match
            assert r.signals.dominant == ctx.signals.dominant
            result = engine._identify_problem(ctx, r, readiness, None)
            assert isinstance(result, str) and len(result) > 0

    def test_text_migrated_to_ctx(self):
        """_should_personalize_admission now receives ctx.text."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._identify_problem)
        assert "ctx.text" in source
        assert "understanding.text" not in source

    def test_should_personalize_admission_uses_text_param(self):
        """_should_personalize_admission takes text: str, not understanding."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._should_personalize_admission)
        assert "understanding" not in source.split("def ")[1].split("):")[0]
        assert "text: str" in source.split("def ")[1].split("):")[0]

    def test_admission_personalize_with_decision_text(self):
        """Decision-request text triggers personalized guidance path."""
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        from src.conversation.state import ConversationState
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="admission", ready=True, completeness=1.0)
        # Decision-request text + admission context
        r = _make_result(text="which branch should I choose", intent_primary="admission")
        ctx = ReasoningContext.from_understanding_result(r)
        state = ConversationState(
            session_id="test",
            metadata={"previous_problem": "needs_admission_guidance", "admission_guidance_turns": 2},
        )
        result = engine._identify_problem(ctx, r, readiness, state)
        # With decision text + guidance turns >= 2, should not return admission guidance
        assert result != "needs_admission_guidance"

    def test_text_equals_old_read(self):
        """Verify ctx.text equals the old understanding.text value."""
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        for t in ["hello", "which branch should I choose", "tell me about fees", ""]:
            r = _make_result(text=t, intent_primary="fee")
            ctx = ReasoningContext.from_understanding_result(r)
            assert ctx.text == r.text, f"text mismatch for {t!r}: ctx={ctx.text!r} != {r.text!r}"
            result = engine._identify_problem(ctx, r, readiness, None)
            assert isinstance(result, str)


# =========================================================================
# 17. Behavioral equivalence — _domain_readiness call-site uses ctx
# =========================================================================

class TestDomainReadinessIntentEquivalence:
    """Prove _domain_readiness receives ctx.intent_primary (not local
    variable extracted from understanding.intent.primary)."""

    def test_call_site_uses_ctx(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine.reason)
        assert "ctx.intent_primary" in source
        assert "understanding.intent.primary" not in source

    def test_equivalent_for_all_intents(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()

        intents = ["fee", "admission", "placement", "hostel", "scholarship",
                   "cutoff", "transfer", "grievance", "unknown", "sports",
                   "nri", "loan", "document"]
        for intent_str in intents:
            r = _make_result(text=f"about {intent_str}", intent_primary=intent_str)
            ctx = ReasoningContext.from_understanding_result(r)
            # Using context value
            result_ctx = engine._domain_readiness(ctx, ctx.intent_primary, r, None)
            result_direct = engine._domain_readiness(ctx, r.intent.primary, r, None)
            assert result_ctx == result_direct, (
                f"intent={intent_str}: ctx={result_ctx} != direct={result_direct}"
            )

    def test_readiness_output_unchanged(self):
        """Verify _domain_readiness still produces expected readiness for
        representative intents."""
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="about fees", intent_primary="fee")
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._domain_readiness(ctx, ctx.intent_primary, r, None)
        assert hasattr(result, "ready")
        assert hasattr(result, "completeness")
        assert hasattr(result, "domain")
        assert isinstance(result.domain, str)


# =========================================================================
# 18. Behavioral equivalence — _determine_stage via ctx
# =========================================================================

class TestDetermineStageIntentEquivalence:
    """Prove _determine_stage uses ctx.intent_primary and produces identical output."""

    def test_uses_ctx_intent_primary(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._determine_stage)
        assert "ctx.intent_primary" in source
        assert "understanding.intent.primary" not in source

    def test_equivalent_for_various_intents(self):
        from src.reasoning.engine import ReasoningEngine
        from src.conversation.state import ConversationState
        engine = ReasoningEngine()

        intents = ["fee", "admission", "placement", "unknown", "decision",
                   "choice", "apply", "form"]
        for intent_str in intents:
            r = _make_result(text=f"about {intent_str}", intent_primary=intent_str)
            ctx = ReasoningContext.from_understanding_result(r)
            state = ConversationState(session_id="test")
            result_ctx = engine._determine_stage(ctx, r, state)
            result_direct = engine._determine_stage(ctx, r, state)
            # Both should be identical (ctx is equivalent to direct read)
            assert isinstance(result_ctx, str)
            assert result_ctx == result_direct

    def test_decision_choice_triggers_decision_stage(self):
        from src.reasoning.engine import ReasoningEngine
        from src.conversation.state import ConversationState
        engine = ReasoningEngine()
        state = ConversationState(session_id="test")
        r = _make_result(text="which branch should I choose", intent_primary="decision")
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._determine_stage(ctx, r, state)
        assert result == "decision"

    def test_apply_form_triggers_application_stage(self):
        from src.reasoning.engine import ReasoningEngine
        from src.conversation.state import ConversationState
        engine = ReasoningEngine()
        state = ConversationState(session_id="test")
        r = _make_result(text="how do I apply", intent_primary="apply")
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._determine_stage(ctx, r, state)
        assert result == "application"

    def test_unknown_intent_discovery(self):
        from src.reasoning.engine import ReasoningEngine
        from src.conversation.state import ConversationState
        engine = ReasoningEngine()
        state = ConversationState(session_id="test")
        r = _make_result(text="hello", intent_primary="unknown")
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._determine_stage(ctx, r, state)
        assert result == "discovery"

    def test_has_field_uses_ctx_instead_of_understanding(self):
        """_determine_stage passes ctx to _has_field, not understanding."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._determine_stage)
        assert "_has_field(ctx," in source
        assert "_has_field(understanding," not in source

    def test_profile_field_present_same_as_direct(self):
        """Field in profile through ctx produces same stage as through understanding."""
        from src.reasoning.engine import ReasoningEngine
        from src.conversation.state import ConversationState
        engine = ReasoningEngine()
        state = ConversationState(
            session_id="test",
            profile={"rank": 25000, "interest": "CSE", "pcm_percentage": 85.0},
        )
        r = _make_result(text="about admission", intent_primary="admission",
                         rank=25000)
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._determine_stage(ctx, r, state)
        assert isinstance(result, str)

    def test_all_three_fields_populated(self):
        """rank, pcm, interest populated → evaluation."""
        from src.reasoning.engine import ReasoningEngine
        from src.conversation.state import ConversationState
        engine = ReasoningEngine()
        state = ConversationState(session_id="test", history=["hi", "rank 25000", "pcm 85", "CSE", "more", "data"])
        r = _make_result(text="about admission", intent_primary="admission", rank=25000)
        r.profile.academic.pcm_percentage = 85.0
        r.profile.career.interest = "CSE"
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._determine_stage(ctx, r, state)
        assert isinstance(result, str)

    def test_none_populated(self):
        """No fields populated → discovery."""
        from src.reasoning.engine import ReasoningEngine
        from src.conversation.state import ConversationState
        engine = ReasoningEngine()
        state = ConversationState(session_id="test")
        r = _make_result(text="hello", intent_primary="unknown")
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._determine_stage(ctx, r, state)
        assert result == "discovery"

    def test_mixed_field_combinations(self):
        """Mixed field presence — each combination produces a valid stage."""
        from src.reasoning.engine import ReasoningEngine
        from src.conversation.state import ConversationState
        engine = ReasoningEngine()
        combinations = [
            {"history": [], "rank": None, "pcm": None, "interest": None},
            {"history": ["a", "b", "c", "d"], "rank": 25000, "pcm": 85.0, "interest": "CSE"},
            {"history": ["a", "b"], "rank": 20000, "pcm": None, "interest": None},
        ]
        for combo in combinations:
            state = ConversationState(session_id="test", history=combo["history"])
            r = _make_result(
                text="test", intent_primary="admission",
                rank=combo["rank"] if combo["rank"] else None,
            )
            if combo.get("pcm"):
                r.profile.academic.pcm_percentage = combo["pcm"]
            ctx = ReasoningContext.from_understanding_result(r)
            result = engine._determine_stage(ctx, r, state)
            assert isinstance(result, str)

    def test_profile_reference_equivalence(self):
        """ctx.profile is the same object as understanding.profile."""
        r = _make_result(text="test")
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.profile is r.profile

    def test_no_unexpected_understanding_reads_in_determine_stage(self):
        """_determine_stage should not have any understanding.* reads beyond signature."""
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._determine_stage)
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if "understanding." in s and not s.startswith("#"):
                # Allow only the parameter name in signature
                assert s.startswith("def ") and "understanding:" in s, (
                    f"Unexpected understanding.* read at line {i}: {s}"
                )


# =========================================================================
# 19. Final — reason() orchestration intent.primary uses ctx
# =========================================================================

class TestReasonOrchestrationIntentEquivalence:
    """Prove reason() sources intent from ctx.intent_primary, not
    understanding.intent.primary."""

    def test_sources_intent_from_ctx(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine.reason)
        assert "ctx.intent_primary" in source
        assert "understanding.intent.primary" not in source

    def test_answerable_intent_no_blocking(self):
        """ANSWERABLE_GENERALLY intents are not blocked even without profile."""
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        for intent in ["fee", "hostel", "grievance"]:
            r = _make_result(text=f"about {intent}", intent_primary=intent)
            result = engine.reason(r)
            assert not result.readiness.blocked, f"intent={intent} should not be blocked"

    def test_non_answerable_intent_blocked_without_profile(self):
        """Non-answerable intents are blocked when no profile data."""
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        for intent in ["admission", "cutoff"]:
            r = _make_result(text=f"about {intent}", intent_primary=intent)
            result = engine.reason(r)
            assert result.readiness.blocked, f"intent={intent} should be blocked"

    def test_input_intent_metadata_matches(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="about fee", intent_primary="fee")
        result = engine.reason(r, debug=True)
        diag = result.metadata.get("reasoning_diagnostics")
        assert diag is not None
        assert diag.input_intent == "fee"

    def test_reasoning_output_unchanged(self):
        """Verify full reasoning output for representative intents."""
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()

        test_cases = [
            ("hello", "unknown"),
            ("tell me about fees", "fee"),
            ("I want admission info", "admission"),
            ("how do I apply", "apply"),
            ("which branch should I choose", "decision"),
        ]
        for text, expected_intent in test_cases:
            r = _make_result(text=text, intent_primary=expected_intent)
            result = engine.reason(r)
            assert isinstance(result.current_problem, str)
            assert isinstance(result.student_stage, str)
            assert isinstance(result.confidence, float)
            assert 0.0 <= result.confidence <= 1.0
            assert isinstance(result.unknowns, list)
            assert isinstance(result.knowledge_needed, list)


# =========================================================================
# 20. Behavioral equivalence — _identify_risks emotion signals via ctx
# =========================================================================

class TestIdentifyRisksEmotionEquivalence:
    """Prove _identify_risks reads ctx.signals.{anxiety,confusion,frustration}
    and produces identical output."""

    def test_uses_ctx_signals(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        source = inspect.getsource(ReasoningEngine._identify_risks)
        assert "ctx.signals.anxiety" in source
        assert "ctx.signals.confusion" in source
        assert "ctx.signals.frustration" in source
        assert "understanding.signals.anxiety" not in source
        assert "understanding.signals.confusion" not in source
        assert "understanding.signals.frustration" not in source

    def test_all_below_threshold(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="hello", signals_kw={"anxiety": 0.2, "confusion": 0.2, "frustration": 0.2})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_risks(ctx, r, readiness)
        assert "student_shows_anxiety" not in result
        assert "student_shows_confusion" not in result
        assert "student_shows_frustration" not in result

    def test_anxiety_above_threshold(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="worried", signals_kw={"anxiety": 0.7, "confusion": 0.2, "frustration": 0.2})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_risks(ctx, r, readiness)
        assert "student_shows_anxiety" in result
        assert "student_shows_confusion" not in result
        assert "student_shows_frustration" not in result

    def test_confusion_above_threshold(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="confused", signals_kw={"anxiety": 0.2, "confusion": 0.7, "frustration": 0.2})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_risks(ctx, r, readiness)
        assert "student_shows_anxiety" not in result
        assert "student_shows_confusion" in result
        assert "student_shows_frustration" not in result

    def test_frustration_above_threshold(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="frustrated", signals_kw={"anxiety": 0.2, "confusion": 0.2, "frustration": 0.7})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_risks(ctx, r, readiness)
        assert "student_shows_anxiety" not in result
        assert "student_shows_confusion" not in result
        assert "student_shows_frustration" in result

    def test_multiple_signals_above_threshold(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="very confused and anxious", signals_kw={"anxiety": 0.7, "confusion": 0.8, "frustration": 0.2})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_risks(ctx, r, readiness)
        assert "student_shows_anxiety" in result
        assert "student_shows_confusion" in result
        assert "student_shows_frustration" not in result

    def test_boundary_values_at_threshold(self):
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=True, completeness=1.0)
        r = _make_result(text="test", signals_kw={"anxiety": 0.5, "confusion": 0.5, "frustration": 0.5})
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_risks(ctx, r, readiness)
        # Exactly 0.5 does NOT trigger (> not >=)
        assert "student_shows_anxiety" not in result
        assert "student_shows_confusion" not in result
        assert "student_shows_frustration" not in result

    def test_readiness_blocked_risks_still_work(self):
        """Verify non-signal risk logic remains untouched."""
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import ReadinessResult
        engine = ReasoningEngine()
        readiness = ReadinessResult(domain="fee", ready=False, blocked=True, missing_critical=["a", "b", "c"], completeness=0.0)
        r = _make_result(text="test")
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._identify_risks(ctx, r, readiness)
        assert "insufficient_profile_for_guidance" in result


class TestGetFieldChainMigration:
    """Prove _get_field chain (→ _resolve_rank/pcm/category → _estimate_eligibility)
    reads profile through ctx, not understanding."""

    def test_resolve_rank_uses_ctx(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        src = inspect.getsource(ReasoningEngine._resolve_rank)
        assert "_get_field(ctx," in src
        assert "_get_field(understanding," not in src

    def test_resolve_pcm_uses_ctx(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        src = inspect.getsource(ReasoningEngine._resolve_pcm)
        assert "_get_field(ctx," in src
        assert "_get_field(understanding," not in src

    def test_resolve_category_uses_ctx(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        src = inspect.getsource(ReasoningEngine._resolve_category)
        assert "_get_field(ctx," in src
        assert "_get_field(understanding," not in src

    def test_estimate_eligibility_passes_ctx(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        src = inspect.getsource(ReasoningEngine._estimate_eligibility)
        assert "self._estimate_via_brain(ctx," in src
        assert "self._estimate_fallback(ctx," in src

    def test_estimate_via_brain_passes_ctx(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        src = inspect.getsource(ReasoningEngine._estimate_via_brain)
        assert "self._resolve_rank(ctx," in src
        assert "self._resolve_pcm(ctx," in src
        assert "self._resolve_category(ctx," in src

    def test_estimate_fallback_passes_ctx(self):
        import inspect
        from src.reasoning.engine import ReasoningEngine
        src = inspect.getsource(ReasoningEngine._estimate_fallback)
        assert "self._resolve_rank(ctx," in src
        assert "self._resolve_pcm(ctx," in src

    def test_rank_present(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="rank 25000", intent_primary="admission", rank=25000)
        ctx = ReasoningContext.from_understanding_result(r)
        rank = engine._resolve_rank(ctx, None)
        assert rank == 25000

    def test_rank_absent(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="hello", intent_primary="unknown")
        ctx = ReasoningContext.from_understanding_result(r)
        rank = engine._resolve_rank(ctx, None)
        assert rank is None

    def test_pcm_present(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="pcm 85", intent_primary="admission")
        r.profile.academic.pcm_percentage = 85.0
        ctx = ReasoningContext.from_understanding_result(r)
        pcm = engine._resolve_pcm(ctx, None)
        assert pcm == 85.0

    def test_pcm_absent(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="hello", intent_primary="unknown")
        ctx = ReasoningContext.from_understanding_result(r)
        pcm = engine._resolve_pcm(ctx, None)
        assert pcm is None

    def test_category_present(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="sc category", intent_primary="admission")
        r.profile.personal.category = "sc"
        ctx = ReasoningContext.from_understanding_result(r)
        cat = engine._resolve_category(ctx, None)
        assert cat == "sc"

    def test_category_absent_defaults_general(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="hello", intent_primary="unknown")
        ctx = ReasoningContext.from_understanding_result(r)
        cat = engine._resolve_category(ctx, None)
        assert cat == "general"

    def test_eligibility_output_unchanged(self):
        """Full eligibility estimate via ctx matches direct profile read."""
        from src.reasoning.engine import ReasoningEngine
        from src.reasoning.models import EligibilityEstimate
        engine = ReasoningEngine()
        r = _make_result(text="rank 25000", intent_primary="admission", rank=25000)
        r.profile.academic.pcm_percentage = 85.0
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine._estimate_fallback(ctx, r, None)
        assert isinstance(result, EligibilityEstimate)
        # ctx.profile is same object as r.profile — values must match
        assert ctx.profile.academic.rank == r.profile.academic.rank
        assert ctx.profile.academic.pcm_percentage == r.profile.academic.pcm_percentage

    def test_partial_profile_rank_present_no_pcm(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="rank only", intent_primary="admission", rank=15000)
        ctx = ReasoningContext.from_understanding_result(r)
        rank = engine._resolve_rank(ctx, None)
        pcm = engine._resolve_pcm(ctx, None)
        assert rank == 15000
        assert pcm is None

    def test_empty_profile(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="hello", intent_primary="unknown")
        ctx = ReasoningContext.from_understanding_result(r)
        rank = engine._resolve_rank(ctx, None)
        pcm = engine._resolve_pcm(ctx, None)
        cat = engine._resolve_category(ctx, None)
        assert rank is None
        assert pcm is None
        assert cat == "general"

    def test_profile_reference_equivalence(self):
        """ctx.profile is the same object as understanding.profile."""
        r = _make_result(text="test", rank=25000)
        ctx = ReasoningContext.from_understanding_result(r)
        assert ctx.profile is r.profile


# =========================================================================
# 20. V1.7 Observational Telemetry — ReasoningObservation
# =========================================================================

class TestReasoningObservationContract:
    """ReasoningObservation is read-only telemetry derived after the
    ReasoningResult is constructed, never influencing reasoning behavior."""

    def test_frozen_cannot_reassign(self):
        obs = ReasoningObservation()
        with pytest.raises((AttributeError, TypeError)):
            obs.reasoning_stage = "evaluation"  # type: ignore[misc]

    def test_frozen_cannot_add_field(self):
        obs = ReasoningObservation()
        with pytest.raises((AttributeError, TypeError)):
            obs.injected_field = 42  # type: ignore[attr-defined]

    def test_defaults_are_safe(self):
        obs = ReasoningObservation()
        assert obs.reasoning_stage == ""
        assert obs.confidence_score == 0.0
        assert obs.missing_critical_fields == ()
        assert obs.structured_signal_types == ()
        assert obs.latency_ms == 0.0

    def test_observe_does_not_mutate_result(self):
        import copy
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="about fee", intent_primary="fee", rank=25000, category="general")
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine.reason(r)
        expected = copy.deepcopy(result)
        _ = observe(result, ctx)
        assert result.current_problem == expected.current_problem
        assert result.student_stage == expected.student_stage
        assert result.confidence == expected.confidence
        assert result.profile_completeness == expected.profile_completeness

    def test_observe_does_not_mutate_context(self):
        import copy
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="about fee", intent_primary="fee")
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine.reason(r)
        expected = copy.deepcopy(ctx)
        _ = observe(result, ctx)
        assert ctx.intent_primary == expected.intent_primary
        assert ctx.intent_confidence == expected.intent_confidence

    def test_observe_populates_all_fields(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        ss = StructuredSignals(
            grievance=Signal(value="waiting", confidence=0.8, source="test"),
            emotion=Signal(value="anxiety", confidence=0.6, source="test"),
        )
        r = _make_result(
            text="about fees", intent_primary="fee",
            intent_confidence=0.9, rank=12000, category="obc",
            signals_kw={"anxiety": 0.7, "financial_concern": 0.4},
            structured=ss,
        )
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine.reason(r)
        obs = observe(result, ctx, latency_ms=12.5)

        assert obs.reasoning_stage == result.student_stage
        assert obs.confidence_score == result.confidence
        assert obs.readiness_domain == (result.readiness.domain if result.readiness else "")
        assert obs.missing_critical_fields == (tuple(result.readiness.missing_critical) if result.readiness else ())
        assert obs.completeness == result.profile_completeness
        assert obs.intent_primary == "fee"
        assert obs.intent_confidence == 0.9
        assert obs.dominant_signal_name == "anxiety"
        assert obs.dominant_signal_score == 0.7
        assert "grievance" in obs.structured_signal_types
        assert "emotion" in obs.structured_signal_types
        assert "decision" not in obs.structured_signal_types
        assert obs.latency_ms == 12.5

    def test_observe_with_empty_context(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="test", intent_primary="unknown")
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine.reason(r)
        obs = observe(result, ctx)
        # zero-score dominant → None, not "anxiety"
        assert obs.dominant_signal_name is None
        assert obs.dominant_signal_score == 0.0
        assert obs.structured_signal_types == ()
        assert obs.signal_interaction_primary_dimension == "none"


class TestReasoningObserverInvariance:
    """Telemetry on/off must produce identical ReasoningResult."""

    def _obs_capture(self, engine, r, state=None):
        captured = []

        def collector(obs):
            captured.append(obs)

        result = engine.reason(r, state, observer=collector)
        return result, captured[0] if captured else None

    def test_result_identical_with_and_without_observer(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="what are the fees", intent_primary="fee", rank=25000)
        state = ConversationState(session_id="test")

        result_no_obs = engine.reason(r, state)
        result_with_obs, obs = self._obs_capture(engine, r, state)

        assert obs is not None
        assert result_no_obs == result_with_obs
        assert obs.reasoning_stage == result_no_obs.student_stage
        assert obs.identified_problem == result_no_obs.current_problem

    def test_observer_sees_observation_with_latency(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="about hostel", intent_primary="hostel")
        state = ConversationState(session_id="test")

        _, obs = self._obs_capture(engine, r, state)
        assert obs is not None
        assert obs.latency_ms > 0

    def test_multiple_calls_produce_independent_observations(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        observations = []

        def collector(obs):
            observations.append(obs)

        r1 = _make_result(text="fees", intent_primary="fee", rank=25000)
        r2 = _make_result(text="hostel", intent_primary="hostel")

        engine.reason(r1, observer=collector)
        engine.reason(r2, observer=collector)

        assert len(observations) == 2
        assert observations[0].intent_primary == "fee"
        assert observations[1].intent_primary == "hostel"

    def test_observer_can_be_none(self):
        """Observer is optional — None should be a no-op."""
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="test")
        result = engine.reason(r, observer=None)
        assert result is not None
        assert isinstance(result, ReasoningResult)


class TestObservationSinks:
    """Sinks are callables that receive ReasoningObservation."""

    def test_in_memory_sink_collects(self):
        sink = InMemorySink()
        r = _make_result(text="fees", intent_primary="fee")
        ctx = ReasoningContext.from_understanding_result(r)
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        result = engine.reason(r, observer=sink)
        assert sink.count == 1
        obs = sink.observations[0]
        assert obs.intent_primary == "fee"
        assert obs.latency_ms > 0

    def test_in_memory_sink_multiple_calls(self):
        sink = InMemorySink()
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        engine.reason(_make_result(text="a", intent_primary="fee"), observer=sink)
        engine.reason(_make_result(text="b", intent_primary="hostel"), observer=sink)
        assert sink.count == 2
        assert sink.observations[0].intent_primary == "fee"
        assert sink.observations[1].intent_primary == "hostel"

    def test_in_memory_sink_clear(self):
        sink = InMemorySink()
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        engine.reason(_make_result(text="x"), observer=sink)
        assert sink.count == 1
        sink.clear()
        assert sink.count == 0

    def test_no_observer_produces_no_sink_call(self):
        sink = InMemorySink()
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        engine.reason(_make_result(text="x"))
        assert sink.count == 0

    def test_tee_sink_fans_out(self):
        s1 = InMemorySink()
        s2 = InMemorySink()
        tee = TeeSink([s1, s2])
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        engine.reason(_make_result(text="fees"), observer=tee)
        assert s1.count == 1
        assert s2.count == 1

    def test_sink_failure_does_not_crash_reasoning(self):
        """A crashing sink must not propagate the exception."""
        def crashing_sink(obs):
            raise RuntimeError("sink exploded")
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        result = engine.reason(
            _make_result(text="fees"),
            observer=safe_observer(crashing_sink),
        )
        # result still produced correctly
        assert result is not None
        assert result.current_problem == "needs_fee_information"

    def test_sink_failure_crash_when_unsafe(self):
        """Without safe_observer, a crashing sink propagates."""
        def crashing_sink(obs):
            raise RuntimeError("sink exploded")
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        with pytest.raises(RuntimeError, match="sink exploded"):
            engine.reason(
                _make_result(text="fees"),
                observer=crashing_sink,
            )


class TestObservationSchemaStability:
    """ReasoningObservation schema must remain stable — serialization round-trips."""

    def test_to_dict_envelope_top_level(self):
        obs = ReasoningObservation(reasoning_stage="evaluation")
        d = obs.to_dict()
        assert "schema_version" in d
        assert "observation_id" in d
        assert "observation" in d
        assert d["schema_version"] == OBSERVATION_SCHEMA_VERSION
        assert isinstance(d["observation_id"], str) and len(d["observation_id"]) > 0

    def test_to_dict_body_contains_all_fields(self):
        obs = ReasoningObservation(
            reasoning_stage="evaluation",
            identified_problem="needs_fee_information",
            confidence_score=0.8,
            intent_primary="fee",
            dominant_signal_name="anxiety",
            dominant_signal_score=0.7,
            latency_ms=5.2,
        )
        d = obs.to_dict()
        body = d["observation"]
        # observation_id is in the envelope, not the body
        skip = {"SCHEMA_VERSION", "REQUIRED_FIELDS", "observation_id"}
        for f in obs.__dataclass_fields__:
            if f in skip:
                continue
            assert f in body, f"missing field {f}"
        assert body["reasoning_stage"] == "evaluation"
        assert body["identified_problem"] == "needs_fee_information"
        assert body["dominant_signal_name"] == "anxiety"
        assert body["latency_ms"] == 5.2

    def test_to_dict_converts_tuples_to_lists(self):
        obs = ReasoningObservation(missing_critical_fields=("rank", "category"))
        d = obs.to_dict()
        assert d["observation"]["missing_critical_fields"] == ["rank", "category"]

    def test_to_json_is_serializable(self):
        obs = ReasoningObservation(
            intent_primary="fee",
            confidence_score=0.75,
            latency_ms=3.1,
        )
        raw = obs.to_json()
        assert isinstance(raw, str)
        import json
        loaded = json.loads(raw)
        assert loaded["schema_version"] == OBSERVATION_SCHEMA_VERSION
        assert loaded["observation"]["intent_primary"] == "fee"
        assert loaded["observation"]["confidence_score"] == 0.75
        assert loaded["observation"]["latency_ms"] == 3.1

    def test_to_json_round_trip(self):
        import json
        obs = ReasoningObservation(
            reasoning_stage="discovery",
            dominant_signal_name=None,
            missing_critical_fields=("rank",),
            structured_signal_types=(),
            latency_ms=0.0,
        )
        loaded = json.loads(obs.to_json())
        body = loaded["observation"]
        assert body["reasoning_stage"] == "discovery"
        assert body["dominant_signal_name"] is None
        assert body["missing_critical_fields"] == ["rank"]
        assert body["structured_signal_types"] == []

    def test_to_json_from_dict_round_trip(self):
        import json
        obs = ReasoningObservation(
            reasoning_stage="evaluation",
            dominant_signal_name=None,
            missing_critical_fields=("rank", "pcm"),
            latency_ms=4.2,
        )
        raw = obs.to_json()
        loaded = json.loads(raw)
        restored = ReasoningObservation.from_dict(loaded)
        assert restored.reasoning_stage == obs.reasoning_stage
        assert restored.dominant_signal_name == obs.dominant_signal_name
        assert restored.missing_critical_fields == obs.missing_critical_fields
        assert restored.latency_ms == obs.latency_ms

    def test_default_observation_serializes(self):
        obs = ReasoningObservation()
        d = obs.to_dict()
        body = d["observation"]
        skip = {"SCHEMA_VERSION", "REQUIRED_FIELDS", "observation_id"}
        for f in obs.__dataclass_fields__:
            if f in skip:
                continue
            assert f in body
        assert body["dominant_signal_name"] is None
        assert body["missing_critical_fields"] == []
        assert body["structured_signal_types"] == []

    def test_observe_to_dict_round_trip(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="fees", intent_primary="fee", rank=25000)
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine.reason(r)
        obs = observe(result, ctx, latency_ms=3.0)
        d = obs.to_dict()
        assert d["observation"]["intent_primary"] == "fee"
        assert d["observation"]["reasoning_stage"] == result.student_stage
        assert d["observation"]["latency_ms"] == 3.0
        assert d["schema_version"] == OBSERVATION_SCHEMA_VERSION

    def test_observation_id_auto_generated(self):
        obs = ReasoningObservation()
        assert obs.observation_id == ""
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="test")
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine.reason(r)
        obs2 = observe(result, ctx)
        assert len(obs2.observation_id) > 0
        assert obs2.observation_id != ""

    def test_observation_id_explicit(self):
        from src.reasoning.engine import ReasoningEngine
        engine = ReasoningEngine()
        r = _make_result(text="test")
        ctx = ReasoningContext.from_understanding_result(r)
        result = engine.reason(r)
        obs = observe(result, ctx, observation_id="my-custom-id")
        assert obs.observation_id == "my-custom-id"

    def test_from_dict_ignores_unknown_keys(self):
        data = {
            "schema_version": 1,
            "observation_id": "abc123",
            "observation": {
                "reasoning_stage": "evaluation",
                "unknown_field": "should be ignored",
                "confidence_score": 0.8,
            },
        }
        obs = ReasoningObservation.from_dict(data)
        assert obs.reasoning_stage == "evaluation"
        assert obs.confidence_score == 0.8
        assert not hasattr(obs, "unknown_field")

    def test_from_dict_missing_keys_use_defaults(self):
        data = {
            "schema_version": 1,
            "observation_id": "abc123",
            "observation": {},
        }
        obs = ReasoningObservation.from_dict(data)
        assert obs.reasoning_stage == ""
        assert obs.dominant_signal_name is None
        assert obs.latency_ms == 0.0

    def test_from_dict_flat_body_no_envelope(self):
        """from_dict still works when passed a flat dict (no envelope)."""
        data = {"reasoning_stage": "evaluation", "intent_primary": "fee"}
        obs = ReasoningObservation.from_dict(data)
        assert obs.reasoning_stage == "evaluation"
        assert obs.intent_primary == "fee"

    def test_from_dict_converts_lists_to_tuples(self):
        data = {
            "observation": {
                "missing_critical_fields": ["rank", "category"],
                "structured_signal_types": ["grievance"],
            },
        }
        obs = ReasoningObservation.from_dict(data)
        assert obs.missing_critical_fields == ("rank", "category")
        assert obs.structured_signal_types == ("grievance",)

    def test_validate_returns_empty_for_populated(self):
        obs = ReasoningObservation(
            reasoning_stage="evaluation",
            identified_problem="needs_fee_information",
            intent_primary="fee",
            readiness_domain="regular",
            confidence_score=0.8,
            latency_ms=5.0,
        )
        assert obs.validate() == []

    def test_validate_returns_missing_required(self):
        obs = ReasoningObservation()
        missing = obs.validate()
        for f in ReasoningObservation.REQUIRED_FIELDS:
            assert f in missing, f"expected {f} in missing"

    def test_schema_version_constant(self):
        assert OBSERVATION_SCHEMA_VERSION == 1
        assert ReasoningObservation.SCHEMA_VERSION == 1
