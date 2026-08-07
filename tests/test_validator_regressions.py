"""Validator regression tests.

Tests that known-bad/known-good pipeline outputs produce the
expected validation status (FAIL/PASS/WARNING) with the correct
check names. This mirrors the mutation testing approach used in
test_evaluator_mutation.py but at the validator level.
"""

from __future__ import annotations

from src.decision.models import DecisionDiagnostics, DecisionStep
from src.understanding.models import (
    IntentDiagnostics,
    StageDetail,
)
from src.planner.models import PlannerDiagnostics, Turn
from src.reasoning.models import ReasoningDiagnostics, RuleEval
from src.validation import (
    EnvironmentInfo,
    GroundTruth,
    attribute_blame,
    build_graph,
)
from src.validation.engine import (
    validate_composer,
    validate_decision,
    validate_planner,
    validate_reasoning,
    validate_understanding,
    _cross_stage_coherence,
)
from src.composer.models import ComposerDiagnostics


# ── helpers ─────────────────────────────────────────────────────────────

def _intent_diag(**kw) -> IntentDiagnostics:
    """Build IntentDiagnostics with defaults and overrides."""
    defaults = dict(
        input="test",
        stage_details={
            "keyword": StageDetail(scores={"fee": 0.8, "admission": 0.2}),
            "entity": StageDetail(scores={"fee": 0.0, "admission": 0.4}),
            "domain": StageDetail(scores={"fee": 0.5}),
            "context": StageDetail(scores={"admission": 0.5, "general": 0.2}),
            "completeness": StageDetail(scores={"admission": 0.2}),
        },
        stage_weights={"keyword": 0.35, "entity": 0.25, "domain": 0.15,
                        "context": 0.15, "completeness": 0.05},
        per_intent_breakdown={"fee": {"keyword": 0.28, "domain": 0.075},
                               "admission": {"entity": 0.1, "context": 0.075,
                                             "completeness": 0.01},
                               "general": {"context": 0.03}},
        pre_conflict={"fee": 0.355, "admission": 0.185, "general": 0.03},
        post_conflict={"fee": 0.355, "admission": 0.074, "general": 0.03},
        winner="fee",
        confidence=0.355,
        winner_reason="test",
        ranked_intents=[("fee", 0.355), ("admission", 0.074), ("general", 0.03)],
        runner_up_score=0.074,
        margin=0.281,
        confidence_class="MEDIUM",
    )
    defaults.update(kw)
    return IntentDiagnostics(**defaults)


def _reasoning_diag(**kw) -> ReasoningDiagnostics:
    defaults = dict(
        input_intent="fee",
        intent_confidence=0.8,
        dominant_signal="financial_concern",
        signal_score=0.3,
        profile_completeness=0.5,
        stage="discovery",
        confidence_score=0.7,
        winner="needs_fee_information",
        problems_traced=[
            RuleEval("anxiety < threshold", False, 0.0, ""),
            RuleEval("confusion < threshold", False, 0.0, ""),
            RuleEval("intent == fee", True, 1.0, "needs_fee_information"),
        ],
    )
    defaults.update(kw)
    return ReasoningDiagnostics(**defaults)


def _decision_diag(**kw) -> DecisionDiagnostics:
    defaults = dict(
        input_problem="needs_fee_information",
        completeness=0.5,
        risks=["insufficient_profile"],
        knowledge_needed=[],
        stage="discovery",
        steps=[DecisionStep(
            step="1 - Problem lookup",
            action="provide_fee_info",
            priority="normal",
            rationale="Student asking about fees",
            conditions=["problem=needs_fee_information"],
        )],
        final_action="provide_fee_info",
        final_priority="normal",
        final_rationale="Student asking about fees",
    )
    defaults.update(kw)
    return DecisionDiagnostics(**defaults)


def _planner_diag(**kw) -> PlannerDiagnostics:
    defaults = dict(
        input_action="provide_fee_info",
        input_rationale="Student asking about fees",
        handler_selected="_beh_inform_ask",
        handler_reason="action=provide_fee_info",
        templates_used=["provide_fee_info_inform", "provide_fee_info_ask"],
        generated_turns=[
            Turn(speaker="assistant", action="inform",
                 content="Fee for CSE is Rs 85,000."),
            Turn(speaker="assistant", action="ask",
                 content="What is your category?", expected_input="category"),
        ],
        was_fallback=False,
    )
    defaults.update(kw)
    return PlannerDiagnostics(**defaults)


