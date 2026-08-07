"""Analyze Reasoning Engine behavior across all benchmarks.

Produces:
- Confusion matrix (predicted vs expected problem)
- Rule firing statistics (frequency, correctness per rule)
- Rule precedence analysis (which rules block others)
- Rule coverage report
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.conversation.state import ConversationState
from src.pipeline import PipelineOrchestrator
from src.validation import GroundTruth

BENCH_DIR = Path("data/benchmark/conversations")


def load_convs(limit=0):
    convs = []
    for path in sorted(BENCH_DIR.rglob("*.json")):
        convs.append(json.loads(path.read_text(encoding="utf-8")))
        if limit and len(convs) >= limit:
            break
    return convs


# ── Rule ordering (matches _trace_problem in reasoning/engine.py) ──────

RULE_ORDER = [
    "anxiety > 0.4",
    "confusion > 0.5",
    "frustration > 0.5",
    "intent == fee",
    "intent == admission",
    "intent == placement",
    "intent == hostel",
    "intent == scholarship",
    "intent == cutoff",
    "intent == department",
    "intent == counseling_info",
    "intent == transfer",
    "intent == sports/sports_quota",
    "intent == nri/nri_admission",
    "intent == management/management_quota",
    "intent == distance_ed/distance_education",
    "intent == grievance",
    "intent == lateral_entry",
    "intent == institution/hod",
    "intent == seats",
    "intent == repeat",
    "intent == loan",
    "intent == document",
    "intent == safety",
    "intent == career_confusion",
    "completeness < 0.3",
    "completeness < 0.6",
    "fallback",
]

RULE_TO_RESULT = {
    "anxiety > 0.4": "needs_reassurance",
    "confusion > 0.5": "needs_clarification",
    "frustration > 0.5": "needs_clarification",
    "intent == fee": "needs_fee_information",
    "intent == admission": "needs_admission_guidance",
    "intent == placement": "needs_placement_information",
    "intent == hostel": "needs_hostel_information",
    "intent == scholarship": "needs_scholarship_information",
    "intent == cutoff": "needs_cutoff_information",
    "intent == department": "needs_institution_info",
    "intent == counseling_info": "needs_personalized_guidance",
    "intent == transfer": "needs_transfer_information",
    "intent == sports/sports_quota": "needs_sports_quota_information",
    "intent == nri/nri_admission": "needs_nri_admission_information",
    "intent == management/management_quota": "needs_management_quota_information",
    "intent == distance_ed/distance_education": "needs_distance_education_information",
    "intent == grievance": "needs_grievance_resolution",
    "intent == lateral_entry": "needs_lateral_entry_information",
    "intent == institution/hod": "needs_institution_info",
    "intent == seats": "needs_seat_info",
    "intent == repeat": "needs_clarification",
    "intent == loan": "needs_loan_info",
    "intent == document": "needs_document_info",
    "intent == safety": "needs_safety_info",
    "intent == career_confusion": "needs_career_guidance",
    "completeness < 0.3": "needs_profile_initial",
    "completeness < 0.6": "needs_profile_completion",
    "fallback": "needs_personalized_guidance",
}

RULE_FAMILIES = {
    "signal": ["anxiety > 0.4", "confusion > 0.5", "frustration > 0.5"],
    "intent": [
        "intent == fee", "intent == admission", "intent == placement",
        "intent == hostel", "intent == scholarship", "intent == cutoff",
        "intent == department", "intent == counseling_info",
        "intent == transfer", "intent == sports/sports_quota",
        "intent == nri/nri_admission", "intent == management/management_quota",
        "intent == distance_ed/distance_education", "intent == grievance",
        "intent == lateral_entry", "intent == institution/hod",
        "intent == seats", "intent == repeat", "intent == loan",
        "intent == document", "intent == safety", "intent == career_confusion",
    ],
    "completeness": ["completeness < 0.3", "completeness < 0.6"],
    "fallback": ["fallback"],
}


def extract_expected(turn):
    exp = turn.get("expected", {})
    return {
        "intent": exp.get("understanding", {}).get("intent", ""),
        "problem": exp.get("reasoning", {}).get("current_problem", ""),
        "action": exp.get("decision", {}).get("action", ""),
    }


def main():
    limit = 0
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit") + 1
        if idx < len(sys.argv):
            limit = int(sys.argv[idx])

    convs = load_convs(limit)
    print(f"Loaded {len(convs)} benchmark conversations")

    pipeline = PipelineOrchestrator()

    # Data collectors
    confusion: Counter = Counter()
    actual_counts: Counter = Counter()
    expected_counts: Counter = Counter()
    rule_fire_counts: Counter = Counter()
    rule_correct_counts: Counter = Counter()
    rule_fire_totals: Counter = Counter()
    precedence_blocks: Counter = Counter()
    precedence_detail: list[dict] = []
    problem_vs_intent: Counter = Counter()
    total_turns = 0

    for ci, conv in enumerate(convs):
        conv_id = conv.get("id", f"conv_{ci}")
        turns = conv.get("turns", [])
        gt_facts = conv.get("ground_truth", {})
        state = ConversationState(
            session_id=f"ra-{conv_id}",
            profile={k: v for k, v in gt_facts.items() if v is not None},
        )

        for ti, turn in enumerate(turns):
            query = turn.get("student", "")
            expected = extract_expected(turn)
            result = pipeline.run(query, state=state, debug=True)
            total_turns += 1

            # Get actual pipeline output
            r = result.reasoning
            actual_problem = getattr(r, "current_problem", "?") if r else "?"
            actual_intent = (result.understanding.intent.primary
                             if result.understanding and hasattr(result.understanding, "intent") else "?")

            # Get diagnostic traces
            rdiag = None
            if hasattr(result.reasoning, "metadata"):
                rdiag = result.reasoning.metadata.get("reasoning_diagnostics")
            if rdiag:
                traces = getattr(rdiag, "problems_traced", [])
            else:
                traces = []

            # ── Confusion matrix ──
            key = (actual_problem, expected["problem"])
            confusion[key] += 1
            actual_counts[actual_problem] += 1
            expected_counts[expected["problem"]] += 1

            # Problem vs intent relationship
            problem_vs_intent[(actual_intent, actual_problem)] += 1

            # ── Rule firing stats ──
            # Find which rule matched (the first one with matched=True)
            matched_rule = None
            matched_idx = -1
            for i, t in enumerate(traces):
                if t.matched:
                    matched_rule = t.condition
                    matched_idx = i
                    break

            if matched_rule:
                # Normalize condition to our canonical names
                canonical = matched_rule
                rule_fire_totals[canonical] += 1
                # Check correctness
                expected_result = RULE_TO_RESULT.get(canonical, "")
                if expected_result and expected_result == expected["problem"]:
                    rule_correct_counts[canonical] += 1

                # Track which rules were evaluated before the winner
                preceding_conditions = [t.condition for t in traces[:matched_idx] if not t.matched]
                if preceding_conditions:
                    precedence_detail.append({
                        "winner": canonical,
                        "winner_result": RULE_TO_RESULT.get(canonical, ""),
                        "expected": expected["problem"],
                        "preceding": preceding_conditions[-3:],  # last 3 before winner
                    })
                # Count this rule as having been evaluated and not winning
                for pc in preceding_conditions:
                    canonical_pc = pc
                    if canonical_pc != canonical:
                        precedence_blocks[(canonical_pc, canonical)] += 1

    # ── Report ────────────────────────────────────────────────────────

    print(f"\n{'=' * 60}")
    print(f"Reasoning Engine Analysis — {total_turns} turns, {len(convs)} conversations")
    print(f"{'=' * 60}")

    # 1. Confusion Matrix
    print(f"\n{'=' * 60}")
    print("1. Confusion Matrix (Predicted Problem → Expected Problem)")
    print(f"{'=' * 60}")
    all_problems = sorted(set(k[0] for k in confusion) | set(k[1] for k in confusion))
    if all_problems:
        col_w = max(len(p) for p in all_problems) + 2
        header = f"{'':>{col_w}}"
        for exp_p in all_problems:
            header += f"  {exp_p:>{col_w}}"
        print(header)
        print("-" * len(header))
        for act_p in all_problems:
            row = f"{act_p:>{col_w}}"
            for exp_p in all_problems:
                val = confusion.get((act_p, exp_p), 0)
                row += f"  {val:>{col_w}d}"
            print(row)
        print()

    # Most common mismatches
    print("\nTop mismatches (predicted ≠ expected):")
    mismatches = [(k, v) for k, v in confusion.items() if k[0] != k[1]]
    mismatches.sort(key=lambda x: -x[1])
    for (act, exp), cnt in mismatches[:15]:
        print(f"  {act} → {exp}: {cnt}")

    # 2. Rule firing statistics
    print(f"\n{'=' * 60}")
    print("2. Rule Firing Statistics")
    print(f"{'=' * 60}")
    print(f"\n{'Rule':<45} {'Fired':>6} {'Correct':>8} {'Rate':>8}")
    print("-" * 70)
    for rule in RULE_ORDER:
        fired = rule_fire_totals.get(rule, 0)
        correct = rule_correct_counts.get(rule, 0)
        rate = f"{correct / fired * 100:.0f}%" if fired > 0 else "—"
        if fired > 0 or rule == "fallback":
            label = rule
            print(f"{label:<45} {fired:>6} {correct:>8} {rate:>8}")

    # By family
    print(f"\n  By family:")
    for family, rules in RULE_FAMILIES.items():
        total = sum(rule_fire_totals.get(r, 0) for r in rules)
        correct = sum(rule_correct_counts.get(r, 0) for r in rules)
        rate = f"{correct / total * 100:.0f}%" if total > 0 else "—"
        print(f"    {family:<15} {'─' if family == 'fallback' else f'{total:>4} fired, {correct:>4} correct, {rate}'}")

    # 3. Rule precedence
    print(f"\n{'=' * 60}")
    print("3. Rule Precedence (which rules block which)")
    print(f"{'=' * 60}")
    blockers = sorted(precedence_blocks.items(), key=lambda x: -x[1])
    if blockers:
        print(f"\n  Rule A blocks Rule B (A fires first, B never reached):")
        for (blocker, blocked), cnt in blockers[:15]:
            print(f"    {blocker:<40} blocks {blocked:<30} {cnt:>4}x")
    else:
        print("  No blocking data collected.")

    # 4. Problem ↔ Intent relationship
    print(f"\n{'=' * 60}")
    print("4. Problem ↔ Intent Relationship")
    print(f"{'=' * 60}")
    print(f"\n{'Intent':<25} {'Problem':<35} {'Count':>6}")
    print("-" * 70)
    for (intent, problem), cnt in sorted(problem_vs_intent.items(), key=lambda x: -x[1])[:20]:
        print(f"{intent:<25} {problem:<35} {cnt:>6}")

    # 5. Ontology coverage
    print(f"\n{'=' * 60}")
    print("5. Ontology Coverage — Problems Seen vs Benchmark Expected")
    print(f"{'=' * 60}")
    all_problems_set = sorted(set(list(actual_counts.keys()) + list(expected_counts.keys())))
    print(f"\n{'Problem':<40} {'Actual':>6} {'Expected':>8}")
    print("-" * 60)
    for p in all_problems_set:
        act = actual_counts.get(p, 0)
        exp = expected_counts.get(p, 0)
        if act > 0 or exp > 0:
            print(f"{p:<40} {act:>6} {exp:>8}")

    # 6. Summary
    print(f"\n{'=' * 60}")
    print("Key Takeaways")
    print(f"{'=' * 60}")

    # Benchmark problems never predicted
    never_predicted = [p for p in expected_counts if p not in actual_counts or actual_counts[p] == 0]
    if never_predicted:
        print(f"\n  Problems expected by benchmark but never predicted by engine:")
        for p in sorted(never_predicted, key=lambda x: -expected_counts[x]):
            print(f"    {p}: expected {expected_counts[p]}x, predicted 0x")

    # Predictions never expected
    never_expected = [p for p in actual_counts if p not in expected_counts or expected_counts[p] == 0]
    if never_expected:
        print(f"\n  Problems predicted by engine but never expected by benchmark:")
        for p in sorted(never_expected, key=lambda x: -actual_counts[x]):
            print(f"    {p}: predicted {actual_counts[p]}x, expected 0x")

    # Rules with worst correctness
    low_correct = [
        (r, rule_fire_totals.get(r, 0), rule_correct_counts.get(r, 0))
        for r in RULE_ORDER
        if rule_fire_totals.get(r, 0) > 0
    ]
    low_correct.sort(key=lambda x: x[2] / x[1] if x[1] > 0 else 1)
    worst = low_correct[:5]
    if worst:
        print(f"\n  Lowest-accuracy rules (most likely to be wrong when they fire):")
        for rule, fired, correct in worst:
            rate = correct / fired * 100 if fired > 0 else 0
            print(f"    {rule:<45} {correct}/{fired} = {rate:.0f}%")

    print()


if __name__ == "__main__":
    main()
