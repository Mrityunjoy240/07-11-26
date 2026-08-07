"""State validation for every pipeline stage.

Rule-based checks, ground-truth comparison, confidence scoring,
and environment awareness.
"""

from __future__ import annotations

from src.composer.models import ComposerDiagnostics
from src.decision.engine import _DECISION_RULES
from src.decision.models import DecisionDiagnostics
from src.understanding.models import IntentDiagnostics
from src.planner.models import PlannerDiagnostics
from src.reasoning.models import ReasoningDiagnostics
from src.validation.models import (
    EnvironmentInfo,
    GroundTruth,
    ValidationCheck,
    ValidationResult,
)

# ── helpers ─────────────────────────────────────────────────────────────

def _gt_check(
    name: str, actual: str, expected: str, label: str,
) -> ValidationCheck | None:
    if not expected:
        return None
    match = actual == expected
    conf = 0.98 if match else 0.05
    return ValidationCheck(
        name=name,
        status="PASS" if match else "FAIL",
        detail=(f"Actual {label}='{actual}' matches expected '{expected}'"
                if match else
                f"Actual {label}='{actual}' ≠ expected '{expected}'"),
        confidence=conf,
        check_type="semantic",
    )


def _evidence_count(diag: IntentDiagnostics) -> int:
    return sum(
        1 for stage in diag.stage_details.values()
        for v in stage.scores.values()
        if v > 0
    )


# ── Understanding ───────────────────────────────────────────────────────

def validate_understanding(
    diag: IntentDiagnostics,
    ground_truth: GroundTruth | None = None,
    env: EnvironmentInfo | None = None,
) -> ValidationResult:
    checks: list[ValidationCheck] = []
    winner = diag.winner

    # Ground-truth comparison
    if ground_truth and not ground_truth.is_empty():
        c = _gt_check("semantic_intent", winner, ground_truth.expected_intent, "intent")
        if c:
            checks.append(c)

    if winner == "unknown":
        checks.append(ValidationCheck(
            "winner_known", "PASS" if diag.confidence > 0 else "WARNING",
            "No intent classified — expected for greetings",
            confidence=0.6,
        ))
        return ValidationResult.from_checks(checks)

    # Evidence check with confidence
    breakdown = diag.per_intent_breakdown.get(winner, {})
    contributing = sum(1 for v in breakdown.values() if v > 0)
    has_evidence = contributing > 0
    # Confidence: more contributing stages = higher confidence
    ev_conf = min(0.5 + 0.15 * contributing, 0.98)
    checks.append(ValidationCheck(
        "winner_has_evidence",
        "FAIL" if not has_evidence else "PASS",
        f"Winner '{winner}' has {contributing} contributing stages",
        confidence=ev_conf if has_evidence else 0.05,
    ))

    # Margin with confidence
    margin = diag.margin
    if margin < 0.05:
        checks.append(ValidationCheck(
            "winner_margin",
            "WARNING" if margin > 0 else "FAIL",
            f"Margin={margin:.3f} — {'ambiguous' if margin < 0.05 else 'very tight'}",
            confidence=margin * 5,
        ))
    elif margin < 0.15:
        checks.append(ValidationCheck(
            "winner_margin", "WARNING",
            f"Margin={margin:.3f} — low confidence",
            confidence=margin,
        ))
    else:
        checks.append(ValidationCheck(
            "winner_margin", "PASS",
            f"Margin={margin:.3f} — clear winner",
            confidence=min(margin, 0.98),
        ))

    # Runner-up ambiguity
    ranked = diag.ranked_intents
    if len(ranked) >= 2:
        runner_up_score = ranked[1][1]
        if runner_up_score > 0.2 and margin < 0.15:
            checks.append(ValidationCheck(
                "runner_up_ambiguity", "WARNING",
                f"Runner-up '{ranked[1][0]}' at {runner_up_score:.3f} is close to winner",
                confidence=1.0 - runner_up_score,
            ))

    # Primary evidence sources
    kw = diag.stage_details.get("keyword", type("", (), {"scores": {}})()).scores
    ent = diag.stage_details.get("entity", type("", (), {"scores": {}})()).scores
    dom = diag.stage_details.get("domain", type("", (), {"scores": {}})()).scores
    has_kw = winner in kw and kw[winner] > 0
    has_ent = winner in ent and ent[winner] > 0
    has_dom = winner in dom and dom[winner] > 0
    sources = sum([has_kw, has_ent, has_dom])
    if sources == 0:
        checks.append(ValidationCheck(
            "winner_primary_evidence",
            "WARNING" if diag.confidence > 0.3 else "FAIL",
            f"Winner '{winner}' has no keyword, entity, or domain evidence",
            confidence=0.1,
        ))
    else:
        checks.append(ValidationCheck(
            "winner_primary_evidence", "PASS",
            f"Winner '{winner}' supported by {sources} evidence source(s)",
            confidence=min(0.5 + 0.2 * sources, 0.98),
        ))

    return ValidationResult.from_checks(checks)


