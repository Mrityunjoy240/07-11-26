"""Deep reasoning analysis with canonical ontology mapping and transition matrices."""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.conversation.state import ConversationState
from src.pipeline import PipelineOrchestrator

BENCH_DIR = Path("data/benchmark/conversations")

# ── Canonical ontology ─────────────────────────────────────────────────
# Map benchmark problem labels → engine problem labels (or None = no direct match)
BENCH_TO_CANON = {
    # Pure naming mismatches
    "needs_hostel_info": "needs_hostel_information",
    "needs_placement_data": "needs_placement_information",
    "has_transfer_query": "needs_transfer_information",
    "needs_fee_details": "needs_fee_information",
    # Semantic overlaps
    "expressing_anxiety": "needs_reassurance",
    # Broad inquiries → fallback
    "general_inquiry": "needs_personalized_guidance",
    "comparing_options": "needs_personalized_guidance",
    # "has_*" patterns → use meaningful engine equivalents when they exist
    "has_grievance": "needs_grievance_resolution",
    "has_management_query": "needs_management_quota_information",
    # These are legitimate differences — no direct alias, flagged as "no-match"
}

# Engine labels that map to different benchmark expectations for evaluation
# (engine ontology is richer — we alias for benchmark comparison, not for routing)
BENCHMARK_ALIAS = {
    "needs_scholarship_information": "needs_fee_information",
    "needs_sports_quota_information": "needs_admission_guidance",
    "needs_distance_education_information": "needs_admission_guidance",
    "needs_cutoff_information": "needs_admission_guidance",
}

# Engine labels that have no benchmark equivalent (pipeline-only problems)
ENGINE_ONLY_LABELS = {
    "needs_scholarship_information",
    "needs_sports_quota_information",
    "needs_career_guidance",
    "needs_institution_info",
    "needs_seat_info",
    "needs_safety_info",
    "needs_loan_info",
    "needs_nri_admission_information",
    "needs_document_info",
    "needs_clarification",
    "needs_distance_education_information",
    "needs_cutoff_information",
}

# Intent → Expected Problem (benchmark's implicit policy, from analyzing benchmark data)
# These are what the benchmark expects for each intent (top expected per intent)
INTENT_TO_EXPECTED = {
    "admission": ["needs_profile_completion", "needs_admission_guidance"],
    "fee": ["needs_fee_information", "needs_scholarship_information"],
    "hostel": ["needs_hostel_info", "needs_hostel_information"],
    "placement": ["needs_placement_data", "needs_placement_information"],
    "scholarship": ["needs_fee_information", "comparing_options", "general_inquiry"],
    "cutoff": ["needs_cutoff_information", "needs_admission_guidance"],
    "transfer": ["has_transfer_query", "needs_transfer_information"],
    "sports_quota": ["needs_admission_guidance"],
    "management_quota": ["has_management_query"],
    "grievance": ["has_grievance"],
    "department": ["needs_institution_info"],
    "institution": ["needs_admission_guidance"],
    "distance_education": ["needs_admission_guidance"],
    "nri_admission": ["needs_admission_guidance"],
    "counseling_info": ["needs_personalized_guidance"],
    "loan": ["needs_loan_info"],
    "document": ["needs_document_info"],
    "safety": ["needs_safety_info"],
    "career_confusion": ["needs_career_guidance"],
    "seats": ["needs_seat_info"],
    "repeat": ["needs_clarification"],
}

# ── Helpers ─────────────────────────────────────────────────────────────

def load_convs(limit=0):
    convs = []
    for path in sorted(BENCH_DIR.rglob("*.json")):
        convs.append(json.loads(path.read_text(encoding="utf-8")))
        if limit and len(convs) >= limit:
            break
    return convs


def extract_expected(turn):
    exp = turn.get("expected", {})
    return {
        "intent": exp.get("understanding", {}).get("intent", ""),
        "problem": exp.get("reasoning", {}).get("current_problem", ""),
        "action": exp.get("decision", {}).get("action", ""),
    }


def canonical(expected: str) -> str:
    """Normalize benchmark problem label to engine ontology."""
    if expected in BENCH_TO_CANON:
        return BENCH_TO_CANON[expected]
    # For labels already matching engine ontology, return as-is
    if expected.startswith("needs_"):
        return expected
    # For other labels with no alias, return original (will be flagged)
    return expected


def fmt_rate(num, den):
    if den == 0:
        return "—"
    return f"{num}/{den} = {num/den*100:.0f}%"


