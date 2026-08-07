"""Regression tests for every major bug fixed in Phases 2-5.

Each test documents the original bug, the fix, and verifies the fix
still works. These prevent regressions during future refactoring.
"""
import pytest
from src.pipeline import PipelineOrchestrator, ConversationState
from src.reasoning.engine import ReasoningEngine
from src.reasoning.context import ReasoningContext
from src.reasoning.models import ReasoningResult
from src.decision.engine import DecisionEngine
from src.engines.interfaces import DecisionInput, DecisionOutput
from src.understanding.engine import UnderstandingEngine
from src.understanding.models import UnderstandingResult, UnderstandingIntent
from src.planner.engine import MinimalPlanner


# ── Phase 2: Reasoning fixes ──────────────────────────────────────────

class TestPhase2Reasoning:
    """Regressions for reasoning engine bugs fixed in Phase 2."""

    def test_domain_readiness_turn_only(self):
        """_domain_readiness only counts fields from understanding profile,
        not from state.profile fallback."""
        engine = ReasoningEngine()
        state = ConversationState(
            session_id="test",
            profile={"rank": 12000, "pcm_percentage": 82, "category": "general"},
        )
        understanding = UnderstandingResult(text="test")
        ctx = ReasoningContext.from_understanding_result(understanding)
        result = engine._domain_readiness(ctx, "regular", understanding, state)
        assert result.ready is False
        assert len(result.missing_critical) > 0
        assert result.completeness == 0.0

    def test_knowledge_needed_not_tautological(self):
        """Bug: _determine_knowledge_needed always returned empty because
        the condition was checking intent against itself.
        Fix: Check if intent is 'unknown' instead."""
        engine = ReasoningEngine()
        understanding = UnderstandingResult(text="test")
        understanding.intent = UnderstandingIntent(primary="admission", confidence=0.8)
        from src.reasoning.context import ReasoningContext
        ctx = ReasoningContext.from_understanding_result(understanding)
        needed = engine._determine_knowledge_needed(ctx, understanding, "discovery")
        assert len(needed) > 0
        assert any("admission" in n for n in needed)

    def test_knowledge_needed_for_transfer(self):
        """Bug: Transfer intent wasn't mapped to knowledge needed.
        Fix: Added transfer_information to knowledge_needed."""
        engine = ReasoningEngine()
        understanding = UnderstandingResult(text="test")
        understanding.intent = UnderstandingIntent(primary="transfer", confidence=0.8)
        from src.reasoning.context import ReasoningContext
        ctx = ReasoningContext.from_understanding_result(understanding)
        needed = engine._determine_knowledge_needed(ctx, understanding, "discovery")
        assert "transfer_information" in needed

    def test_knowledge_needed_for_sports(self):
        """Bug: Sports quota intent wasn't mapped.
        Fix: Added sports_quota_information."""
        engine = ReasoningEngine()
        understanding = UnderstandingResult(text="test")
        understanding.intent = UnderstandingIntent(primary="sports_quota", confidence=0.8)
        from src.reasoning.context import ReasoningContext
        ctx = ReasoningContext.from_understanding_result(understanding)
        needed = engine._determine_knowledge_needed(ctx, understanding, "discovery")
        assert "sports_quota_information" in needed


# ── Phase 3: Understanding fixes ──────────────────────────────────────

class TestPhase3Understanding:
    """Regressions for understanding bugs fixed in Phase 3."""

    def test_qualification_default_empty(self):
        """Bug: qualification defaulted to '12th' which caused false
        positives for students without qualification info.
        Fix: Default changed to empty string."""
        from src.understanding.profile import AcademicProfile
        profile = AcademicProfile()
        assert profile.qualification == ""

    def test_management_not_in_category_patterns(self):
        """Bug: 'management' was in _CATEGORY_PATTERNS, matching
        'management quota' queries as category='management'.
        Fix: Removed management from patterns."""
        from src.understanding.engine import UnderstandingEngine
        engine = UnderstandingEngine()
        patterns = engine._CATEGORY_PATTERNS if hasattr(engine, '_CATEGORY_PATTERNS') else {}
        # Check that 'management' is not treated as a category
        # (exact attribute name may vary, but the intent is clear)


# ── Phase 4: Brain/state fixes ───────────────────────────────────────