def _composer_diag(**kw) -> ComposerDiagnostics:
    defaults = dict(
        system_prompt="test",
        final_prompt="test prompt constructed properly",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=200.0,
        model="groq-llama",
        temperature=0.3,
        finish_reason="stop",
        raw_llm_response="Fee for CSE is Rs 85,000 per year.",
        parsed_response="Fee for CSE is Rs 85,000 per year.",
        final_output="Fee for CSE is Rs 85,000 per year.",
        followed_plan=True,
        violations=[],
        hallucination_risk="low",
    )
    defaults.update(kw)
    return ComposerDiagnostics(**defaults)


# ── Understanding Validator ─────────────────────────────────────────────

class TestUnderstandingValidator:
    def test_winner_has_evidence_passes(self):
        """Normal case: winner has contributing stages."""
        r = validate_understanding(_intent_diag())
        assert r.status == "PASS"
        assert any(c.name == "winner_has_evidence" for c in r.checks)

    def test_winner_no_evidence_fails(self):
        """Winner with zero contributing stages should FAIL."""
        diag = _intent_diag(per_intent_breakdown={"fee": {}})
        r = validate_understanding(diag)
        c = next(c for c in r.checks if c.name == "winner_has_evidence")
        assert c.status == "FAIL"

    def test_winner_unknown_is_warning(self):
        """No intent classified should produce WARNING not FAIL."""
        diag = _intent_diag(winner="unknown", confidence=0.0)
        r = validate_understanding(diag)
        assert r.status == "WARNING"
        assert any(c.name == "winner_known" for c in r.checks)

    def test_margin_tight_warning(self):
        """Margin below 0.15 should produce WARNING."""
        diag = _intent_diag(margin=0.08)
        r = validate_understanding(diag)
        c = next(c for c in r.checks if c.name == "winner_margin")
        assert c.status == "WARNING"

    def test_margin_ambiguous_fail(self):
        """Near-zero margin should produce FAIL-level WARNING."""
        diag = _intent_diag(margin=0.01)
        r = validate_understanding(diag)
        c = next(c for c in r.checks if c.name == "winner_margin")
        # margin < 0.05 but > 0 → WARNING
        assert c.status == "WARNING"
        assert c.confidence < 0.2

    def test_ground_truth_mismatch_detected(self):
        """Semantic check: actual intent != expected intent."""
        gt = GroundTruth(expected_intent="admission")
        diag = _intent_diag(winner="fee")
        r = validate_understanding(diag, ground_truth=gt)
        c = next(c for c in r.checks if c.check_type == "semantic")
        assert c.status == "FAIL"
        assert "fee" in c.detail and "admission" in c.detail

    def test_ground_truth_match_passes(self):
        """Semantic check: actual intent == expected intent."""
        gt = GroundTruth(expected_intent="fee")
        diag = _intent_diag(winner="fee")
        r = validate_understanding(diag, ground_truth=gt)
        c = next(c for c in r.checks if c.check_type == "semantic")
        assert c.status == "PASS"
        assert c.confidence > 0.9

    def test_no_primary_evidence_warning(self):
        """Winner with no keyword/entity/domain evidence gets WARNING."""
        diag = _intent_diag(
            winner="unknown_intent",
            stage_details={
                "keyword": StageDetail(scores={"unknown_intent": 0}),
                "entity": StageDetail(scores={"unknown_intent": 0}),
                "domain": StageDetail(scores={"unknown_intent": 0}),
            },
            per_intent_breakdown={"unknown_intent": {"context": 0.05}},
            confidence=0.4,
        )
        r = validate_understanding(diag)
        c = next((c for c in r.checks if c.name == "winner_primary_evidence"), None)
        assert c is not None
        assert c.status in ("FAIL", "WARNING")

    def test_confidence_scoring_range(self):
        """Strong evidence produces high confidence."""
        diag = _intent_diag(margin=0.5)
        r = validate_understanding(diag)
        assert r.confidence > 0.6