# ── Reasoning ───────────────────────────────────────────────────────────

_INTENT_PROBLEM_MAP: dict[str, str] = {
    "fee": "needs_fee_information",
    "admission": "needs_admission_guidance",
    "placement": "needs_placement_information",
    "hostel": "needs_hostel_information",
    "scholarship": "needs_scholarship_information",
    "cutoff": "needs_cutoff_information",
    "department": "needs_institution_info",
    "counseling_info": "needs_personalized_guidance",
    "transfer": "needs_transfer_information",
    "grievance": "needs_grievance_resolution",
    "loan": "needs_loan_info",
    "document": "needs_document_info",
    "safety": "needs_safety_info",
    "career_confusion": "needs_career_guidance",
}


def validate_reasoning(
    diag: ReasoningDiagnostics,
    ground_truth: GroundTruth | None = None,
    env: EnvironmentInfo | None = None,
) -> ValidationResult:
    checks: list[ValidationCheck] = []
    winner = diag.winner
    intent = diag.input_intent
    signal = diag.dominant_signal
    signal_score = diag.signal_score

    # Ground-truth
    if ground_truth and not ground_truth.is_empty():
        c = _gt_check("semantic_problem", winner, ground_truth.expected_problem, "problem")
        if c:
            checks.append(c)

    # Intent-to-problem consistency with confidence
    expected_from_intent = _INTENT_PROBLEM_MAP.get(intent, "")

    if winner == expected_from_intent:
        checks.append(ValidationCheck(
            "intent_problem_consistency", "PASS",
            f"Problem '{winner}' correctly maps from intent '{intent}'",
            confidence=0.95, check_type="dependency",
        ))
    elif winner == "needs_reassurance":
        justified = signal == "anxiety" and signal_score > 0.4
        checks.append(ValidationCheck(
            "intent_problem_consistency", "PASS" if justified else "WARNING",
            (f"Problem 'needs_reassurance' correctly overridden by anxiety ({signal_score:.2f})"
             if justified else
             f"Problem 'needs_reassurance' chosen but anxiety={signal_score:.2f}"),
            confidence=0.9 if justified else signal_score,
            check_type="dependency",
        ))
    elif winner == "needs_clarification":
        checks.append(ValidationCheck(
            "intent_problem_consistency", "PASS",
            f"Problem 'needs_clarification' from signal '{signal}'",
            confidence=0.85, check_type="dependency",
        ))
    elif winner in ("needs_profile_initial", "needs_profile_completion"):
        checks.append(ValidationCheck(
            "intent_problem_consistency", "WARNING",
            f"Problem '{winner}' from completeness={diag.profile_completeness:.2f} — no intent match",
            confidence=0.5, check_type="dependency",
        ))
    else:
        checks.append(ValidationCheck(
            "intent_problem_consistency",
            "FAIL" if expected_from_intent else "WARNING",
            f"Problem '{winner}' doesn't match expected '{expected_from_intent}' from intent '{intent}'",
            confidence=0.1, check_type="dependency",
        ))

    # Signal-to-problem handling
    if signal == "anxiety" and signal_score > 0.4 and winner != "needs_reassurance":
        checks.append(ValidationCheck(
            "anxiety_handling", "FAIL",
            f"Anxiety={signal_score:.2f} but problem is '{winner}' not 'needs_reassurance'",
            confidence=0.95, check_type="semantic",
        ))
    elif signal in ("confusion", "frustration") and signal_score > 0.5 and winner != "needs_clarification":
        checks.append(ValidationCheck(
            "confusion_handling",
            "FAIL" if signal_score > 0.7 else "WARNING",
            f"Signal '{signal}'={signal_score:.2f} but problem is '{winner}' not 'needs_clarification'",
            confidence=signal_score, check_type="semantic",
        ))

    # Completeness guard
    if diag.profile_completeness < 0.3 and winner not in (
        "needs_profile_initial", "needs_profile_completion", "needs_reassurance",
    ):
        checks.append(ValidationCheck(
            "completeness_guard",
            "WARNING" if expected_from_intent else "FAIL",
            f"Completeness={diag.profile_completeness:.2f} but problem is '{winner}' not profile-related",
            confidence=min(diag.profile_completeness * 2, 0.5),
            check_type="dependency",
        ))

    # Rule trace — confidence based on whether winning rule exists
    matched_rules = [r for r in diag.problems_traced if r.matched]
    if not matched_rules:
        checks.append(ValidationCheck(
            "rule_trace", "WARNING",
            "No traced rules matched — winner may be from fallback",
            confidence=0.3,
        ))

    return ValidationResult.from_checks(checks)