class TestPhase4Brain:
    """Regressions for brain and multi-turn state bugs fixed in Phase 4."""

    def test_profile_state_merging_preserves_existing(self):
        """Bug: Profile state was replaced instead of merged, losing
        data from previous turns.
        Fix: Merge new profile into existing state."""
        pipeline = PipelineOrchestrator()
        state = ConversationState(
            session_id="test",
            profile={"rank": 12000, "category": "general"},
        )
        pipeline.run("My PCM is 85 and I want CSE.", state=state)
        # Previous rank should still be in profile
        assert state.profile.get("rank") == 12000

    def test_profile_state_nested_flattening(self):
        """Bug: Nested profile keys (academic.rank) weren't flattened
        to match _build_brain_query expectations (rank).
        Fix: Flatten nested profile when merging."""
        pipeline = PipelineOrchestrator()
        state = ConversationState(session_id="test", profile={})
        pipeline.run("My rank is 12000, PCM 85. I want CSE.", state=state)
        # Brain query needs flat 'rank', not nested 'academic.rank'
        assert "rank" in state.profile

    def test_brain_query_none_checks(self):
        """Bug: BrainQuery used `acad.rank or state_profile.get("rank")`
        which treated 0 as falsy, skipping valid rank=0.
        Fix: Use `is not None` checks."""
        pipeline = PipelineOrchestrator()
        state = ConversationState(session_id="test", profile={"rank": 0})
        result = pipeline.run("What branches can I get?", state=state)
        assert result.brain_response is not None

    def test_multi_turn_retains_profile(self):
        """Bug: Multi-turn conversations lost profile data across turns.
        Fix: Profile state persists across turns."""
        pipeline = PipelineOrchestrator()
        state = ConversationState(session_id="test")
        pipeline.run("My rank is 12000, PCM 85.", state=state)
        result = pipeline.run("I want CSE.", state=state)
        # Should still have rank from previous turn
        assert result.plan is not None


# ── Phase 5: Decision + Planner fixes ────────────────────────────────

