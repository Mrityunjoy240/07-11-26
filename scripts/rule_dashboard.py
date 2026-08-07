"""Rule-level precision/recall dashboard.

Runs all 65 benchmark conversations through the pipeline and reports
per-rule statistics: how often each rule fires, wins, and is correct
against the canonical (normalized) benchmark expectation.
"""

import json
from collections import defaultdict
from pathlib import Path

from src.pipeline import PipelineOrchestrator, ConversationState

BENCH_DIR = Path("data/benchmark/conversations")

BENCH_TO_CANON = {
    "needs_hostel_info": "needs_hostel_information",
    "needs_placement_data": "needs_placement_information",
    "has_transfer_query": "needs_transfer_information",
    "comparing_options": "needs_personalized_guidance",
    "general_inquiry": "needs_personalized_guidance",
    "needs_detailed_comparison": "needs_personalized_guidance",
    "needs_branch_recommendation": "needs_personalized_guidance",
    "needs_cutoff_analysis": "needs_cutoff_information",
    "needs_admission_process": "needs_admission_guidance",
    "fee_query": "needs_fee_information",
    "scholarship_query": "needs_scholarship_information",
    "rank_analysis": "needs_cutoff_information",
    "needs_college_list": "needs_admission_guidance",
    "needs_fee_details": "needs_fee_information",
    "expressing_anxiety": "needs_reassurance",
    "has_grievance": "needs_grievance_resolution",
    "has_management_query": "needs_management_quota_information",
}


def canonical(label: str) -> str:
    return BENCH_TO_CANON.get(label, label)


# Engine labels that map to different benchmark expectations for evaluation
BENCHMARK_ALIAS = {
    "needs_scholarship_information": "needs_fee_information",
    "needs_sports_quota_information": "needs_admission_guidance",
    "needs_distance_education_information": "needs_admission_guidance",
    "needs_cutoff_information": "needs_admission_guidance",
}


def run_dashboard():
    pipeline = PipelineOrchestrator()

    # Per-rule stats
    rule_stats = defaultdict(lambda: {
        "fired": 0, "won": 0, "correct": 0, "margins": [],
        "incorrect_to": defaultdict(int),
    })
    total_turns = 0
    unmatched = 0

    for fpath in sorted(BENCH_DIR.rglob("BENCH_*.json")):
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        conv_id = data.get("id", fpath.stem)
        turns = data.get("turns", [])
        if not turns:
            continue
        gt_facts = data.get("ground_truth", {})
        state_facts = {k: v for k, v in gt_facts.items() if v is not None}

        for turn in turns:
            query = turn.get("student", "")
            if not query:
                continue
            expected = turn.get("expected", {})
            gold_raw = expected.get("reasoning", {}).get("current_problem", "")
            gold = canonical(gold_raw)
            if not gold:
                continue

            state = ConversationState(session_id=f"dash-{conv_id}", profile=dict(state_facts))
            result = pipeline.run(query, state=state, debug=True)

            total_turns += 1

            diag = None
            if result.reasoning and result.reasoning.metadata:
                diag = result.reasoning.metadata.get("reasoning_diagnostics")

            pred = result.reasoning.current_problem if result.reasoning else ""
            aliased_pred = BENCHMARK_ALIAS.get(pred, pred)
            explanations = diag.explanations if diag else []
            margin = diag.margin if diag else 0.0

            if aliased_pred != gold:
                unmatched += 1

            for ex in explanations:
                rule_key = ex.rule_name
                rule_stats[rule_key]["fired"] += 1
                if ex.matched:
                    rule_stats[rule_key]["won"] += 1
                    if BENCHMARK_ALIAS.get(ex.result, ex.result) == gold:
                        rule_stats[rule_key]["correct"] += 1
                    else:
                        rule_stats[rule_key]["incorrect_to"][gold] += 1
                    if margin > 0:
                        rule_stats[rule_key]["margins"].append(margin)

    # Print dashboard
    print("=" * 80)
    print("RULE PRECISION / RECALL DASHBOARD")
    print("=" * 80)
    print(f"\nTotal turns evaluated: {total_turns}")
    print(f"Unmatched predictions:  {unmatched} ({unmatched/total_turns:.1%})" if total_turns else "")
    print(f"Unique rules tracked:   {len(rule_stats)}")

    print(f"\n{'Rule':<55} {'Fired':>6} {'Won':>5} {'Correct':>8} {'Precision':>10} {'Avg Margin':>10}")
    print("-" * 96)

    sorted_rules = sorted(rule_stats.items(), key=lambda x: -x[1]["won"])
    for rule_name, stats in sorted_rules:
        won = stats["won"]
        fired = stats["fired"]
        correct = stats["correct"]
        precision = correct / won if won > 0 else 0.0
        avg_margin = sum(stats["margins"]) / len(stats["margins"]) if stats["margins"] else 0.0
        print(f"{rule_name:<55} {fired:>6} {won:>5} {correct:>8} {precision:>9.1%} {avg_margin:>9.3f}")

    # Top incorrect patterns per winning rule
    print(f"\n{'─' * 80}")
    print("TOP INCORRECT PATTERNS (per winning rule)")
    print(f"{'─' * 80}")
    for rule_name, stats in sorted_rules:
        if stats["incorrect_to"]:
            total_incorrect = sum(stats["incorrect_to"].values())
            tops = sorted(stats["incorrect_to"].items(), key=lambda x: -x[1])[:3]
            patterns = ", ".join(f"{e}({c})" for e, c in tops)
            print(f"  {rule_name:<50}: {patterns}  [{total_incorrect} total]")

    # Summary
    print(f"\n{'─' * 80}")
    print("SUMMARY")
    print(f"{'─' * 80}")
    all_correct = sum(s["correct"] for s in rule_stats.values())
    all_won = sum(s["won"] for s in rule_stats.values())
    all_fired = sum(s["fired"] for s in rule_stats.values())
    print(f"  Total rule evaluations: {all_fired}")
    print(f"  Total wins:             {all_won}")
    print(f"  Total correct:          {all_correct}")
    print(f"  Overall precision:      {all_correct/all_won:.1%}" if all_won > 0 else "  No wins recorded")


if __name__ == "__main__":
    run_dashboard()
