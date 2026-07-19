"""
Mutation tests — verify the evaluator catches deliberately injected failures.

For each mutated pipeline result, exactly ONE stage should fail.
All other stages should still pass.

This proves the evaluator is trustworthy before we scale the benchmark.
"""

from typing import Any

from scripts.evaluate import (
    ConversationResult,
    evaluate_conversation,
    evaluate_turn,
    load_conversation,
    mock_pipeline_result,
)

_FIXTURE = "ADM_LOWRANK_001"


def _load() -> dict[str, Any]:
    return load_conversation(f"data/benchmark/v0.1/{_FIXTURE}.json")


def _deepcopy_result(results: list[dict]) -> list[dict]:
    import copy
    return copy.deepcopy(results)


# ── Mutation helpers ────────────────────────────────────────────────────

def _mutate_understanding_facts(results: list[dict], turn: int, field: str, wrong_value: Any) -> list[dict]:
    r = _deepcopy_result(results)
    r[turn]["understanding"]["facts"][field] = wrong_value
    return r


def _mutate_understanding_intent(results: list[dict], turn: int, wrong_intent: str) -> list[dict]:
    r = _deepcopy_result(results)
    r[turn]["understanding"]["intent"]["primary"] = wrong_intent
    return r


def _mutate_decision_action(results: list[dict], turn: int, wrong_action: str) -> list[dict]:
    r = _deepcopy_result(results)
    r[turn]["decision"]["action"] = wrong_action
    return r


def _mutate_planner_action(results: list[dict], turn: int, plan_turn: int, wrong_action: str) -> list[dict]:
    r = _deepcopy_result(results)
    if plan_turn < len(r[turn]["plan"]["turns"]):
        r[turn]["plan"]["turns"][plan_turn]["action"] = wrong_action
    return r


def _mutate_planner_content(results: list[dict], turn: int, plan_turn: int, content: str) -> list[dict]:
    r = _deepcopy_result(results)
    if plan_turn < len(r[turn]["plan"]["turns"]):
        r[turn]["plan"]["turns"][plan_turn]["content"] = content
    return r


def _mutate_must_not_violation(results: list[dict], turn: int, forbidden_item: str) -> list[dict]:
    r = _deepcopy_result(results)
    r[turn]["response"] = f"I think you should consider {forbidden_item} as an option."
    return r


def _assert_stage(result: ConversationResult, turn: int, stage: str, expected_passed: int, expected_total: int, must_fail: bool = False) -> None:
    tr = result.turn_results[turn]
    s = tr.stages.get(stage)
    assert s is not None, f"Stage '{stage}' not found in turn {turn}"
    assert s.passed == expected_passed, (
        f"[{result.conv_id}] turn {turn} {stage}: expected {expected_passed}/{expected_total} passed, "
        f"got {s.passed}/{s.total}. Checks: {[f'✗ {c.name}: {c.detail}' for c in s.checks if not c.passed]}"
    )
    assert s.total == expected_total, (
        f"[{result.conv_id}] turn {turn} {stage}: expected total {expected_total}, got {s.total}"
    )
    if must_fail:
        assert s.score < 1.0, f"[{result.conv_id}] turn {turn} {stage} should have failed but passed all"


# ── Mutation tests ──────────────────────────────────────────────────────

def test_mutation_understanding_wrong_rank():
    """Turn 0: rank should be 48000, inject 84000 → understanding catches it."""
    conv = _load()
    good = mock_pipeline_result(conv)
    bad = _mutate_understanding_facts(good, 0, "rank", 84000)
    result = evaluate_conversation(conv, bad)
    _assert_stage(result, 0, "understanding", 3, 4, must_fail=True)


def test_mutation_understanding_wrong_intent():
    """Turn 0: intent should be admission, inject fee → understanding catches it."""
    conv = _load()
    good = mock_pipeline_result(conv)
    bad = _mutate_understanding_intent(good, 0, "fee")
    result = evaluate_conversation(conv, bad)
    _assert_stage(result, 0, "understanding", 3, 4, must_fail=True)


def test_mutation_understanding_wrong_pcm():
    """Turn 1: PCM should be 82, inject 95 → understanding catches it."""
    conv = _load()
    good = mock_pipeline_result(conv)
    bad = _mutate_understanding_facts(good, 1, "pcm_percentage", 95)
    result = evaluate_conversation(conv, bad)
    _assert_stage(result, 1, "understanding", 2, 3, must_fail=True)


def test_mutation_decision_wrong_action_turn0():
    """Turn 0: should be collect_profile, inject recommend_branches → decision catches it."""
    conv = _load()
    good = mock_pipeline_result(conv)
    bad = _mutate_decision_action(good, 0, "recommend_branches")
    result = evaluate_conversation(conv, bad)
    _assert_stage(result, 0, "decision", 0, 1, must_fail=True)


def test_mutation_decision_wrong_action_turn2():
    """Turn 2: should be recommend_branches, inject collect_profile → decision catches it."""
    conv = _load()
    good = mock_pipeline_result(conv)
    bad = _mutate_decision_action(good, 2, "collect_profile")
    result = evaluate_conversation(conv, bad)
    _assert_stage(result, 2, "decision", 0, 1, must_fail=True)