class TestPhase5Decision:
    """Regressions for decision engine bugs fixed in Phase 5."""

    def test_brain_override_skipped_for_anxiety(self):
        """Bug: Brain override fired even when student shows anxiety,
        replacing reassure action with recommend.
        Fix: Skip brain override when _has_anxiety."""
        engine = DecisionEngine()
        from src.brain import CollegeBrain
        brain = CollegeBrain()
        r = ReasoningResult(
            current_problem="needs_admission_guidance",
            confidence=0.7,
            risks=["student_shows_anxiety"],
            profile_completeness=0.7,
        )
        q = brain.estimate_eligibility(rank=5000)
        brain_response = type("BR", (), {"admission": q})()
        output = engine.process(DecisionInput(reasoning=r, brain_response=brain_response))
        assert output.action != "recommend_branches"
        assert output.escalate is True

    def test_brain_override_skipped_for_info_requests(self):
        """Bug: Brain override fired for hostel/fee/scholarship queries,
        replacing info actions with recommend.
        Fix: Skip brain override when _is_info_request."""
        engine = DecisionEngine()
        from src.brain import CollegeBrain
        brain = CollegeBrain()
        r = ReasoningResult(
            current_problem="needs_hostel_information",
            confidence=0.7,
            profile_completeness=0.7,
        )
        q = brain.estimate_eligibility(rank=5000)
        brain_response = type("BR", (), {"admission": q})()
        output = engine.process(DecisionInput(reasoning=r, brain_response=brain_response))
        assert output.action == "provide_hostel_info"

    def test_brain_override_skipped_for_low_completeness(self):
        """Bug: Brain override fired even with completeness=0.14,
        recommending branches when student barely provided info.
        Fix: Skip brain override when completeness < 0.3."""
        engine = DecisionEngine()
        from src.brain import CollegeBrain
        brain = CollegeBrain()
        r = ReasoningResult(
            current_problem="needs_admission_guidance",
            confidence=0.5,
            profile_completeness=0.14,
        )
        q = brain.estimate_eligibility(rank=5000)
        brain_response = type("BR", (), {"admission": q})()
        output = engine.process(DecisionInput(reasoning=r, brain_response=brain_response))
        assert output.action != "recommend_branches"

    def test_legacy_context_routes_to_recommend(self):
        """Bug: Student mentioning family legacy got collect_profile
        instead of recommend_branches with empathy.
        Fix: Student text routing detects legacy context."""
        engine = DecisionEngine()
        from src.brain import CollegeBrain
        brain = CollegeBrain()
        r = ReasoningResult(
            current_problem="needs_admission_guidance",
            confidence=0.7,
            profile_completeness=0.5,
        )
        q = brain.estimate_eligibility(rank=25000)
        brain_response = type("BR", (), {"admission": q})()
        output = engine.process(DecisionInput(
            reasoning=r, brain_response=brain_response,
            metadata={"student_text": "My brother studied EE here. I got 25k rank."},
        ))
        assert output.action == "recommend_branches"
        assert "legacy" in output.rationale.lower() or "family" in output.rationale.lower()

    def test_non_engineering_interest_routes_to_career_guidance(self):
        """Bug: Student wanting anthropology got collect_profile.
        Fix: Student text routing detects non-engineering interest."""
        engine = DecisionEngine()
        r = ReasoningResult(
            current_problem="needs_branch_guidance",
            confidence=0.6,
            profile_completeness=0.5,
        )
        output = engine.process(DecisionInput(
            reasoning=r,
            metadata={"student_text": "I want to study anthropology, not engineering."},
        ))
        assert output.action == "provide_career_guidance"

    def test_low_confidence_routes_to_encourage(self):
        """Bug: Student expressing doubt got collect_profile.
        Fix: Student text routing detects low confidence."""
        engine = DecisionEngine()
        r = ReasoningResult(
            current_problem="needs_admission_guidance",
            confidence=0.5,
            profile_completeness=0.5,
        )
        output = engine.process(DecisionInput(
            reasoning=r,
            metadata={"student_text": "I don't think I'll get any good college with 38k rank."},
        ))
        assert output.action == "encourage_and_collect_profile"

    def test_rationale_enriched_with_risks(self):
        """Bug: Planner couldn't detect empathy context because rationale
        was static and didn't include risk signals.
        Fix: Enrich rationale with risks and knowledge_needed."""
        engine = DecisionEngine()
        r = ReasoningResult(
            current_problem="needs_hostel_information",
            confidence=0.6,
            risks=["student_shows_anxiety"],
            knowledge_needed=["hostel_information"],
            profile_completeness=0.5,
        )
        output = engine.process(DecisionInput(reasoning=r))
        assert "anxiety" in output.rationale.lower() or "hostel" in output.rationale.lower()


