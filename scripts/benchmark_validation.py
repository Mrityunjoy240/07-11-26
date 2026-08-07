"""Run all benchmark conversations through validation, produce quality report.

Usage:
    python scripts/benchmark_validation.py
    python scripts/benchmark_validation.py --limit 5   (run only 5 conversations)
"""

import json
import sys
import os
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.conversation.state import ConversationState
from src.pipeline import PipelineOrchestrator
from src.validation import (
    EnvironmentInfo,
    GroundTruth,
    ValidationResult,
    attribute_blame,
    build_graph,
    run_all_validations,
)
from src.validation.stats import StatsCollector

BENCH_DIR = Path("data/benchmark/conversations")


# ── helpers ─────────────────────────────────────────────────────────────

def load_all_conversations(limit: int = 0) -> list[dict]:
    convs = []
    for path in sorted(BENCH_DIR.rglob("*.json")):
        convs.append(json.loads(path.read_text(encoding="utf-8")))
        if limit and len(convs) >= limit:
            break
    return convs


def extract_gt(turn: dict) -> GroundTruth:
    exp = turn.get("expected", {})
    return GroundTruth(
        expected_intent=exp.get("understanding", {}).get("intent", ""),
        expected_problem=exp.get("reasoning", {}).get("current_problem", ""),
        expected_action=exp.get("decision", {}).get("action", ""),
        expected_turns=len(exp.get("planner", {}).get("turns", [])),
    )


def actual_matches_gt(result, gt: GroundTruth) -> dict[str, bool]:
    u = getattr(result, "understanding", None)
    r = getattr(result, "reasoning", None)
    d = getattr(result, "decision", None)
    plan = getattr(result, "plan", None)
    return {
        "intent": u is not None and hasattr(u, "intent") and u.intent.primary == gt.expected_intent if gt.expected_intent else True,
        "problem": r is not None and hasattr(r, "current_problem") and r.current_problem == gt.expected_problem if gt.expected_problem else True,
        "action": d is not None and hasattr(d, "action") and d.action == gt.expected_action if gt.expected_action else True,
        "plan": plan is not None and len(plan.turns) == gt.expected_turns if gt.expected_turns > 0 else True,
    }


def _conf_label(conf: float) -> str:
    if conf >= 0.8:
        return "high"
    if conf >= 0.5:
        return "medium"
    return "low"


# ── report ──────────────────────────────────────────────────────────────

def _stage_table(title: str, rows: list[list], headers: list[str]) -> str:
    col_w = [max(len(str(r[i])) for r in rows + [headers]) for i in range(len(headers))]
    sep = "  ".join("-" * w for w in col_w)
    hdr = "  ".join(h.ljust(w) for h, w in zip(headers, col_w))
    body = "\n".join(
        "  ".join(str(r[i]).ljust(w) for i, w in enumerate(col_w))
        for r in rows
    )
    return f"\n{title}\n{'-' * 40}\n{hdr}\n{sep}\n{body}\n"