# ── Decision ────────────────────────────────────────────────────────────

def validate_decision(
    diag: DecisionDiagnostics,
    ground_truth: GroundTruth | None = None,
    env: EnvironmentInfo | None = None,
) -> ValidationResult:
    checks: list[ValidationCheck] = []
    problem = diag.input_problem
    final_action = diag.final_action

    # Ground-truth
    if ground_truth and not ground_truth.is_empty():
        c = _gt_check("semantic_action", final_action, ground_truth.expected_action, "action")
        if c:
            checks.append(c)

    # Problem-to-action mapping
    rule = _DECISION_RULES.get(problem)
    if rule:
        expected_action = rule[0]
        if final_action == expected_action:
            checks.append(ValidationCheck(
                "problem_action_mapping", "PASS",
                f"Problem '{problem}' → '{final_action}' matches rule",
                confidence=0.95, check_type="dependency",
            ))
        else:
            overrides = [s for s in diag.steps if s.step.startswith(("2", "3", "4"))]
            if overrides:
                reasons = "; ".join(f"{s.step}: {s.action}" for s in overrides)
                checks.append(ValidationCheck(
                    "action_override", "WARNING",
                    f"Final '{final_action}' overrode rule '{expected_action}'. Steps: {reasons}",
                    confidence=0.4, check_type="dependency",
                ))
            else:
                checks.append(ValidationCheck(
                    "action_override", "FAIL",
                    f"Final '{final_action}' ≠ rule '{expected_action}' with no override",
                    confidence=0.05, check_type="dependency",
                ))
    else:
        checks.append(ValidationCheck(
            "problem_action_mapping", "WARNING",
            f"Problem '{problem}' has no rule — using fallback",
            confidence=0.3,
        ))

    # Completeness guard
    if diag.completeness < 0.3:
        guard_steps = [s for s in diag.steps if "Incompleteness guard" in s.step]
        if final_action == "collect_profile" and not guard_steps:
            checks.append(ValidationCheck(
                "completeness_guard", "FAIL",
                f"Completeness={diag.completeness:.2f} but guard didn't fire for 'collect_profile'",
                confidence=0.1,
            ))

    # Stage priority
    priority = diag.steps[-1].priority if diag.steps else ""
    if diag.stage == "decision" and priority != "high":
        checks.append(ValidationCheck(
            "priority_for_decision_stage", "WARNING",
            f"Stage='decision' but priority='{priority}' not 'high'",
            confidence=0.4,
        ))

    return ValidationResult.from_checks(checks)


# ── Planner ─────────────────────────────────────────────────────────────