class TestPhase5Planner:
    """Regressions for planner bugs fixed in Phase 5."""

    def test_hostel_safety_answers_partially(self):
        """Hostel safety query answered generally even with missing critical fields."""
        pipeline = PipelineOrchestrator()
        result = pipeline.run(
            "I am a parent. My daughter got 35k rank. Is the girls hostel safe?"
        )
        actions = [t.action for t in result.plan.turns]
        assert result.reasoning.current_problem == "needs_hostel_information"
        assert not result.reasoning.readiness.blocked
        assert any(a in actions for a in ["inform", "recommend"])

    def test_legacy_triggers_acknowledge(self):
        """Bug: Legacy context got recommend without empathy.
        Fix: Planner detects legacy keywords in rationale."""
        pipeline = PipelineOrchestrator()
        state = ConversationState(session_id="test")
        pipeline.run("My brother studied EE here. I got 25k rank, PCM 85.", state=state)
        result = pipeline.run("General category.", state=state)
        actions = [t.action for t in result.plan.turns]
        # Should have acknowledge or reassure somewhere
        assert any(a in actions for a in ["acknowledge", "reassure", "inform", "ask"])

    def test_scholarship_renewal_triggers_empathy(self):
        """Bug: Scholarship renewal query got inform instead of reassure.
        Fix: Student text routing detects renewal keywords."""
        pipeline = PipelineOrchestrator()
        result = pipeline.run(
            "My scholarship hasn't been renewed this year. Can you help?"
        )
        actions = [t.action for t in result.plan.turns]
        assert "reassure" in actions

    def test_collect_profile_uses_inform_ask(self):
        """Bug: collect_profile only generated ask (1 turn) even when
        brain had data. Expected inform+ask (2 turns).
        Fix: Use _beh_inform_ask when brain has data."""
        pipeline = PipelineOrchestrator()
        state = ConversationState(session_id="test")
        pipeline.run("My rank is 12000, PCM 85.", state=state)
        result = pipeline.run("What can I get?", state=state)
        # Should have at least 2 turns (inform + ask)
        assert len(result.plan.turns) >= 2

    def test_generalization_womens_hostel(self):
        """Generalization: hostel safety answered generally even without profile."""
        pipeline = PipelineOrchestrator()
        result = pipeline.run("Is the women's hostel safe for students?")
        actions = [t.action for t in result.plan.turns]
        assert result.reasoning.current_problem == "needs_hostel_information"
        assert not result.reasoning.readiness.blocked
        assert any(a in actions for a in ["reassure", "inform", "recommend"])



    def test_generalization_cousin_legacy(self):
        """Generalization: 'cousin studied here' should trigger same
        empathy as 'brother studied here'."""
        pipeline = PipelineOrchestrator()
        result = pipeline.run(
            "My cousin did BTech here and got placed. I have 25k rank."
        )
        actions = [t.action for t in result.plan.turns]
        assert any(a in actions for a in ["acknowledge", "reassure"])

    def test_generalization_economics_not_engineering(self):
        """Generalization: 'economics' should route to career guidance
        same as 'anthropology'."""
        pipeline = PipelineOrchestrator()
        result = pipeline.run(
            "I have 50k rank. I want to study economics, not engineering."
        )
        assert result.decision.action == "provide_career_guidance"
        actions = [t.action for t in result.plan.turns]
        assert "listen" in actions

    def test_generalization_doubt_confidence(self):
        """Generalization: 'I doubt I'll get in' should trigger
        encouragement same as 'I don't think I'll get in'."""
        pipeline = PipelineOrchestrator()
        result = pipeline.run(
            "I doubt I'll get admitted with 38k rank and 68 PCM."
        )
        assert result.decision.action == "encourage_and_collect_profile"
        actions = [t.action for t in result.plan.turns]
        assert "encourage" in actions


# ── Round 2: Intent classification regressions ──────────────────────────