def print_report(
    results: list[dict],
    collector: StatsCollector,
):
    total_conv = len(set(r["conv_id"] for r in results))
    total_turns = len(results)

    print("=" * 60)
    print("Benchmark Validation Report")
    print("=" * 60)
    print(f"\nConversations: {total_conv}")
    print(f"Turns:         {total_turns}")

    # ── 1. Per-stage validation outcomes ──
    print("\n" + "=" * 60)
    print("1. Validation Outcomes per Stage")
    print("=" * 60)
    print(collector.report())

    # ── 2. Ground-truth match rate ──
    print("\n" + "=" * 60)
    print("2. Semantic Correctness (actual vs ground truth)")
    print("=" * 60)
    gt_total = Counter()
    gt_pass = Counter()
    for r in results:
        for field, ok in r.get("gt_match", {}).items():
            gt_total[field] += 1
            if ok:
                gt_pass[field] += 1
    rows = []
    for field in ["intent", "problem", "action", "plan"]:
        t = gt_total.get(field, 0)
        p = gt_pass.get(field, 0)
        rate = f"{p}/{t} ({p / t * 100:.0f}%)" if t else "N/A"
        rows.append([field, rate])
    print(_stage_table("Field  Correct/Total",
                       rows, ["Field", "Correct/Total"]))

    # ── 3. Validator quality (precision/recall for predicting benchmark failure) ──
    print("=" * 60)
    print("3. Validator Quality (treating FAIL as 'predicts benchmark error')")
    print("=" * 60)
    stages = ["understanding", "reasoning", "decision", "planner", "composer", "cross_stage"]
    qual_rows = []
    for stage in stages:
        tp = fp = fn = tn = 0
        for r in results:
            gt_match = r.get("gt_match", {})
            vr = r.get("validations", {}).get(stage)
            if vr is None:
                continue
            # Ground truth says "this turn failed"
            stage_failed = any(not v for v in gt_match.values())
            # Validator says "this stage failed"
            val_failed = vr.status == "FAIL" or vr.status == "WARNING"
            if stage_failed and val_failed:
                tp += 1
            elif not stage_failed and val_failed:
                fp += 1
            elif stage_failed and not val_failed:
                fn += 1
            else:
                tn += 1
            # If the stage has a semantic check, also check specific match
            if stage == "understanding":
                for c in vr.checks:
                    if c.check_type == "semantic":
                        if c.status in ("FAIL", "WARNING"):
                            fp_sem = 1
        total = tp + fp + fn + tn
        if total == 0:
            continue
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        qual_rows.append([
            stage,
            f"{tp}/{fp}/{fn}/{tn}",
            f"{precision:.0%}",
            f"{recall:.0%}",
            f"{f1:.0%}",
        ])
    print(_stage_table(
        "Stage  TP/FP/FN/TN  Prec  Recall  F1",
        qual_rows,
        ["Stage", "TP/FP/FN/TN", "Prec", "Recall", "F1"],
    ))

    # ── 4. Blame attribution accuracy ──
    print("=" * 60)
    print("4. Blame Attribution Accuracy")
    print("=" * 60)
    blame_correct = 0
    blame_total = 0
    blame_breakdown = Counter()
    for r in results:
        blame = r.get("blame")
        gt_match = r.get("gt_match", {})
        if not blame or not gt_match:
            continue
        # Determine true root cause from ground truth
        true_root = None
        if not gt_match.get("intent", True):
            true_root = "understanding"
        elif not gt_match.get("problem", True):
            true_root = "reasoning"
        elif not gt_match.get("action", True):
            true_root = "decision"
        elif not gt_match.get("plan", True):
            true_root = "planner"

        pred_root = blame.root_cause_stage
        blame_total += 1
        if true_root is None or pred_root == "none":
            # No actual failure — blame correctly says nothing
            if pred_root == "none":
                blame_correct += 1
                blame_breakdown["none"] += 1
        elif true_root == pred_root:
            blame_correct += 1
            blame_breakdown[true_root] += 1
        else:
            blame_breakdown[f"mismatch:{true_root}→{pred_root}"] += 1

    if blame_total:
        print(f"\n  Blame correct: {blame_correct}/{blame_total} ({blame_correct / blame_total * 100:.0f}%)")
        print(f"\n  Breakdown:")
        for key, count in blame_breakdown.most_common():
            print(f"    {key}: {count}")
    else:
        print("\n  No blame data available.")

    # ── 5. Top failure patterns ──
    print("\n" + "=" * 60)
    print("5. Failure Pattern Analysis")
    print("=" * 60)
    pattern_counts = Counter()
    for r in results:
        gt_match = r.get("gt_match", {})
        failures = [k for k, v in gt_match.items() if not v]
        if failures:
            pattern_counts["+".join(failures)] += 1
    if pattern_counts:
        print("\n  Most common failure patterns:")
        for pattern, count in pattern_counts.most_common(10):
            print(f"    {pattern}: {count}")
    else:
        print("\n  No ground-truth failures detected.")

    # ── 6. Validator false alarms (most common) ──
    print("\n" + "=" * 60)
    print("6. Validator False Alarms (FAIL/WARNING when GT says correct)")
    print("=" * 60)
    false_alarm_checks = Counter()
    for r in results:
        gt_match = r.get("gt_match", {})
        stage_ok = all(v for v in gt_match.values())
        if stage_ok:
            for stage, vr in r.get("validations", {}).items():
                for c in vr.checks:
                    if c.status in ("FAIL", "WARNING"):
                        false_alarm_checks[f"{stage}.{c.name} ({c.status})"] += 1
    if false_alarm_checks:
        print("\n  Top false alarm checks (GT correct but validator flagged):")
        for key, count in false_alarm_checks.most_common(10):
            print(f"    {key}: {count}")
    else:
        print("\n  No false alarms.")
    print()