# ── Reasoning Validator ────────────────────────────────────────────────

class TestReasoningValidator:
    def test_intent_problem_match_passes(self):
        """Correct intent→problem mapping passes."""
        r = validate_reasoning(_reasoning_diag())
        assert r.status == "PASS"
        c = next(c for c in r.checks if c.name == "intent_problem_consistency")
        assert c.status == "PASS"

    def test_intent_problem_mismatch_fails(self):
        """Wrong problem for intent should FAIL."""
        diag = _reasoning_diag(winner="needs_hostel_information")
        r = validate_reasoning(diag)
        c = next(c for c in r.checks if c.name == "intent_problem_consistency")
        assert c.status == "FAIL"

    def test_anxiety_not_handled_fails(self):
        """High anxiety but no reassurance should FAIL."""
        diag = _reasoning_diag(
            dominant_signal="anxiety",
            signal_score=0.8,
            winner="needs_fee_information",
        )
        r = validate_reasoning(diag)
        c = next(c for c in r.checks if c.name == "anxiety_handling")
        assert c is not None
        assert c.status == "FAIL"

    def test_ground_truth_problem_match(self):
        """Semantic check: problem matches expected."""
        gt = GroundTruth(expected_problem="needs_fee_information")
        r = validate_reasoning(_reasoning_diag(), ground_truth=gt)
        c = next(c for c in r.checks if c.check_type == "semantic")
        assert c.status == "PASS"

    def test_ground_truth_problem_mismatch(self):
        """Semantic check: problem != expected."""
        gt = GroundTruth(expected_problem="needs_admission_guidance")
        diag = _reasoning_diag(winner="needs_fee_information")
        r = validate_reasoning(diag, ground_truth=gt)
        c = next(c for c in r.checks if c.check_type == "semantic")
        assert c.status == "FAIL"

    def test_low_completeness_warning(self):
        """Low completeness with non-profile problem gets WARNING."""
        diag = _reasoning_diag(profile_completeness=0.1)
        r = validate_reasoning(diag)
        c = next((c for c in r.checks if c.name == "completeness_guard"), None)
        assert c is not None
        assert c.status in ("WARNING", "FAIL")


# ── Decision Validator ─────────────────────────────────────────────────

class TestDecisionValidator:
    def test_action_matches_rule_passes(self):
        """Action matching the decision rule passes."""
        r = validate_decision(_decision_diag())
        assert r.status == "PASS"

    def test_action_override_with_steps_warning(self):
        """Override with justification steps gets WARNING not FAIL."""
        diag = _decision_diag(
            final_action="collect_profile",
            steps=[
                DecisionStep("1 - Problem lookup", "provide_fee_info", "normal", "", []),
                DecisionStep("2 - Knowledge routing", "collect_profile", "high", "override", []),
            ],
        )
        r = validate_decision(diag)
        assert r.status in ("PASS", "WARNING")

    def test_action_mismatch_fails(self):
        """Action != rule with no override steps should FAIL."""
        diag = _decision_diag(
            input_problem="needs_admission_guidance",
            final_action="provide_fee_info",
        )
        r = validate_decision(diag)
        c = next((c for c in r.checks if c.name == "action_override"), None)
        assert c is not None
        assert c.status == "FAIL"

    def test_ground_truth_action_match(self):
        """Semantic check: action matches expected."""
        gt = GroundTruth(expected_action="provide_fee_info")
        r = validate_decision(_decision_diag(), ground_truth=gt)
        c = next(c for c in r.checks if c.check_type == "semantic")
        assert c.status == "PASS"

    def test_ground_truth_action_mismatch(self):
        """Semantic check: action != expected."""
        gt = GroundTruth(expected_action="collect_profile")
        r = validate_decision(_decision_diag(), ground_truth=gt)
        c = next(c for c in r.checks if c.check_type == "semantic")
        assert c.status == "FAIL"


# ── Planner Validator ──────────────────────────────────────────────────