def test_mutation_planner_wrong_action():
    """Turn 0: planner turn[0] should be ask, inject recommend → planner catches it."""
    conv = _load()
    good = mock_pipeline_result(conv)
    bad = _mutate_planner_action(good, 0, 0, "recommend")
    result = evaluate_conversation(conv, bad)
    _assert_stage(result, 0, "planner", 2, 3, must_fail=True)


def test_mutation_planner_missing_content():
    """Turn 0: should contain 'PCM' and 'percentage', inject unrelated → planner catches it."""
    conv = _load()
    good = mock_pipeline_result(conv)
    bad = _mutate_planner_content(good, 0, 0, "Tell me about your hobbies")
    result = evaluate_conversation(conv, bad)
    _assert_stage(result, 0, "planner", 1, 3, must_fail=True)


def test_mutation_must_not_detected():
    """Turn 0: must_not includes 'ask_interest_before_pcm', inject it → violation flagged."""
    conv = _load()
    good = mock_pipeline_result(conv)
    bad = _mutate_must_not_violation(good, 0, "ask_interest_before_pcm")
    result = evaluate_conversation(conv, bad)
    assert len(result.turn_results[0].must_not_violations) >= 1, "Must-not violation not detected"
    _assert_stage(result, 0, "understanding", 4, 4)  # understanding intact
    _assert_stage(result, 0, "decision", 1, 1)       # decision intact


def test_mutation_planner_content_contains_partial_fail():
    """Turn 0: expect 'PCM' and 'percentage', provide only 'PCM' → one check passes, one fails."""
    conv = _load()
    good = mock_pipeline_result(conv)
    bad = _mutate_planner_content(good, 0, 0, "Please tell me your PCM marks")
    result = evaluate_conversation(conv, bad)
    _assert_stage(result, 0, "planner", 2, 3, must_fail=True)


def test_mutation_understanding_only_intact():
    """Only understanding mutated → decision and planner should still pass."""
    conv = _load()
    good = mock_pipeline_result(conv)
    bad = _mutate_understanding_facts(good, 0, "rank", 99999)
    result = evaluate_conversation(conv, bad)
    _assert_stage(result, 0, "understanding", 3, 4, must_fail=True)
    _assert_stage(result, 0, "decision", 1, 1)
    _assert_stage(result, 0, "planner", 3, 3)


def test_mutation_decision_only_intact():
    """Only decision mutated → understanding should still pass."""
    conv = _load()
    good = mock_pipeline_result(conv)
    bad = _mutate_decision_action(good, 0, "provide_fee_info")
    result = evaluate_conversation(conv, bad)
    _assert_stage(result, 0, "understanding", 4, 4)
    _assert_stage(result, 0, "decision", 0, 1, must_fail=True)


def test_mutation_isolated_per_turn():
    """Mutating turn 0 must not affect turn 1 or vice versa."""
    conv = _load()
    good = mock_pipeline_result(conv)

    # Mutate turn 0 rank
    bad0 = _mutate_understanding_facts(good, 0, "rank", 99999)
    r0 = evaluate_conversation(conv, bad0)
    _assert_stage(r0, 0, "understanding", 3, 4, must_fail=True)
    _assert_stage(r0, 1, "understanding", 3, 3)  # turn 1 intact

    # Mutate turn 1 PCM
    bad1 = _mutate_understanding_facts(good, 1, "pcm_percentage", 65)
    r1 = evaluate_conversation(conv, bad1)
    _assert_stage(r1, 0, "understanding", 4, 4)  # turn 0 intact
    _assert_stage(r1, 1, "understanding", 2, 3, must_fail=True)


def test_mutation_all_stages_for_turn_2():
    """Verify each stage independently on turn 2 (interest response)."""
    conv = _load()
    good = mock_pipeline_result(conv)

    # Wrong interest fact for turn 2
    bad = _mutate_understanding_facts(good, 2, "interest", "placement")
    result = evaluate_conversation(conv, bad)
    _assert_stage(result, 2, "understanding", 2, 3, must_fail=True)

    # Wrong decision on turn 2 (should be recommend_branches)
    bad2 = _mutate_decision_action(good, 2, "collect_profile")
    result2 = evaluate_conversation(conv, bad2)
    _assert_stage(result2, 2, "decision", 0, 1, must_fail=True)

    # Wrong planner action on turn 2, plan turn 0 (should be recommend → ask)
    bad3 = _mutate_planner_action(good, 2, 0, "ask")
    result3 = evaluate_conversation(conv, bad3)
    assert result3.turn_results[2].stages["planner"].score < 1.0, "Planner should have failed"


def test_mutation_must_not_with_clean_response_passes():
    """Default mock response has no forbidden content → must-not passes."""
    conv = _load()
    good = mock_pipeline_result(conv)
    result = evaluate_conversation(conv, good)
    for tr in result.turn_results:
        assert len(tr.must_not_violations) == 0, f"Unexpected violations: {tr.must_not_violations}"


def test_evaluator_rejects_empty_pipeline_result():
    """Missing pipeline result → conversation should not pass."""
    conv = _load()
    result = evaluate_conversation(conv, None)
    assert not result.passed
    assert result.total_checks > 0
