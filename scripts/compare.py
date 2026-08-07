#!/usr/bin/env python3
"""
Three-way comparison: Old pipeline vs New pipeline vs Expected.

Shows all three side by side for a given conversation so you can
visually spot where the new pipeline differs from the old one and
whether either matches the expected ground truth.

Usage:
    python compare.py ADM_LOWRANK_001
    python compare.py data/benchmark/v0.1/
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.evaluate import (
    CheckResult,
    TurnResult,
    StageResult,
    evaluate_turn,
    load_conversation,
    load_all,
    mock_pipeline_result,
    print_result,
)


# ── Import old pipeline lazily ──────────────────────────────────────────

_OLD_PIPELINE_CACHE: dict[str, dict] | None = None


def _run_old_pipeline(student_text: str) -> dict:
    """Run the legacy GroqService pipeline and return its result dict."""
    global _OLD_PIPELINE_CACHE
    try:
        from src.dual.runner import run_dual
        from src.config.settings import get_settings
        from src.pipeline import run_pipeline

        settings = get_settings()
        old_mode = settings.get("pipeline_mode", "legacy")
        settings["pipeline_mode"] = "legacy"
        # Import legacy
        from src.llm.groq import GroqService
        service = GroqService()
        result = service.process(student_text)
        settings["pipeline_mode"] = old_mode
        return {
            "understanding": getattr(result, "understanding", {}),
            "reasoning": getattr(result, "reasoning", {}),
            "brain": getattr(result, "brain", {}),
            "decision": getattr(result, "decision", {}),
            "plan": getattr(result, "plan", {}),
            "response": getattr(result, "response", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def _run_new_pipeline(student_text: str) -> dict:
    """Run the new pipeline and return its result dict."""
    try:
        from src.pipeline import run_pipeline
        from src.pipeline.types import PipelineState

        state = PipelineState()
        result = run_pipeline(student_text, state)
        return {
            "understanding": getattr(result, "understanding", {}),
            "reasoning": getattr(result, "reasoning", {}),
            "brain": getattr(result, "brain", {}),
            "decision": getattr(result, "decision", {}),
            "plan": getattr(result, "plan", {}),
            "response": getattr(result, "response", ""),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Formatter ───────────────────────────────────────────────────────────

def _truncate(val: Any, width: int = 60) -> str:
    s = json.dumps(val, indent=None, default=str) if not isinstance(val, str) else val
    if len(s) > width:
        return s[:width - 3] + "..."
    return s


def _render_stage_comparison(conv: dict, results: list[dict] | None, label: str) -> None:
    """Render old vs new side-by-side comparison."""
    if results is None:
        print(f"  ⚠ {label}: no results")
        return

    has_error = any("error" in r for r in results)
    if has_error:
        for r in results:
            err = r.get("error")
            if err:
                print(f"  ✗ {label}: {err}")
        return

    for i, turn in enumerate(conv.get("turns", [])):
        pr = results[i] if i < len(results) else None
        if pr is None:
            print(f"  Turn {i + 1}: no result")
            continue

        exp = turn.get("expected", {})
        print(f"\n  ── Turn {i + 1}: {turn.get('student', '')[:50]} ──")

        stages = ["understanding", "reasoning", "brain", "decision", "planner"]
        for stage in stages:
            exp_s = exp.get(stage, {})
            act_s = pr.get(stage, {})
            if not exp_s and not act_s:
                continue
            label_s = stage.upper()
            exp_str = _truncate(exp_s, 50)
            act_str = _truncate(act_s, 50)
            match = "✓" if exp_str == act_str else "✗"
            print(f"    {match} {label_s:15s} Expected: {exp_str}")
            print(f"      {'':15s} {label:15s} {act_str}")

        # Response comparison
        exp_response = turn.get("response", "")
        act_response = pr.get("response", "")
        if exp_response or act_response:
            match = "✓" if exp_response == act_response else "✗"
            resp_str = _truncate(act_response, 50)
            print(f"    {match} {'RESPONSE':15s} Expected: {_truncate(exp_response, 50)}")
            print(f"      {'':15s} {label:15s} {resp_str}")

        # Must not
        must_not_items = turn.get("must_not", [])
        if must_not_items:
            violations = [v for v in must_not_items if v.lower().replace("_", " ") in act_response.lower().replace("_", " ")]
            if violations:
                print(f"    ✗ {'MUST_NOT':15s} VIOLATED: {', '.join(violations)}")


def compare_conversation(conv: dict, pipeline_results: list[dict], label: str) -> None:
    """Evaluate and print comparison."""
    result = evaluate_conversation(conv, pipeline_results)
    print_result(result)


# ── Main ────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    target = args[0]
    is_directory = os.path.isdir(target)
    show_expected = "--expected" in args

    if is_directory:
        convs = load_all(target)
    else:
        convs = [load_conversation(target)]

    for conv in convs:
        conv_id = conv["id"]
        print(f"\n{'='*70}")
        print(f"  {conv_id}  (difficulty={conv.get('difficulty', '?')})")
        print(f"  Tags: {', '.join(conv.get('tags', []))}")
        print(f"{'='*70}")

        # Expected data (mock)
        expected_results = mock_pipeline_result(conv)
        print(f"\n  → Expected (ground truth)")
        compare_conversation(conv, expected_results, "EXPECTED")

        # Try new pipeline
        new_results: list[dict] = []
        for turn in conv.get("turns", []):
            new_results.append(_run_new_pipeline(turn.get("student", "")))
        print(f"  → New pipeline")
        compare_conversation(conv, new_results, "NEW")

        # Try old pipeline
        old_results: list[dict] = []
        for turn in conv.get("turns", []):
            old_results.append(_run_old_pipeline(turn.get("student", "")))
        print(f"  → Old pipeline (legacy)")
        compare_conversation(conv, old_results, "OLD")

    # Summary
    if len(convs) > 1:
        print(f"\n{'='*70}")
        print(f"  COMPARISON SUMMARY — {len(convs)} conversations")
        print(f"{'='*70}")
        # TODO: aggregate old vs new stats
        print()


if __name__ == "__main__":
    main()