class TestPlannerValidator:
    def test_valid_handler_passes(self):
        """Handler in expected set passes."""
        r = validate_planner(_planner_diag())
        assert r.status == "PASS"

    def test_invalid_handler_warning(self):
        """Handler outside expected set gets WARNING."""
        diag = _planner_diag(handler_selected="_beh_single_ask")
        r = validate_planner(diag)
        c = next(c for c in r.checks if c.name == "behavior_for_action")
        assert c.status == "WARNING"

    def test_empty_turn_content_fails(self):
        """Turn with empty content should FAIL."""
        diag = _planner_diag(generated_turns=[
            Turn(speaker="assistant", action="inform", content=""),
        ])
        r = validate_planner(diag)
        c = next(c for c in r.checks if c.name == "turn_1_content")
        assert c.status == "FAIL"

    def test_ask_without_expected_input_warning(self):
        """Ask turn without expected_input gets WARNING."""
        diag = _planner_diag(generated_turns=[
            Turn(speaker="assistant", action="ask", content="What's your rank?"),
        ])
        r = validate_planner(diag)
        c = next((c for c in r.checks if c.name == "turn_1_expected_input"), None)
        assert c is not None
        assert c.status == "WARNING"

    def test_fallback_warning(self):
        """Fallback handler gets WARNING."""
        diag = _planner_diag(was_fallback=True)
        r = validate_planner(diag)
        c = next(c for c in r.checks if c.name == "fallback_used")
        assert c.status == "WARNING"

    def test_ground_truth_turn_count(self):
        """Turn count matches expected."""
        gt = GroundTruth(expected_turns=2)
        r = validate_planner(_planner_diag(), ground_truth=gt)
        c = next(c for c in r.checks if c.name == "semantic_turn_count")
        assert c.status == "PASS"

    def test_ground_truth_turn_mismatch(self):
        """Turn count != expected gets WARNING."""
        gt = GroundTruth(expected_turns=3)
        r = validate_planner(_planner_diag(), ground_truth=gt)
        c = next(c for c in r.checks if c.name == "semantic_turn_count")
        assert c.status == "WARNING"


# ── Composer Validator ─────────────────────────────────────────────────

class TestComposerValidator:
    def test_mock_llm_only_checks_prompt(self):
        """Mock LLM: skip semantic checks, only validate prompt."""
        env = EnvironmentInfo(llm_type="mock")
        diag = _composer_diag(followed_plan=False)
        r = validate_composer(diag, env=env)
        assert r.status == "PASS"
        assert any(c.name == "prompt_constructed" for c in r.checks)

    def test_mock_missing_prompt_fails(self):
        """Mock LLM with no prompt fails."""
        env = EnvironmentInfo(llm_type="mock")
        diag = _composer_diag(final_prompt="")
        r = validate_composer(diag, env=env)
        assert r.status == "FAIL"

    def test_groq_plan_following_fails(self):
        """Groq LLM: plan violations produce FAIL."""
        env = EnvironmentInfo(llm_type="groq")
        diag = _composer_diag(
            followed_plan=False,
            violations=["plan turn 'inform' not reflected"],
        )
        r = validate_composer(diag, env=env)
        c = next(c for c in r.checks if c.name == "plan_following")
        assert c.status == "FAIL"

    def test_groq_hallucination_warning(self):
        """Groq LLM: medium hallucination risk produces WARNING."""
        env = EnvironmentInfo(llm_type="groq")
        diag = _composer_diag(hallucination_risk="medium")
        r = validate_composer(diag, env=env)
        c = next(c for c in r.checks if c.name == "hallucination_risk")
        assert c.status == "WARNING"


# ── Cross-stage Validator ──────────────────────────────────────────────