_ACTION_TO_BEHAVIOR: dict[str, list[str]] = {
    "collect_profile": ["_beh_single_ask", "_beh_inform_ask"],
    "recommend_branches": ["_beh_recommend_ask", "_beh_empathy_reassure",
                           "_beh_empathy_legacy", "_beh_empathy_reassure_ask"],
    "provide_fee_info": ["_beh_inform_ask"],
    "provide_hostel_info": ["_beh_inform_ask", "_beh_empathy_reassure_inform_ask"],
    "provide_admission_guidance": ["_beh_inform_ask"],
    "provide_cutoff_info": ["_beh_inform_ask"],
    "provide_guidance": ["_beh_inform_ask"],
    "reassure": ["_beh_empathy_reassure"],
    "provide_scholarship_info": ["_beh_empathy_triple", "_beh_inform_ask"],
}


def validate_planner(
    diag: PlannerDiagnostics,
    ground_truth: GroundTruth | None = None,
    env: EnvironmentInfo | None = None,
) -> ValidationResult:
    checks: list[ValidationCheck] = []
    action = diag.input_action
    handler = diag.handler_selected

    expected_handlers = _ACTION_TO_BEHAVIOR.get(action, [])
    valid = not expected_handlers or handler in expected_handlers
    checks.append(ValidationCheck(
        "behavior_for_action", "PASS" if valid else "WARNING",
        f"Handler '{handler}' {'valid' if valid else 'not in expected'} for action '{action}'",
        confidence=0.9 if valid else 0.3,
        check_type="dependency",
    ))

    for i, turn in enumerate(diag.generated_turns, 1):
        if not turn.content.strip():
            checks.append(ValidationCheck(
                f"turn_{i}_content", "FAIL",
                f"Turn {i} ({turn.action}) has empty content",
                confidence=0.05,
            ))
            continue
        if turn.action == "ask" and not turn.expected_input:
            checks.append(ValidationCheck(
                f"turn_{i}_expected_input", "WARNING",
                f"Turn {i} is 'ask' but no expected_input",
                confidence=0.4,
            ))

    if diag.was_fallback:
        checks.append(ValidationCheck(
            "fallback_used", "WARNING",
            f"No handler for action '{action}' — fallback used",
            confidence=0.3,
        ))

    # Ground-truth: expected turn count
    if ground_truth and ground_truth.expected_turns > 0:
        actual = len(diag.generated_turns)
        match = actual == ground_truth.expected_turns
        checks.append(ValidationCheck(
            "semantic_turn_count",
            "PASS" if match else "WARNING",
            f"Turns: actual={actual}, expected={ground_truth.expected_turns}",
            confidence=0.95 if match else 0.3,
            check_type="semantic",
        ))

    return ValidationResult.from_checks(checks)


# ── Composer ────────────────────────────────────────────────────────────

def validate_composer(
    diag: ComposerDiagnostics,
    ground_truth: GroundTruth | None = None,
    env: EnvironmentInfo | None = None,
) -> ValidationResult:
    checks: list[ValidationCheck] = []
    if env is None:
        env = EnvironmentInfo()

    # Skip semantic checks for mock LLM
    if env.llm_type == "mock":
        # Validate prompt construction only, not output
        if diag.final_prompt:
            checks.append(ValidationCheck(
                "prompt_constructed", "PASS",
                f"Prompt built ({len(diag.final_prompt)} chars)",
                confidence=0.98,
            ))
        else:
            checks.append(ValidationCheck(
                "prompt_constructed", "FAIL",
                "No prompt was constructed",
                confidence=0.05,
            ))
        return ValidationResult.from_checks(checks)

    # Full semantic checks for production LLM
    if not diag.followed_plan:
        checks.append(ValidationCheck(
            "plan_following",
            "FAIL" if diag.violations else "WARNING",
            f"Plan violations: {'; '.join(diag.violations[:3])}" if diag.violations else "Unknown",
            confidence=0.1 if diag.violations else 0.4,
            check_type="semantic",
        ))

    if diag.hallucination_risk in ("high", "medium"):
        checks.append(ValidationCheck(
            "hallucination_risk", "WARNING",
            f"Risk: {diag.hallucination_risk}",
            confidence={"low": 0.95, "medium": 0.5, "high": 0.1}.get(
                diag.hallucination_risk, 0.5),
            check_type="semantic",
        ))

    if diag.finish_reason == "length" and diag.completion_tokens > 0:
        checks.append(ValidationCheck(
            "truncated_output", "WARNING",
            f"Truncated at {diag.completion_tokens} tokens",
            confidence=0.3,
        ))

    if not diag.parsed_response.strip():
        checks.append(ValidationCheck(
            "empty_response", "FAIL",
            "Parsed response is empty",
            confidence=0.05,
        ))

    return ValidationResult.from_checks(checks)