def main():
    limit = 0
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit") + 1
        if idx < len(sys.argv):
            limit = int(sys.argv[idx])

    convs = load_convs(limit)
    print(f"Loaded {len(convs)} benchmark conversations\n")

    pipeline = PipelineOrchestrator()

    # Collectors
    intent_expected = Counter()
    intent_predicted = Counter()
    intent_expected_problem = Counter()  # (intent, expected_problem_canonical)
    intent_transition = Counter()  # (intent, predicted, expected_canonical)
    raw_confusion = Counter()  # (predicted, expected_raw)
    canon_confusion = Counter()  # (predicted, expected_canonical)
    predicted_counts = Counter()
    expected_counts = Counter()
    total_turns = 0
    no_alias_expected = Counter()
    engine_only_matches = Counter()
    turns_data = []

    for ci, conv in enumerate(convs):
        conv_id = conv.get("id", f"conv_{ci}")
        turns = conv.get("turns", [])
        gt_facts = conv.get("ground_truth", {})
        state = ConversationState(
            session_id=f"deep-{conv_id}",
            profile={},  # Start empty — facts accumulate via pipeline profile merge
        )

        for ti, turn in enumerate(turns):
            query = turn.get("student", "")
            expected = extract_expected(turn)
            result = pipeline.run(query, state=state, debug=True)
            total_turns += 1

            intent = (result.understanding.intent.primary
                      if result.understanding and hasattr(result.understanding, "intent") else "?")
            predicted = (result.reasoning.current_problem
                         if result.reasoning and hasattr(result.reasoning, "current_problem") else "?")
            exp_raw = expected["problem"]
            exp_canon = canonical(exp_raw)

            # Track whether the bench problem matched an engine label
            if exp_canon == exp_raw and exp_raw.startswith("needs_") is False:
                no_alias_expected[exp_raw] += 1
            if predicted in ENGINE_ONLY_LABELS:
                engine_only_matches[predicted] += 1

            raw_confusion[(predicted, exp_raw)] += 1
            aliased_pred = BENCHMARK_ALIAS.get(predicted, predicted)
            canon_confusion[(aliased_pred, exp_canon)] += 1
            predicted_counts[predicted] += 1
            expected_counts[exp_canon] += 1
            intent_expected[(intent, exp_canon)] += 1
            intent_predicted[(intent, aliased_pred)] += 1
            intent_expected_problem[(intent, exp_canon)] += 1
            intent_transition[(intent, aliased_pred, exp_canon)] += 1

            rdiag = None
            if hasattr(result.reasoning, "metadata"):
                rdiag = result.reasoning.metadata.get("reasoning_diagnostics")
            rdiag_traces = getattr(rdiag, "problems_traced", []) if rdiag else []

            turns_data.append({
                "conv": conv_id,
                "turn": ti,
                "intent": intent,
                "predicted": predicted,
                "aliased_pred": aliased_pred,
                "expected_raw": exp_raw,
                "expected_canon": exp_canon,
                "matched": aliased_pred == exp_canon,
                "traces": [{
                    "condition": t.condition,
                    "matched": t.matched,
                    "result": t.result,
                } for t in rdiag_traces],
            })

    # ── Report ────────────────────────────────────────────────────────

    print("=" * 60)
    print("REASONING DEEP ANALYSIS")
    print("=" * 60)

    # 1. Ontology normalization impact
    raw_matched = sum(1 for t in turns_data if t["predicted"] == t["expected_raw"])
    canon_matched = sum(1 for t in turns_data if t["aliased_pred"] == t["expected_canon"])
    print(f"\n{'─' * 60}")
    print("1. Ontology Normalization Impact")
    print(f"{'─' * 60}")
    print(f"\n  Raw accuracy (engine vs bench label):  {fmt_rate(raw_matched, total_turns)}")
    print(f"  Canonical accuracy (after aliasing):  {fmt_rate(canon_matched, total_turns)}")
    print(f"  Improvement from aliasing:            +{canon_matched - raw_matched} turns")

    if no_alias_expected:
        print(f"\n  Benchmark labels with no engine alias:")
        for label, cnt in no_alias_expected.most_common():
            print(f"    {label}: {cnt}x")

    # 2. Canonical confusion matrix (top entries)
    print(f"\n{'─' * 60}")
    print("2. Canonical Confusion Matrix (predicted → normalized expected)")
    print(f"{'─' * 60}")
    mismatches = [(k, v) for k, v in canon_confusion.items() if k[0] != k[1]]
    mismatches.sort(key=lambda x: -x[1])
    print(f"\n  After normalization, top mismatches (n={sum(v for _, v in mismatches)}):")
    for (pred, exp), cnt in mismatches[:20]:
        correct = fmt_rate(0, cnt)  # placeholder
        print(f"    {pred:<40} → {exp:<35} {cnt:>3}x")

    canon_matched_total = sum(v for (p, e), v in canon_confusion.items() if p == e)
    canon_mismatch_total = sum(v for (p, e), v in canon_confusion.items() if p != e)
    print(f"\n    Canonical matches:   {canon_matched_total}")
    print(f"    Canonical mismatches: {canon_mismatch_total}")
    print(f"    Normalized accuracy:  {canon_matched_total}/{total_turns} = {canon_matched_total/total_turns*100:.0f}%")

    # 3. Intent → Expected Problem matrix (benchmark policy)
    print(f"\n{'─' * 60}")
    print("3. Intent → Expected Problem (benchmark's implicit policy)")
    print(f"{'─' * 60}")
    ie_rows = []
    for (intent, exp_prob), cnt in sorted(intent_expected_problem.items(), key=lambda x: -x[1]):
        if cnt >= 2:
            ie_rows.append((intent, exp_prob, cnt))
    print(f"\n{'Intent':<25} {'Expected Problem':<40} {'Count':>5}")
    print("-" * 72)
    for intent, exp_prob, cnt in ie_rows:
        print(f"{intent:<25} {exp_prob:<40} {cnt:>5}")

    # 4. Intent → Predicted → Expected transition matrix
    print(f"\n{'─' * 60}")
    print("4. Intent → Predicted Problem → Expected Problem (transition matrix)")
    print(f"{'─' * 60}")
    transitions = [(k, v) for k, v in intent_transition.items()]
    transitions.sort(key=lambda x: -x[1])
    print(f"\n{'Intent':<25} {'Predicted':<35} {'Expected':<35} {'Count':>5} {'Acc':>5}")
    print("-" * 110)
    for (intent, pred, exp), cnt in transitions[:25]:
        correct = "✓" if pred == exp else "✗"
        print(f"{intent:<25} {pred:<35} {exp:<35} {cnt:>5}  {correct}")

    # 5. Signal rule investigation
    print(f"\n{'─' * 60}")
    print("5. Signal Rule Analysis (why do anxiety/confusion/frustration rules never fire?)")
    print(f"{'─' * 60}")
    # Find turns where signal rules would be applicable
    signal_turns = []
    for t in turns_data:
        for trace in t["traces"]:
            if any(s in trace["condition"] for s in ["anxiety", "confusion", "frustration"]):
                signal_turns.append(t)
                break
    print(f"\n  Turns with signal rules evaluated: {len(signal_turns)}")
    # Check if signal rules matched
    signal_wins = [t for t in signal_turns if t["predicted"] in ("needs_reassurance", "needs_clarification")]
    print(f"  Signal rules won: {len(signal_wins)}")
    # For each signal turn, check if a preceding intent rule blocked it
    intent_blocked = 0
    for t in signal_turns:
        for trace in t["traces"]:
            if "intent" in trace["condition"] and trace["matched"]:
                intent_blocked += 1
                break
    print(f"  Intent rule fired first (blocking signal): {intent_blocked}/{len(signal_turns)}" if signal_turns else "  No signal turns found")
    # Show concretely: anxiety turns that got intent-routed
    anxiety_turns = [t for t in turns_data if any("anxiety" in tr["condition"] for tr in t["traces"])]
    print(f"\n  Turns where anxiety rule was checked: {len(anxiety_turns)}")
    if anxiety_turns:
        print(f"  What those turns actually predicted instead of reassurance:")
        for pred in sorted(set(t["predicted"] for t in anxiety_turns)):
            cnt = sum(1 for t in anxiety_turns if t["predicted"] == pred)
            print(f"    {pred}: {cnt}x")

    # 6. Top incorrect transitions (highest-impact fixes)
    print(f"\n{'─' * 60}")
    print("6. Top Incorrect Transitions — Impact-ordered fix candidates")
    print(f"{'─' * 60}")
    incorrect = [(k, v) for k, v in intent_transition.items() if k[1] != k[2]]
    incorrect.sort(key=lambda x: -x[1])
    print(f"\n{'Intent':<20} {'Predicted':<35} {'Expected':<35} {'Count':>5}")
    print("-" * 100)
    for (intent, pred, exp), cnt in incorrect[:15]:
        # Suggest fix
        if intent in INTENT_TO_EXPECTED and exp in INTENT_TO_EXPECTED[intent]:
            fix = "NEEDS: forward intent→expected directly"
        elif pred in ENGINE_ONLY_LABELS:
            fix = "UNUSED: predicted label not in benchmark ontology"
        elif exp in BENCH_TO_CANON:
            fix = "ALIAS: alias in canonical map (should auto-fix)"
        else:
            fix = "RULE: different expected problem for this intent"
        print(f"{intent:<20} {pred:<35} {exp:<35} {cnt:>5}  # {fix}")

    # 7. Summary
    print(f"\n{'─' * 60}")
    print("SUMMARY")
    print(f"{'─' * 60}")
    print(f"""
  Raw accuracy:        {fmt_rate(raw_matched, total_turns)}
  Canonical accuracy:  {fmt_rate(canon_matched, total_turns)}
  Ontology gap:        {raw_matched}/{total_turns} → {canon_matched}/{total_turns}
  Remaining errors:    {total_turns - canon_matched} turns

  Signal rules fired:  {len(signal_wins)}/{len(signal_turns)} turns
  Intent blocks signal: {intent_blocked} turns

  Top 3 fixes by impact:
""")
    if incorrect:
        for (intent, pred, exp), cnt in incorrect[:3]:
            pct = cnt / total_turns * 100
            print(f"    {cnt:>3}x ({pct:.0f}%)  {intent}: {pred} → {exp}")
    print()


if __name__ == "__main__":
    main()