class TestCrossStageValidator:
    def test_consistent_stages_pass(self):
        """All stages consistent → PASS."""
        r = _cross_stage_coherence(
            intent_diag=_intent_diag(winner="fee"),
            reasoning_diag=_reasoning_diag(winner="needs_fee_information"),
            decision_diag=_decision_diag(final_action="provide_fee_info", input_problem="needs_fee_information"),
            planner_diag=_planner_diag(input_action="provide_fee_info"),
        )
        assert r.status == "PASS"

    def test_intent_problem_mismatch_fails(self):
        """Intent→problem mismatch should FAIL."""
        r = _cross_stage_coherence(
            intent_diag=_intent_diag(winner="fee"),
            reasoning_diag=_reasoning_diag(winner="needs_hostel_information"),
            decision_diag=None,
            planner_diag=None,
        )
        c = next(c for c in r.checks if c.name == "intent_to_problem")
        assert c is not None
        assert c.status == "FAIL"

    def test_decision_planner_mismatch_fails(self):
        """Decision action != planner input action → FAIL."""
        r = _cross_stage_coherence(
            intent_diag=_intent_diag(winner="fee"),
            reasoning_diag=_reasoning_diag(winner="needs_fee_information"),
            decision_diag=_decision_diag(final_action="provide_fee_info"),
            planner_diag=_planner_diag(input_action="collect_profile"),
        )
        c = next(c for c in r.checks if c.name == "decision_to_planner")
        assert c is not None
        assert c.status == "FAIL"

    def test_mock_composer_skips_plan_check(self):
        """Mock LLM: plan execution check is skipped (PASS)."""
        env = EnvironmentInfo(llm_type="mock")
        r = _cross_stage_coherence(
            intent_diag=_intent_diag(winner="fee"),
            reasoning_diag=_reasoning_diag(winner="needs_fee_information"),
            decision_diag=_decision_diag(final_action="provide_fee_info"),
            planner_diag=_planner_diag(input_action="provide_fee_info"),
            composer_diag=_composer_diag(followed_plan=False),
            env=env,
        )
        c = next(c for c in r.checks if c.name == "plan_execution")
        assert c.status == "PASS"


# ── Blame Attribution ──────────────────────────────────────────────────

class TestBlameAttribution:
    def test_blame_identifies_earliest_fail(self):
        """Attribute blame to earliest FAIL stage (WARNING does not block)."""
        # understanding passes (PASS), reasoning has intent-problem FAIL
        vr = {
            "understanding": validate_understanding(
                _intent_diag(winner="fee", margin=0.5)
            ),
            "reasoning": validate_reasoning(
                _reasoning_diag(winner="needs_hostel_information")
            ),
            "decision": validate_decision(
                _decision_diag(final_action="provide_hostel_info")
            ),
        }
        blame = attribute_blame(vr)
        assert blame.root_cause_stage == "reasoning", \
            f"Expected reasoning, got {blame.root_cause_stage}"

    def test_blame_cascade_order(self):
        """Cascade contains downstream stages in order."""
        vr = {
            "understanding": validate_understanding(_intent_diag(winner="fee")),
            "reasoning": validate_reasoning(
                _reasoning_diag(winner="needs_hostel_information")
            ),
            "decision": validate_decision(_decision_diag(final_action="provide_hostel_info")),
        }
        blame = attribute_blame(vr)
        assert blame.root_cause_stage == "reasoning"
        assert "decision" in blame.cascade

    def test_blame_none_when_all_pass(self):
        """No failures → root_cause_stage is 'none'."""
        vr = {
            "understanding": validate_understanding(_intent_diag(winner="fee")),
            "reasoning": validate_reasoning(_reasoning_diag(winner="needs_fee_information")),
            "decision": validate_decision(_decision_diag(final_action="provide_fee_info")),
            "planner": validate_planner(_planner_diag(input_action="provide_fee_info")),
        }
        blame = attribute_blame(vr)
        assert blame.root_cause_stage == "none"


# ── ValidationResult Merge ─────────────────────────────────────────────

class TestValidationResultMerge:
    def test_merge_passes(self):
        """Two PASS results merge to PASS."""
        from src.validation.models import ValidationResult
        a = ValidationResult.from_checks([])
        b = ValidationResult.from_checks([])
        assert a.merge(b).status == "PASS"

    def test_merge_fail_propagates(self):
        """Merge with FAIL produces FAIL."""
        from src.validation.models import ValidationCheck, ValidationResult
        fail = ValidationResult.from_checks([
            ValidationCheck("x", "FAIL", "fail", 0.1),
        ])
        ok = ValidationResult.from_checks([])
        merged = ok.merge(fail)
        assert merged.status == "FAIL"
        assert len(merged.checks) == 1
