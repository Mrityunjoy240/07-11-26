"""Classify every canonical mismatch into root cause categories.

Categories:
  ENGINE_BUG       → engine should produce a different label
  BENCH_ONTOLOGY   → benchmark has no equivalent for the engine label
  ENGINE_ONTOLOGY  → engine has no equivalent for the benchmark label
  BENCH_POLICY     → benchmark intentionally maps intent→different problem
  DEAD_RULE        → rule fires but never matches benchmark expectation
  ACCEPTABLE       → reasonable disagreement, both labels are valid
"""

import json
from collections import Counter, defaultdict
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

ENGINE_LABELS = {
    "needs_fee_information", "needs_admission_guidance", "needs_placement_information",
    "needs_hostel_information", "needs_scholarship_information", "needs_cutoff_information",
    "needs_institution_info", "needs_personalized_guidance", "needs_transfer_information",
    "needs_sports_quota_information", "needs_nri_admission_information",
    "needs_management_quota_information", "needs_distance_education_information",
    "needs_grievance_resolution", "needs_lateral_entry_information", "needs_seat_info",
    "needs_clarification", "needs_loan_info", "needs_document_info", "needs_safety_info",
    "needs_career_guidance", "needs_profile_initial", "needs_profile_completion",
    "needs_reassurance",
}

# Intent → Expected Problem (benchmark policy, derived from data analysis)
BENCHMARK_POLICY = {
    "scholarship": "needs_fee_information",
    "loan": "needs_fee_information",
    "sports_quota": "needs_admission_guidance",
    "sports": "needs_admission_guidance",
    "nri_admission": "needs_admission_guidance",
    "nri": "needs_admission_guidance",
    "distance_ed": "needs_admission_guidance",
    "distance_education": "needs_admission_guidance",
    "seats": "needs_admission_guidance",
    "safety": "needs_admission_guidance",
    "career_confusion": "needs_reassurance",
}


def canonical(label: str) -> str:
    return BENCH_TO_CANON.get(label, label)


def classify(engine_pred: str, gold: str, intent: str) -> str:
    """Classify a single mismatch."""
    if engine_pred == gold:
        return "CORRECT"

    # Engine label not in benchmark ontology at all
    if engine_pred not in BENCH_TO_CANON.values() and engine_pred not in BENCH_TO_CANON:
        if gold in BENCH_TO_CANON.values():
            return "BENCH_ONTOLOGY"

    # Gold label not in engine ontology
    if gold not in ENGINE_LABELS:
        return "ENGINE_ONTOLOGY"

    # Policy: benchmark consistently maps this intent to a different problem
    if intent in BENCHMARK_POLICY and gold == BENCHMARK_POLICY[intent]:
        return "BENCH_POLICY"

    # Admission + low completeness: engine bug (should produce profile_completion)
    if engine_pred == "needs_admission_guidance" and gold == "needs_profile_completion":
        return "ENGINE_BUG"

    # Completeness rules that disagree with benchmark
    if engine_pred in ("needs_profile_initial", "needs_profile_completion") and gold not in ("needs_profile_initial", "needs_profile_completion"):
        return "ENGINE_BUG"

    # Signal rules vs intent rules
    if engine_pred == "needs_reassurance" and gold != "needs_reassurance":
        return "ACCEPTABLE"

    # Default: acceptable disagreement or uncategorized
    return "ACCEPTABLE"


def run_classifier():
    pipeline = PipelineOrchestrator()

    categories = Counter()
    category_details = defaultdict(list)

    for fpath in sorted(BENCH_DIR.rglob("BENCH_*.json")):
        with open(fpath, encoding="utf-8") as f:
            data = json.load(f)
        turns = data.get("turns", [])
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

            state = ConversationState(session_id="cls", profile=dict(state_facts))
            result = pipeline.run(query, state=state, debug=True)
            pred = result.reasoning.current_problem if result.reasoning else ""
            intent = ""
            if result.understanding:
                intent = getattr(result.understanding, "intent", None)
                if intent:
                    intent = intent.primary

            cat = classify(pred, gold, intent)
            categories[cat] += 1
            category_details[cat].append({
                "file": fpath.name,
                "query": query[:60],
                "intent": intent,
                "pred": pred,
                "gold": gold,
            })

    # Print report
    print("=" * 80)
    print("MISMATCH CLASSIFIER REPORT")
    print("=" * 80)
    total = sum(categories.values())
    correct = categories.get("CORRECT", 0)
    print(f"\nTotal turns: {total}")
    print(f"Correct:      {correct} ({correct/total:.1%})")
    print(f"Mismatches:   {total - correct} ({(total-correct)/total:.1%})")
    print()

    CAT_LABELS = {
        "CORRECT": "Match",
        "BENCH_ONTOLOGY": "Benchmark ontology gap",
        "ENGINE_ONTOLOGY": "Engine ontology gap",
        "BENCH_POLICY": "Benchmark policy difference",
        "ENGINE_BUG": "Engine bug",
        "ACCEPTABLE": "Acceptable disagreement",
        "DEAD_RULE": "Dead rule",
    }
    ORDER = ["CORRECT", "BENCH_ONTOLOGY", "ENGINE_ONTOLOGY", "BENCH_POLICY", "ENGINE_BUG", "ACCEPTABLE"]

    print(f"{'Category':<35} {'Count':>6} {'% of Total':>11} {'% of Errors':>11}")
    print("-" * 65)
    for cat in ORDER:
        cnt = categories.get(cat, 0)
        if cnt == 0:
            continue
        pct_total = cnt / total * 100
        pct_errors = cnt / (total - correct) * 100 if (total - correct) > 0 else 0
        print(f"{CAT_LABELS.get(cat, cat):<35} {cnt:>6} {pct_total:>10.1f}% {pct_errors:>10.1f}%")

    # Show examples for each mismatch category
    print(f"\n{'─' * 80}")
    print("EXAMPLES PER CATEGORY")
    print(f"{'─' * 80}")
    for cat in ORDER:
        if cat == "CORRECT" or cat not in category_details:
            continue
        items = category_details[cat]
        print(f"\n  {CAT_LABELS.get(cat, cat)} ({len(items)} turns):")
        for item in items[:3]:
            print(f"    {item['file']:<30} intent={item['intent']:<15} pred={item['pred']:<35} gold={item['gold']}")
            print(f"    {'':>30} \"{item['query']}\"")

    # Show BENCH_POLICY patterns in detail
    if "BENCH_POLICY" in category_details:
        print(f"\n{'─' * 80}")
        print("BENCHMARK POLICY DIFFERENCES (intent → expected mapping)")
        print(f"{'─' * 80}")
        policy_details = category_details["BENCH_POLICY"]
        intent_counts = Counter(item["intent"] for item in policy_details)
        for intent, cnt in sorted(intent_counts.items(), key=lambda x: -x[1]):
            expected = BENCHMARK_POLICY.get(intent, "?")
            print(f"  {intent:<20} → {expected:<35} ({cnt} turns)")


if __name__ == "__main__":
    run_classifier()
