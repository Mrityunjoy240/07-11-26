#!/usr/bin/env python3
"""
Evaluation CLI for the Golden Conversation Benchmark.

Usage:
    # Evaluate a single conversation by ID
    python evaluate.py ADM_LOWRANK_001

    # Evaluate all conversations in a directory
    python evaluate.py data/benchmark/v0.1/

    # Run old vs new comparison on a conversation
    python evaluate.py ADM_LOWRANK_001 --dual

    # Generate a report for all conversations
    python evaluate.py data/benchmark/v0.1/ --report
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Result types ──────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    name: str
    passed: bool
    expected: Any = None
    actual: Any = None
    detail: str = ""


@dataclass
class StageResult:
    stage: str
    passed: int = 0
    total: int = 0
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def score(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0


@dataclass
class TurnResult:
    turn_index: int
    stages: dict[str, StageResult] = field(default_factory=dict)
    must_not_violations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(s.passed for s in self.stages.values())

    @property
    def total(self) -> int:
        return sum(s.total for s in self.stages.values())

    @property
    def score(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0


@dataclass
class ConversationResult:
    conv_id: str
    passed: bool = False
    overall_score: float = 0.0
    turn_results: list[TurnResult] = field(default_factory=list)
    error: str = ""

    @property
    def total_passed(self) -> int:
        return sum(t.passed for t in self.turn_results)

    @property
    def total_checks(self) -> int:
        return sum(t.total for t in self.turn_results)


# ── Loader ────────────────────────────────────────────────────────────────

def load_conversation(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        # Try finding in benchmark directories
        for d in [Path("data/benchmark/v0.1"), Path("data/benchmark/v0.2"),
                   Path("../data/benchmark/v0.1"), Path("../data/benchmark/v0.2")]:
            candidate = d / f"{path}.json" if not path.endswith(".json") else d / path
            if candidate.exists():
                p = candidate
                break
        else:
            raise FileNotFoundError(f"Conversation not found: {path}")
    with open(p) as f:
        return json.load(f)


def load_all(directory: str | Path) -> list[dict[str, Any]]:
    p = Path(directory)
    convs = []
    for f in sorted(p.glob("*.json")):
        try:
            convs.append(load_conversation(f))
        except Exception as e:
            print(f"  [SKIP] {f.name}: {e}")
    return convs


# ── Compliance checks ─────────────────────────────────────────────────────

def check_field(path: str, expected: Any, actual: dict) -> CheckResult:
    """Check that `actual` has a nested field matching `expected`."""
    keys = path.split(".")
    val: Any = actual
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return CheckResult(
                name=path, passed=False, expected=expected, actual=None,
                detail=f"Can't traverse '{k}' on {type(val).__name__}",
            )
    passed = val == expected
    detail = "" if passed else f"Expected {expected!r}, got {val!r}"
    return CheckResult(name=path, passed=passed, expected=expected, actual=val, detail=detail)


def check_contains(path: str, expected_substrings: list[str], actual: dict) -> list[CheckResult]:
    """Check that a string field contains all expected substrings."""
    keys = path.split(".")
    val: Any = actual
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return [CheckResult(name=path, passed=False, expected=expected_substrings, actual=None)]
    if not isinstance(val, str):
            return [CheckResult(name=path, passed=False, expected=expected_substrings,
                                actual=type(val).__name__)]
    results = []
    for s in expected_substrings:
        found = s.lower() in val.lower()
        results.append(CheckResult(
            name=f"{path} contains '{s}'",
            passed=found,
            expected=s,
            actual=val[:100] if not found else "(present)",
            detail="" if found else f"'{s}' not found in '{val[:100]}'",
        ))
    return results


def check_must_not(response: str, violations: list[str]) -> list[str]:
    """Check which forbidden patterns appear in the response."""
    resp_norm = response.lower().replace("_", " ")
    found = []
    for v in violations:
        v_norm = v.lower().replace("_", " ")
        if v_norm in resp_norm:
            found.append(v)
    return found


# ── Evaluate a single turn ────────────────────────────────────────────────

def evaluate_turn(
    turn: dict,
    pipeline_result: dict | None,
    turn_index: int,
) -> TurnResult:
    result = TurnResult(turn_index=turn_index)

    if pipeline_result is None:
        result.stages["pipeline"] = StageResult("pipeline", 0, 1, [
            CheckResult("run", False, detail="No pipeline result available"),
        ])
        return result

    expected = turn.get("expected", {})

    # ── Understanding ─────────────────────────────────────────────────
    u_stage = StageResult("understanding")
    u_exp = expected.get("understanding", {})
    _u_act = pipeline_result.get("understanding", {})

    # Facts
    for fact_field, exp_val in u_exp.get("facts", {}).items():
        if exp_val is not None:
            c = check_field(f"understanding.facts.{fact_field}", exp_val, pipeline_result)
            u_stage.checks.append(c)
            u_stage.total += 1
            if c.passed:
                u_stage.passed += 1

    # Intent
    intent_exp = u_exp.get("intent")
    if intent_exp:
        c = check_field("understanding.intent.primary", intent_exp, pipeline_result)
        u_stage.checks.append(c)
        u_stage.total += 1
        if c.passed:
            u_stage.passed += 1

    # Missing info
    missing_exp = u_exp.get("missing", [])
    u_stage.total += 1
    c = check_field("understanding.missing", missing_exp, pipeline_result)
    # relax: check that actual missing is subset of expected or vice versa
    actual_missing = set(pipeline_result.get("understanding", {}).get("missing", []))
    expected_missing = set(missing_exp)
    overlap = len(actual_missing & expected_missing)
    max_len = max(len(actual_missing), len(expected_missing))
    if max_len > 0 and overlap / max_len >= 0.5:
        c.passed = True
        c.detail = f"Missing overlap {overlap}/{max_len}"
    c.actual = list(actual_missing)
    u_stage.checks.append(c)
    if c.passed:
        u_stage.passed += 1

    result.stages["understanding"] = u_stage

    # ── Reasoning ─────────────────────────────────────────────────────
    r_stage = StageResult("reasoning")
    r_exp = expected.get("reasoning", {})
    r_act = pipeline_result.get("reasoning", {})

    # Only evaluate if pipeline actually produced reasoning data
    if r_act:
        if r_exp.get("stage"):
            c = check_field("reasoning.stage", r_exp["stage"], pipeline_result)
            r_stage.checks.append(c)
            r_stage.total += 1
            if c.passed:
                r_stage.passed += 1

        if r_exp.get("profile_completeness") is not None:
            exp_val = r_exp["profile_completeness"]
            act_val = r_act.get("profile_completeness", -1)
            tol = 0.3
            passed = abs(act_val - exp_val) <= tol
            c = CheckResult(
                "reasoning.profile_completeness",
                passed=passed,
                expected=exp_val,
                actual=act_val,
                detail="" if passed else f"Expected {exp_val}, got {act_val} (tol=0.3)",
            )
            r_stage.checks.append(c)
            r_stage.total += 1
            if c.passed:
                r_stage.passed += 1

        if r_exp.get("confidence"):
            c = check_field("reasoning.confidence", r_exp["confidence"], pipeline_result)
            r_stage.checks.append(c)
            r_stage.total += 1
            if c.passed:
                r_stage.passed += 1

        if r_exp.get("current_problem") is not None:
            exp_problem = r_exp["current_problem"]
            act_problem = r_act.get("current_problem", "")
            passed = exp_problem == act_problem
            c = CheckResult(
                "reasoning.current_problem",
                passed=passed,
                expected=exp_problem,
                actual=act_problem,
                detail="" if passed else f"Expected '{exp_problem}', got '{act_problem}'",
            )
            r_stage.checks.append(c)
            r_stage.total += 1
            if c.passed:
                r_stage.passed += 1

    result.stages["reasoning"] = r_stage

    # ── Brain ─────────────────────────────────────────────────────────
    b_stage = StageResult("brain")
    b_exp = expected.get("brain", {})
    b_act = pipeline_result.get("brain", {})

    # Only evaluate if pipeline actually produced brain data
    if b_act:
        if b_exp.get("applicable") is not None:
            c = check_field("brain.applicable", b_exp["applicable"], pipeline_result)
            b_stage.checks.append(c)
            b_stage.total += 1
            if c.passed:
                b_stage.passed += 1

        if b_exp.get("eligible_branches") is not None:
            exp_branches = set(b_exp["eligible_branches"])
            act_branches = set(b_act.get("eligible_branches", []))
            overlap = len(exp_branches & act_branches)
            passed = overlap >= len(exp_branches) * 0.5 if len(exp_branches) > 0 else len(act_branches) == 0
            c = CheckResult(
                "brain.eligible_branches",
                passed=passed,
                expected=list(exp_branches),
                actual=list(act_branches),
                detail="" if passed else f"Overlap {overlap}/{len(exp_branches)} insufficient",
            )
            b_stage.checks.append(c)
            b_stage.total += 1
            if c.passed:
                b_stage.passed += 1

        if b_exp.get("why") is not None:
            exp_why_conditions = set(r.get("condition", "") for r in b_exp["why"])
            act_why_conditions = set(r.get("condition", "") for r in b_act.get("why", []))
            overlap = len(exp_why_conditions & act_why_conditions)
            passed = overlap >= len(exp_why_conditions) * 0.5 if len(exp_why_conditions) > 0 else len(act_why_conditions) == 0
            c = CheckResult(
                "brain.why",
                passed=passed,
                expected=list(exp_why_conditions),
                actual=list(act_why_conditions),
                detail="" if passed else f"Overlap {overlap}/{len(exp_why_conditions)} insufficient",
            )
            b_stage.checks.append(c)
            b_stage.total += 1
            if c.passed:
                b_stage.passed += 1

    result.stages["brain"] = b_stage

    # ── Decision ──────────────────────────────────────────────────────
    d_stage = StageResult("decision")
    d_exp = expected.get("decision", {})
    d_act = pipeline_result.get("decision", {})

    action_exp = d_exp.get("action")
    action_act = d_act.get("action", "")
    c = CheckResult(
        "decision.action",
        passed=action_act == action_exp,
        expected=action_exp,
        actual=action_act,
        detail="" if action_act == action_exp else f"Expected '{action_exp}', got '{action_act}'",
    )
    d_stage.checks.append(c)
    d_stage.total += 1
    if c.passed:
        d_stage.passed += 1

    result.stages["decision"] = d_stage

    # ── Planner ───────────────────────────────────────────────────────
    p_stage = StageResult("planner")
    p_exp = expected.get("planner", {})
    p_act = pipeline_result.get("plan", {})

    exp_turns = p_exp.get("turns", [])
    act_turns = p_act.get("turns", []) if isinstance(p_act, dict) else []

    for i, exp_t in enumerate(exp_turns):
        if i >= len(act_turns):
            c = CheckResult(
                f"planner.turn[{i}].action", passed=False,
                expected=exp_t.get("action"), actual=None,
                detail="Missing turn in pipeline output",
            )
            p_stage.checks.append(c)
            p_stage.total += 1
            continue

        act_t = act_turns[i] if isinstance(act_turns[i], dict) else {}
        act_action = act_t.get("action", "")
        exp_action = exp_t.get("action", "")
        c = CheckResult(
            f"planner.turn[{i}].action",
            passed=act_action == exp_action,
            expected=exp_action,
            actual=act_action,
            detail=("" if act_action == exp_action
                     else f"Expected '{exp_action}', got '{act_action}'"),
        )
        p_stage.checks.append(c)
        p_stage.total += 1
        if c.passed:
            p_stage.passed += 1

        # Check content contains
        content_checks = exp_t.get("content_contains", [])
        act_content = act_t.get("content", "")
        for s in content_checks:
            found = s.lower() in act_content.lower()
            c = CheckResult(
                f"planner.turn[{i}] contains '{s}'",
                passed=found,
                expected=s,
                actual=act_content[:80],
                detail="" if found else f"'{s}' not found in '{act_content[:80]}'",
            )
            p_stage.checks.append(c)
            p_stage.total += 1
            if c.passed:
                p_stage.passed += 1

    result.stages["planner"] = p_stage

    # ── Must-not ──────────────────────────────────────────────────────
    response_text = pipeline_result.get("response", "")
    must_not_items = turn.get("must_not", [])
    violations = check_must_not(response_text, must_not_items)
    result.must_not_violations = violations

    return result


# ── Evaluate full conversation ────────────────────────────────────────────

def evaluate_conversation(
    conv: dict,
    pipeline_results: list[dict] | None = None,
) -> ConversationResult:
    conv_id = conv["id"]
    result = ConversationResult(conv_id=conv_id)

    for i, turn in enumerate(conv.get("turns", [])):
        pr = pipeline_results[i] if pipeline_results and i < len(pipeline_results) else None
        tr = evaluate_turn(turn, pr, i)
        result.turn_results.append(tr)

    passed_checks = sum(t.passed for t in result.turn_results)
    total_checks = sum(t.total for t in result.turn_results)
    result.overall_score = passed_checks / total_checks if total_checks > 0 else 0.0

    must_not_violations = any(t.must_not_violations for t in result.turn_results)
    result.passed = result.overall_score >= 0.7 and not must_not_violations

    return result


# ── Manual run (no pipeline — just check what would happen) ───────────────

def mock_pipeline_result(conv: dict) -> list[dict]:
    """Create a minimal mock pipeline result for testing the evaluator itself."""
    results = []
    for turn in conv.get("turns", []):
        exp = turn.get("expected", {})
        u = exp.get("understanding", {})
        d = exp.get("decision", {})
        p = exp.get("planner", {})
        results.append({
            "understanding": {
                "intent": {"primary": u.get("intent", "unknown")},
                "facts": {k: v for k, v in u.get("facts", {}).items() if v is not None},
                "missing": u.get("missing", []),
            },
            "decision": {
                "action": d.get("action", ""),
            },
            "plan": {
                "turns": [
                    {"action": t.get("action", ""),
                     "content": " ".join(t.get("content_contains", []))}
                    for t in p.get("turns", [])
                ],
            },
            "response": "Mock assistant response for testing.",
        })
    return results


# ── Output formatting ─────────────────────────────────────────────────────

def print_coverage(result: ConversationResult) -> None:
    """Print per-stage coverage across all turns."""
    stage_totals: dict[str, dict[str, int]] = {}
    for tr in result.turn_results:
        for sname, stage in tr.stages.items():
            cat = stage_totals.setdefault(sname, {"passed": 0, "total": 0})
            cat["passed"] += stage.passed
            cat["total"] += stage.total

    if not stage_totals:
        return

    print("\n  ── Per-stage coverage ──")
    for sname in ["understanding", "reasoning", "brain", "decision", "planner"]:
        cat = stage_totals.get(sname)
        if cat and cat["total"] > 0:
            pct = cat["passed"] / cat["total"] * 100
            icon = "✓" if pct >= 80 else "✗"
            print(f"  {icon} {sname:20s} {cat['passed']:3d}/{cat['total']:<3d} ({pct:5.1f}%)")
    must_not_total = sum(len(tr.must_not_violations) for tr in result.turn_results)
    icon = "✓" if must_not_total == 0 else "✗"
    print(f"  {icon} {'must_not':20s} violations={must_not_total}")


def print_result(result: ConversationResult) -> None:
    print(f"\n{'='*60}")
    print(f"  {result.conv_id}")
    print(f"{'='*60}")

    for tr in result.turn_results:
        print(f"\n  ── Turn {tr.turn_index + 1} ──")
        for stage_name, stage in tr.stages.items():
            icon = "✓" if stage.score >= 0.8 else "✗"
            print(f"  {icon} {stage_name.upper()}  {stage.passed}/{stage.total}")
            for c in stage.checks:
                if not c.passed:
                    print(f"      ✗ {c.name}: {c.detail}")
        if tr.must_not_violations:
            print(f"      ✗ VIOLATIONS: {', '.join(tr.must_not_violations)}")

    print("\n  ── Overall ──")
    print(f"  Score: {result.overall_score:.0%} ({result.total_passed}/{result.total_checks})")
    print(f"  Status: {'✓ PASS' if result.passed else '✗ FAIL'}")
    print_coverage(result)
    print()


def print_summary(results: list[ConversationResult]) -> None:
    total_p = sum(r.total_passed for r in results)
    total_c = sum(r.total_checks for r in results)
    avg = total_p / total_c if total_c > 0 else 0.0
    passed = sum(1 for r in results if r.passed)
    print(f"\n{'='*60}")
    print(f"  SUMMARY — {len(results)} conversations")
    print(f"{'='*60}")
    print(f"  Passed:  {passed}/{len(results)}")
    print(f"  Overall: {avg:.0%} ({total_p}/{total_c})")
    print(f"  Score:   {avg*100:.1f}%")

    # Aggregate per-stage coverage across all conversations
    stage_agg: dict[str, dict[str, int]] = {}
    for r in results:
        for sname in ["understanding", "reasoning", "brain", "decision", "planner"]:
            for tr in r.turn_results:
                s = tr.stages.get(sname)
                if s and s.total > 0:
                    cat = stage_agg.setdefault(sname, {"passed": 0, "total": 0})
                    cat["passed"] += s.passed
                    cat["total"] += s.total

    if stage_agg:
        print("\n  ── Aggregate per-stage coverage ──")
        for sname in ["understanding", "reasoning", "brain", "decision", "planner"]:
            cat = stage_agg.get(sname)
            if cat and cat["total"] > 0:
                pct = cat["passed"] / cat["total"] * 100
                print(f"     {sname:20s} {cat['passed']:3d}/{cat['total']:<3d} ({pct:5.1f}%)")

    must_not_count = sum(
        1 for r in results
        for tr in r.turn_results
        if tr.must_not_violations
    )
    print(f"     {'must_not':20s} violations in {must_not_count} turn(s)")
    print()


# ── Main CLI ──────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    target = args[0]
    is_directory = os.path.isdir(target)
    use_dual = "--dual" in args
    _show_report = "--report" in args  # reserved for future use

    if is_directory:
        convs = load_all(target)
    else:
        convs = [load_conversation(target)]

    results: list[ConversationResult] = []
    for conv in convs:
        if is_directory:
            print(f"  Evaluating {conv['id']}...", end=" ")
        # Use expected data as mock pipeline result for the evaluator test
        mock_results = mock_pipeline_result(conv) if not use_dual else None
        result = evaluate_conversation(conv, mock_results)
        results.append(result)
        if is_directory:
            print(f"{'PASS' if result.passed else 'FAIL'} ({result.overall_score:.0%})")
        else:
            print_result(result)

    if len(results) > 1:
        print_summary(results)

    # Non-zero exit if any failed
    if not all(r.passed for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