# ── Cross-stage coherence ──────────────────────────────────────────────

def _cross_stage_coherence(
    intent_diag: IntentDiagnostics | None,
    reasoning_diag: ReasoningDiagnostics | None,
    decision_diag: DecisionDiagnostics | None,
    planner_diag: PlannerDiagnostics | None,
    composer_diag: ComposerDiagnostics | None = None,
    env: EnvironmentInfo | None = None,
) -> ValidationResult:
    checks: list[ValidationCheck] = []
    if env is None:
        env = EnvironmentInfo()

    if intent_diag and reasoning_diag:
        intent = intent_diag.winner
        problem = reasoning_diag.winner
        expected = _INTENT_PROBLEM_MAP.get(intent)
        if expected and problem not in (
            expected, "needs_reassurance", "needs_clarification",
            "needs_profile_initial", "needs_profile_completion",
        ):
            checks.append(ValidationCheck(
                "intent_to_problem", "FAIL",
                f"Intent '{intent}' → Problem '{problem}' (expected '{expected}')",
                confidence=0.05, check_type="dependency",
            ))

    if decision_diag and planner_diag:
        da = decision_diag.final_action
        pa = planner_diag.input_action
        if da != pa:
            checks.append(ValidationCheck(
                "decision_to_planner", "FAIL",
                f"Decision '{da}' ≠ Planner '{pa}'",
                confidence=0.05, check_type="dependency",
            ))

    if planner_diag and composer_diag:
        if composer_diag.followed_plan is False:
            # Skip in mock mode — prompt construction is sufficient
            if env.llm_type == "mock":
                checks.append(ValidationCheck(
                    "plan_execution", "PASS",
                    "Mock LLM — plan execution not applicable",
                    confidence=0.95,
                ))
            else:
                checks.append(ValidationCheck(
                    "plan_execution",
                    "FAIL" if composer_diag.violations else "WARNING",
                    f"Composer didn't follow plan: {'; '.join(composer_diag.violations[:3])}",
                    confidence=0.1, check_type="dependency",
                ))

    if not checks:
        checks.append(ValidationCheck(
            "cross_stage", "PASS", "No coherence issues",
            confidence=0.95,
        ))

    return ValidationResult.from_checks(checks)


# ── Orchestrator ────────────────────────────────────────────────────────

def run_all_validations(
    intent_diag: IntentDiagnostics | None = None,
    reasoning_diag: ReasoningDiagnostics | None = None,
    decision_diag: DecisionDiagnostics | None = None,
    planner_diag: PlannerDiagnostics | None = None,
    composer_diag: ComposerDiagnostics | None = None,
    ground_truth: GroundTruth | None = None,
    env: EnvironmentInfo | None = None,
) -> dict[str, ValidationResult]:
    results: dict[str, ValidationResult] = {}
    if intent_diag:
        results["understanding"] = validate_understanding(intent_diag, ground_truth, env)
    if reasoning_diag:
        results["reasoning"] = validate_reasoning(reasoning_diag, ground_truth, env)
    if decision_diag:
        results["decision"] = validate_decision(decision_diag, ground_truth, env)
    if planner_diag:
        results["planner"] = validate_planner(planner_diag, ground_truth, env)
    if composer_diag:
        results["composer"] = validate_composer(composer_diag, ground_truth, env)
    results["cross_stage"] = _cross_stage_coherence(
        intent_diag, reasoning_diag, decision_diag, planner_diag, composer_diag, env,
    )
    return results
