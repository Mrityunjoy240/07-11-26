#!/usr/bin/env python3
"""
Evaluator validation: run real pipeline on selected conversations and show
detailed per-metric evaluator decisions for human review.

Usage:
    python scripts/validate_evaluator.py ADM_HIGHRANK_001
    python scripts/validate_evaluator.py ADM_HIGHRANK_001 ADM_LOWRANK_001
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

if not os.getenv("GROQ_API_KEY"):
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("GROQ_API_KEY="):
                os.environ["GROQ_API_KEY"] = line.split("=", 1)[1].strip()
                break

from src.conversation.state import ConversationState
from src.pipeline import PipelineOrchestrator
from scripts.evaluate import (
    evaluate_turn,
    load_conversation,
    check_field,
    CheckResult,
)


def run_pipeline_on_conv(conv: dict) -> list[dict]:
    """Run real pipeline on each turn, maintaining conversation state."""
    from scripts.benchmark import _pipeline_to_dict

    pipeline = PipelineOrchestrator()
    state = ConversationState(session_id=f"validate_{conv['id']}")
    results = []
    for turn in conv.get("turns", []):
        text = turn.get("student", "")
        try:
            result = pipeline.run(text, state=state)
            results.append(_pipeline_to_dict(result))
        except Exception as e:
            print(f"    [ERROR] {e}")
            results.append(None)
    return results


def deep_get(d: dict, path: str) -> Any:
    """Get a nested field from a dict using dot notation."""
    keys = path.split(".")
    val = d
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return None
    return val


def validate_turn(
    turn_idx: int,
    turn: dict,
    pipeline_result: dict | None,
) -> dict[str, Any]:
    """Run evaluator checks and return detailed per-metric report."""
    expected = turn.get("expected", {})
    report: dict[str, Any] = {"turn": turn_idx, "student": turn.get("student", "")}

    if pipeline_result is None:
        report["error"] = "No pipeline result"
        return report

    metrics = []

    # ── Understanding ──
    u_exp = expected.get("understanding", {})

    # Intent
    intent_exp = u_exp.get("intent")
    if intent_exp:
        intent_act = deep_get(pipeline_result, "understanding.intent.primary")
        metrics.append({
            "stage": "understanding",
            "metric": "intent.primary",
            "expected": intent_exp,
            "actual": intent_act,
            "pass": intent_exp == intent_act,
            "judge": "",  # fill in manually
        })

    # Facts
    for field, exp_val in u_exp.get("facts", {}).items():
        if exp_val is not None:
            act_val = deep_get(pipeline_result, f"understanding.facts.{field}")
            metrics.append({
                "stage": "understanding",
                "metric": f"facts.{field}",
                "expected": exp_val,
                "actual": act_val,
                "pass": exp_val == act_val,
                "judge": "",
            })

    # Missing
    missing_exp = u_exp.get("missing", [])
    if missing_exp is not None:
        actual_missing = pipeline_result.get("understanding", {}).get("missing", [])
        exp_set = set(missing_exp)
        act_set = set(actual_missing)
        overlap = len(exp_set & act_set)
        max_len = max(len(exp_set), len(act_set))
        evaluator_pass = max_len > 0 and overlap / max_len >= 0.5
        metrics.append({
            "stage": "understanding",
            "metric": "missing",
            "expected": sorted(missing_exp),
            "actual": sorted(actual_missing),
            "pass": evaluator_pass,
            "detail": f"overlap={overlap}/{max_len}",
            "judge": "",
        })

    # ── Reasoning ──
    r_exp = expected.get("reasoning", {})
    r_act = pipeline_result.get("reasoning", {})

    if r_exp.get("stage"):
        metrics.append({
            "stage": "reasoning",
            "metric": "stage",
            "expected": r_exp["stage"],
            "actual": r_act.get("stage", ""),
            "pass": r_exp["stage"] == r_act.get("stage", ""),
            "judge": "",
        })

    if r_exp.get("profile_completeness") is not None:
        exp_pc = r_exp["profile_completeness"]
        act_pc = r_act.get("profile_completeness", -1)
        metrics.append({
            "stage": "reasoning",
            "metric": "profile_completeness",
            "expected": exp_pc,
            "actual": act_pc,
            "pass": abs(exp_pc - act_pc) <= 0.3,
            "detail": f"tol=0.3, diff={abs(exp_pc - act_pc):.2f}",
            "judge": "",
        })

    if r_exp.get("confidence"):
        metrics.append({
            "stage": "reasoning",
            "metric": "confidence",
            "expected": r_exp["confidence"],
            "actual": r_act.get("confidence", ""),
            "pass": r_exp["confidence"] == r_act.get("confidence", ""),
            "judge": "",
        })

    if r_exp.get("current_problem") is not None:
        metrics.append({
            "stage": "reasoning",
            "metric": "current_problem",
            "expected": r_exp["current_problem"],
            "actual": r_act.get("current_problem", ""),
            "pass": r_exp["current_problem"] == r_act.get("current_problem", ""),
            "judge": "",
        })

    # ── Brain ──
    b_exp = expected.get("brain", {})
    b_act = pipeline_result.get("brain", {})

    if b_exp.get("applicable") is not None:
        metrics.append({
            "stage": "brain",
            "metric": "applicable",
            "expected": b_exp["applicable"],
            "actual": b_act.get("applicable"),
            "pass": b_exp["applicable"] == b_act.get("applicable"),
            "judge": "",
        })

    if b_exp.get("eligible_branches") is not None:
        exp_br = set(b_exp["eligible_branches"])
        act_br = set(b_act.get("eligible_branches", []))
        overlap = len(exp_br & act_br)
        evaluator_pass = overlap >= len(exp_br) * 0.5 if len(exp_br) > 0 else len(act_br) == 0
        metrics.append({
            "stage": "brain",
            "metric": "eligible_branches",
            "expected": sorted(exp_br),
            "actual": sorted(act_br),
            "pass": evaluator_pass,
            "detail": f"overlap={overlap}/{len(exp_br)}",
            "judge": "",
        })

    # ── Decision ──
    d_exp = expected.get("decision", {})
    d_act = pipeline_result.get("decision", {})
    metrics.append({
        "stage": "decision",
        "metric": "action",
        "expected": d_exp.get("action", ""),
        "actual": d_act.get("action", ""),
        "pass": d_exp.get("action") == d_act.get("action", ""),
        "judge": "",
    })

    # ── Planner ──
    p_exp = expected.get("planner", {})
    p_act = pipeline_result.get("plan", {})
    exp_turns = p_exp.get("turns", [])
    act_turns = p_act.get("turns", []) if isinstance(p_act, dict) else []

    for i, exp_t in enumerate(exp_turns):
        if i >= len(act_turns):
            metrics.append({
                "stage": "planner",
                "metric": f"turn[{i}].action",
                "expected": exp_t.get("action"),
                "actual": None,
                "pass": False,
                "detail": "Missing turn",
                "judge": "",
            })
            continue

        act_t = act_turns[i]
        act_action = act_t.get("action", "")
        exp_action = exp_t.get("action", "")
        metrics.append({
            "stage": "planner",
            "metric": f"turn[{i}].action",
            "expected": exp_action,
            "actual": act_action,
            "pass": exp_action == act_action,
            "judge": "",
        })

        for s in exp_t.get("content_contains", []):
            act_content = act_t.get("content", "")
            found = s.lower() in act_content.lower()
            metrics.append({
                "stage": "planner",
                "metric": f"turn[{i}] content contains '{s}'",
                "expected": s,
                "actual": act_content[:100] if not found else "(present)",
                "pass": found,
                "judge": "",
            })

    # ── Must-not ──
    resp = pipeline_result.get("response", "")
    for v in turn.get("must_not", []):
        v_norm = v.lower().replace("_", " ")
        if v_norm in resp.lower().replace("_", " "):
            metrics.append({
                "stage": "must_not",
                "metric": f"violation: {v}",
                "expected": "absent",
                "actual": "PRESENT",
                "pass": False,
                "judge": "",
            })

    report["metrics"] = metrics
    passed = sum(1 for m in metrics if m["pass"])
    total = len(metrics)
    report["score"] = f"{passed}/{total}" if total else "N/A"
    return report


def print_report(report: dict) -> None:
    """Print a single turn's validation report."""
    print(f"\n  Turn {report['turn']+1}: \"{report['student'][:80]}\"")
    if "error" in report:
        print(f"    ERROR: {report['error']}")
        return
    print(f"    Score: {report['score']}")
    for m in report.get("metrics", []):
        icon = "+" if m["pass"] else "X"
        detail = f" ({m['detail']})" if m.get("detail") else ""
        judge = f"  JUDGE: {m['judge']}" if m.get("judge") else ""
        print(f"    [{icon}] {m['stage']:15s} {m['metric']:30s}  "
              f"expected={m['expected']!r:30s}  actual={m['actual']!r}{detail}{judge}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return

    for conv_id in args:
        print(f"\n{'='*70}")
        print(f"  {conv_id}")
        print(f"{'='*70}")

        # Load gold conversation
        conv = load_conversation(conv_id)

        # Run real pipeline
        print(f"  Running pipeline...", end=" ", flush=True)
        results = run_pipeline_on_conv(conv)
        print("done.")

        # Validate each turn
        for i, turn in enumerate(conv.get("turns", [])):
            pr = results[i] if i < len(results) else None
            report = validate_turn(i, turn, pr)
            print_report(report)

        print(f"\n  Overall: {sum(1 for r in [validate_turn(i, t, results[i] if i < len(results) else None) for i, t in enumerate(conv.get('turns', []))] for m in r.get('metrics', []) if m.get('pass'))} / "
              f"{sum(len(r.get('metrics', [])) for r in [validate_turn(i, t, results[i] if i < len(results) else None) for i, t in enumerate(conv.get('turns', []))])} evaluator checks passed")

        # Write full report to JSON
        reports = []
        for i, turn in enumerate(conv.get("turns", [])):
            pr = results[i] if i < len(results) else None
            reports.append(validate_turn(i, turn, pr))

        out_dir = Path("data/benchmark/validation")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{conv_id}.json"
        out_path.write_text(json.dumps(reports, indent=2))
        print(f"  Report written to {out_path}")


if __name__ == "__main__":
    main()