# ── main ────────────────────────────────────────────────────────────────

def main():
    limit = 0
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit") + 1
        if idx < len(sys.argv):
            limit = int(sys.argv[idx])

    convs = load_all_conversations(limit)
    print(f"Loaded {len(convs)} benchmark conversations")

    env = EnvironmentInfo(llm_type="mock", tag="benchmark-run")
    collector = StatsCollector()
    all_results: list[dict] = []

    for ci, conv in enumerate(convs):
        conv_id = conv.get("id", f"conv_{ci}")
        turns_raw = conv.get("turns", [])
        ground_truth = conv.get("ground_truth", {})
        # Initialize state with ground-truth profile
        state = ConversationState(
            session_id=f"bench-{conv_id}",
            profile={k: v for k, v in ground_truth.items() if v is not None},
        )
        pipeline = PipelineOrchestrator()

        for ti, turn in enumerate(turns_raw):
            query = turn.get("student", "")
            gt = extract_gt(turn)
            result = pipeline.run(query, state=state, debug=True)

            # Extract diagnostics
            u_diag = None
            r_diag = None
            d_diag = None
            p_diag = None
            c_diag = None
            if hasattr(result.understanding, "metadata"):
                u_diag = result.understanding.metadata.get("intent_diagnostics")
            if hasattr(result.reasoning, "metadata"):
                r_diag = result.reasoning.metadata.get("reasoning_diagnostics")
            if hasattr(result.decision, "metadata"):
                d_diag = result.decision.metadata.get("decision_diagnostics")
            if result.plan and hasattr(result.plan, "metadata"):
                p_diag = result.plan.metadata.get("planner_diagnostics")
            c_diag = result.llm_diagnostics

            # Check ground-truth match
            gt_match = actual_matches_gt(result, gt)

            # Validate
            vrs = run_all_validations(
                intent_diag=u_diag,
                reasoning_diag=r_diag,
                decision_diag=d_diag,
                planner_diag=p_diag,
                composer_diag=c_diag,
                ground_truth=gt if not gt.is_empty() else None,
                env=env,
            )
            collector.record(vrs)

            # Blame
            graph = build_graph(u_diag, r_diag, d_diag, p_diag, gt if not gt.is_empty() else None)
            blame = attribute_blame(vrs, graph)

            all_results.append({
                "conv_id": conv_id,
                "turn": ti,
                "query": query,
                "gt": gt,
                "gt_match": gt_match,
                "validations": vrs,
                "blame": blame,
            })

            total_all = len(convs) * max(len(c.get("turns", [])) for c in convs) if convs else 1
            if (ci * max(len(c.get("turns", [])) for c in convs) + ti) % 10 == 0:
                pass  # Progress signal

    # Print the full report
    print_report(all_results, collector)

    # Save raw data
    out_dir = Path("scripts/output")
    out_dir.mkdir(exist_ok=True)
    serializable = []
    for r in all_results:
        serializable.append({
            "conv_id": r["conv_id"],
            "turn": r["turn"],
            "gt_match": r["gt_match"],
            "validations": {
                k: {"status": v.status, "confidence": round(v.confidence, 3),
                    "checks": [{"name": c.name, "status": c.status, "confidence": round(c.confidence, 3),
                                "check_type": c.check_type} for c in v.checks]}
                for k, v in r["validations"].items()
            },
            "blame": {
                "root_cause_stage": r["blame"].root_cause_stage,
                "cascade": r["blame"].cascade,
                "confidence": round(r["blame"].confidence, 3),
            } if r["blame"] else None,
        })
    (out_dir / "benchmark_validation_results.json").write_text(
        json.dumps(serializable, indent=2)
    )
    print(f"\nRaw data saved to scripts/output/benchmark_validation_results.json")


if __name__ == "__main__":
    main()