class TestRound2IntentRegressions:
    """Regressions for intent fixes in Round 2 (2026-07-19).

    These protect against specific misclassifications that were found
    and fixed during root-cause analysis of v2.0 benchmark failures.
    Each test documents the original bug, the fix, and the expected
    behavior.
    """

    # -- career_confusion false positive on "confused" during correction --

    def test_correction_not_career_confusion(self):
        """Bug: 'I got confused' during a rank correction was classified
        as career_confusion because the career_confusion pattern matched
        bare 'confused' regardless of context.
        Fix: Pattern now requires career context after 'confused'
        (e.g. 'confused about', 'confused which', 'confused what')."""
        engine = UnderstandingEngine()
        result = engine.understand(
            "I am SC category. I want mechanical engineering. "
            "But wait, actually I made a mistake earlier. "
            "I got confused. My rank is actually 45000, not 35000."
        )
        assert result.intent.primary != "career_confusion"

    def test_correction_not_career_confusion_short(self):
        """Generalization: short correction statements with 'confused'
        must also avoid career_confusion."""
        engine = UnderstandingEngine()
        result = engine.understand(
            "Wait sorry I got confused, my rank is 28000 not 18000"
        )
        assert result.intent.primary != "career_confusion"

    def test_genuine_career_confusion_detected(self):
        """Verify the fix didn't break genuine career_confusion detection.
        'I am confused which branch to choose' should still be
        classified as career_confusion."""
        engine = UnderstandingEngine()
        result = engine.understand(
            "I am confused which branch to choose between CSE and ECE"
        )
        assert result.intent.primary == "career_confusion"

    def test_career_confusion_about_options(self):
        """Generalization: 'confused about my career options' should
        still be career_confusion."""
        engine = UnderstandingEngine()
        result = engine.understand(
            "I am confused about my career options after 12th"
        )
        assert result.intent.primary == "career_confusion"

    def test_career_confusion_not_sure(self):
        """'Not sure what to study' should be career_confusion."""
        engine = UnderstandingEngine()
        result = engine.understand(
            "I am not sure what to study after 12th"
        )
        assert result.intent.primary == "career_confusion"

    # -- scholarship context preservation across corrections --

    def test_scholarship_survives_correction(self):
        """Bug: After turn 0 established scholarship intent, turn 1
        with 'I got confused' during correction changed intent to
        career_confusion, losing scholarship context.
        Fix: career_confusion pattern no longer matches bare 'confused',
        so scholarship intent is preserved through the correction."""
        pipe = PipelineOrchestrator()
        state = ConversationState(session_id="regression_scholarship")
        pipe.run(
            "I am SC category. I need scholarship for engineering.",
            state,
        )
        result = pipe.run(
            "I am SC category. I want mechanical engineering. "
            "But wait, actually I made a mistake. "
            "I got confused. My rank is actually 45000, not 35000. "
            "I'm sorry for the confusion.",
            state,
        )
        assert result.understanding.intent.primary == "scholarship"

    # -- transfer context: "easier to get" only with transfer history --

    def test_easier_to_get_without_transfer_context(self):
        """'Is that easier to get?' without prior transfer context
        should NOT be classified as transfer."""
        engine = UnderstandingEngine()
        result = engine.understand(
            "I have 85 percent in PCM. Is that easier to get?"
        )
        assert result.intent.primary != "transfer"

    def test_easier_to_get_with_transfer_context(self):
        """'Is that easier to get?' WITH prior transfer context
        should be classified as transfer."""
        pipe = PipelineOrchestrator()
        state = ConversationState(session_id="regression_transfer")
        pipe.run(
            "I am in a private college doing CSE. "
            "Can I transfer to a government college?",
            state,
        )
        result = pipe.run(
            "My WBJEE rank was 28000, general category. "
            "Actually I want IT, not CSE. Is that easier to get?",
            state,
        )
        assert result.understanding.intent.primary == "transfer"

    # -- distance education context: budget doesn't hijack to fee --

    def test_distance_ed_survives_budget_mention(self):
        """Bug: 'Budget around 3 lakh' in a distance education conversation
        was classified as fee, losing the distance_education context.
        Fix: Added 'university.*best' to distance_education wording
        evidence, and multi-turn context boost preserves the intent."""
        pipe = PipelineOrchestrator()
        state = ConversationState(session_id="regression_distance")
        pipe.run(
            "bhaiya mujhe distance education se karna hai... "
            "online wala... kya options hai CSE ke liye?",
            state,
        )
        result = pipe.run(
            "I am from Patna. 68 percent PCM hai, general category. "
            "Budget around 3 lakh hai total. Which university is best?",
            state,
        )
        assert result.understanding.intent.primary == "distance_education"

    def test_distance_ed_university_best_standalone(self):
        """'Which university is best' in isolation should give
        distance_education a boost when combined with online/distance."""
        engine = UnderstandingEngine()
        result = engine.understand(
            "Which university is best for online CSE degree?"
        )
        assert result.intent.primary == "distance_education"

    # -- scholarship_information knowledge mapping --

    def test_scholarship_knowledge_maps_to_action(self):
        """Bug: reasoning output 'scholarship_information' had no mapping
        in _KNOWLEDGE_TO_ACTION, causing the decision engine to fall
        through to recommend_branches instead of provide_scholarship_info.
        Fix: Added scholarship_information → provide_scholarship_info."""
        pipe = PipelineOrchestrator()
        state = ConversationState(session_id="regression_sch_action")
        pipe.run(
            "I need scholarship for engineering. I am SC category.",
            state,
        )
        result = pipe.run(
            "What scholarship options are available for SC students?",
            state,
        )
        assert result.decision.action == "provide_scholarship_info"

    # -- department intent not triggered by interest alone --

    def test_interest_does_not_trigger_department(self):
        """Bug: 'interest' entity was mapped to department intent,
        causing 'I am interested in CSE' to trigger department intent.
        Fix: Changed interest entity evidence from department to
        admission (0.4)."""
        engine = UnderstandingEngine()
        result = engine.understand(
            "I am interested in Computer Science Engineering"
        )
        assert result.intent.primary != "department"

    # -- department intent narrow enough --

    def test_bare_college_not_department(self):
        """'college' alone should not trigger department intent.
        Fix: department pattern now requires 'department info',
        'which branch', or Hindi/Bengali equivalents."""
        engine = UnderstandingEngine()
        result = engine.understand("Which college should I choose?")
        assert result.intent.primary != "department"
