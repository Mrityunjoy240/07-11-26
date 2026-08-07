"""Evaluate shadow-mode routing against annotated evaluation set + benchmark conversations.

Produces:
  1. Confidence threshold curve for routing decisions
  2. Per-signal eligibility breakdown
  3. Benchmark coverage analysis
  4. Routing decision log
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from src.reasoning.shadow_routing import ShadowSignalRouter, format_threshold_table


def load_merged_annotations() -> list[dict]:
    """Load the merged annotation file (81 entries)."""
    path = Path("data/evaluation/structured_signals/annotations_merged.jsonl")
    if not path.exists():
        print(f"ERROR: {path} not found. Run scripts/merge_annotations.py first.")
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").strip().split("\n")]


def load_mined_candidates() -> list[dict]:
    """Load mined candidates (130 raw entries, all turns)."""
    path = Path("data/evaluation/structured_signals/mined_candidates.jsonl")
    if not path.exists():
        print(f"ERROR: {path} not found.")
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").strip().split("\n")]


def load_benchmark_conversations() -> list[dict[str, str | int]]:
    """Load all 65 benchmark conversations and create turn-flat entries."""
    bench_dir = Path("data/benchmark/conversations")
    entries: list[dict] = []
    for fpath in sorted(bench_dir.rglob("*.json")):
        try:
            conv = json.loads(fpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        cid = conv.get("id", fpath.stem)
        for t_idx, turn in enumerate(conv.get("turns", [])):
            text = (turn.get("student") or "").strip()
            if not text:
                continue
            entries.append({
                "conversation_id": cid,
                "turn_id": t_idx,
                "text": text,
                "scope": "utterance_local",
                "detector_output": {},
            })
    return entries


def main() -> None:
    # ── Load data ───────────────────────────────────────────────────────
    annotations = load_merged_annotations()
    mined = load_mined_candidates()
    benchmark = load_benchmark_conversations()

    # ── Run detectors on benchmark turns (they lack detector_output) ───
    from src.understanding.signals.grievance import detect_grievance
    from src.understanding.signals.decision import detect_decision_intent
    from src.understanding.signals.emotion import detect_emotion

    for e in benchmark:
        text = e["text"]
        d_g = detect_grievance(text)
        d_d = detect_decision_intent(text)
        d_e = detect_emotion(text)
        e["detector_output"] = {
            "grievance": {"value": d_g.value if d_g else None, "confidence": d_g.confidence if d_g else 0.0},
            "decision": {"value": d_d.value if d_d else None, "confidence": d_d.confidence if d_d else 0.0},
            "emotion": {"value": d_e.value if d_e else None, "confidence": d_e.confidence if d_e else 0.0},
        }

    print("Starting shadow-mode evaluation...")
    print()

    # ── 1. Threshold sweep on annotated entries ─────────────────────────
    print("=" * 70)
    print("  1. Confidence threshold sweep — annotated entries (n=81)")
    print("=" * 70)
    print()

    router = ShadowSignalRouter(threshold=0.8)
    sweep = router.threshold_sweep(annotations)
    print(format_threshold_table(sweep))
    print()

    # ── 2. Per-signal eligibility breakdown at threshold=0.8 ──────────
    print("=" * 70)
    print("  2. Per-signal breakdown at threshold=0.8")
    print("=" * 70)
    print()

    router80 = ShadowSignalRouter(threshold=0.8)
    decisions80 = router80.evaluate_all(annotations)

    # Per-signal counts
    would_route_by_signal: Counter[str] = Counter()
    would_route_by_scope: Counter[str] = Counter()
    eligible_count = 0
    ineligible_count = 0
    for d in decisions80:
        if d.would_route:
            would_route_by_signal[d.signal_type or "unknown"] += 1
            would_route_by_scope[d.scope] += 1
        if d.eligible:
            eligible_count += 1
        else:
            ineligible_count += 1

    print(f"  Eligible (utterance_local or ambiguous): {eligible_count}")
    print(f"  Ineligible (conversation_context_required): {ineligible_count}")
    print(f"  Would route: {sum(would_route_by_signal.values())}")
    print(f"    By signal type: {dict(would_route_by_signal)}")
    print(f"    By scope: {dict(would_route_by_scope)}")
    print()

    # ── 3. Would-be-selected vs current reasoning path ─────────────────
    print("=" * 70)
    print("  3. Routing decision details at threshold=0.8")
    print("=" * 70)
    print()

    would_route_index = 0
    for i, d in enumerate(decisions80):
        if not d.would_route:
            continue
        would_route_index += 1
        e = annotations[i]
        labels = e.get("labels", {})
        sig_details = ", ".join(
            f"{s}={labels.get(s, {}).get('present', False)}"
            for s in ("emotion", "grievance", "decision")
        )
        print(f"  [{would_route_index}] {e['conversation_id']}:{e['turn_id']}")
        print(f"      signal: {d.signal_type} @ {d.confidence:.2f} | threshold: {d.threshold}")
        print(f"      scope: {d.scope} | eligible: {d.eligible}")
        print(f"      gold: {sig_details}")
        print(f"      text: {e['text'][:80]}...")
        print()

    # ── 4. Coverage on full mined corpus (182 turns, scope-aware) ──────
    print("=" * 70)
    print("  4. Full corpus coverage at threshold=0.8 (mined_candidates, n={})".format(len(mined)))
    print("=" * 70)
    print()

    router_mined = ShadowSignalRouter(threshold=0.8)
    mined_decisions = router_mined.evaluate_all(mined, label_key=None)

    mined_would_route = [d for d in mined_decisions if d.would_route]
    mined_by_sig: Counter[str] = Counter()
    mined_by_scope: Counter[str] = Counter()
    mined_ineligible_scope = 0
    for i, d in enumerate(mined_decisions):
        if d.would_route:
            mined_by_sig[d.signal_type or "unknown"] += 1
            mined_by_scope[d.scope] += 1
        if not d.eligible:
            mined_ineligible_scope += 1

    print(f"  Total mined entries: {len(mined)}")
    print(f"  Ineligible (conversation-context scope): {mined_ineligible_scope}")
    print(f"  Would route: {len(mined_would_route)} ({len(mined_would_route)/(len(mined)-mined_ineligible_scope)*100:.1f}% of eligible)")
    print(f"    By signal: emotion={mined_by_sig.get('emotion', 0)}, "
          f"grievance={mined_by_sig.get('grievance', 0)}")
    print(f"    By scope: {dict(mined_by_scope)}")
    print()

    # ── 5. Full benchmark raw coverage (182 turns, all utterance_local default) ──
    print("=" * 70)
    print("  5. Raw benchmark coverage at threshold=0.8 (all 182 turns)")
    print("=" * 70)
    print()

    router_bench = ShadowSignalRouter(threshold=0.8)
    bench_decisions = router_bench.evaluate_all(benchmark, label_key=None)

    bench_would_route = [d for d in bench_decisions if d.would_route]
    bench_by_sig: Counter[str] = Counter()
    for d in bench_would_route:
        bench_by_sig[d.signal_type or "unknown"] += 1

    print(f"  Total benchmark turns: {len(benchmark)}")
    print(f"  Would route: {len(bench_would_route)} ({len(bench_would_route)/len(benchmark)*100:.1f}%)")
    print(f"    emotion: {bench_by_sig.get('emotion', 0)}")
    print(f"    grievance: {bench_by_sig.get('grievance', 0)}")
    print(f"    (decision would be excluded even if detected)")
    print()

    # ── 6. Optimization: which threshold maximizes F1 on held-out data? ─
    print("=" * 70)
    print("  6. Optimization: which threshold maximizes F1 on held-out data?")
    print("=" * 70)
    print()

    best_threshold = max(sweep, key=lambda t: sweep[t]["f1"])
    best = sweep[best_threshold]
    print(f"  Best threshold by F1: {best_threshold:.1f} (F1={best['f1']:.1f}, "
          f"precision={best['precision']:.1f}%, recall={best['recall']:.1f}%)")
    print()

    # What changes between 0.7 and 0.8
    for a, b in [(0.7, 0.8), (0.8, 0.9)]:
        if a in sweep and b in sweep:
            sa, sb = sweep[a], sweep[b]
            print(f"  {a:.1f} → {b:.1f}: "
                  f"precision {sa['precision']}→{sb['precision']}, "
                  f"recall {sa['recall']}→{sb['recall']}, "
                  f"F1 {sa['f1']}→{sb['f1']}, "
                  f"would_route {sa['would_route_count']}→{sb['would_route_count']}")
    print()

    # ── 7. Decision recall impact of excluding decision signals ────────
    print("=" * 70)
    print("  7. Impact of excluding decision signals from routing")
    print("=" * 70)
    print()

    # Count how many gold decision signals would be missed
    gold_decision_turns = 0
    decision_only_turns = 0
    for e in annotations:
        labels = e.get("labels", {})
        if labels.get("decision", {}).get("present", False):
            gold_decision_turns += 1
            if not labels.get("emotion", {}).get("present", False) and \
               not labels.get("grievance", {}).get("present", False):
                decision_only_turns += 1

    print(f"  Gold decision signals in merged set: {gold_decision_turns}")
    print(f"  Decision-only turns (no emotion/grievance): {decision_only_turns}")
    print(f"  These would NOT trigger routing (correctly — 60% recall is unreliable)")
    print()

    # ── 8. Summary ──────────────────────────────────────────────────────
    print("=" * 70)
    print("  SHADOW MODE EVALUATION SUMMARY")
    print("=" * 70)
    print()
    print(f"  Router config: emotion+grievance only, utterance-local+ambiguous only")
    print(f"  Recommended threshold: {best_threshold:.1f} (F1={best['f1']:.1f})")
    print(f"  At threshold=0.8:")
    print(f"    would_route: {sweep[0.8]['would_route_count']}/{sweep[0.8]['total_eligible']} turns")
    print(f"    precision:   {sweep[0.8]['precision']}%")
    print(f"    recall:      {sweep[0.8]['recall']}%")
    print(f"    fp_rate:     {sweep[0.8]['fp_rate']}%")
    print()
    print(f"  Full corpus coverage (threshold=0.8, eligible scopes only):")
    print(f"    {len(mined_would_route)}/{len(mined)-mined_ineligible_scope} eligible turns would route")
    print(f"    emotion={mined_by_sig.get('emotion', 0)}, grievance={mined_by_sig.get('grievance', 0)}")
    print()
    print("  Routing policy:")
    print("    - Eligible: emotion ≥ threshold, grievance ≥ threshold")
    print("    - Ineligible: decision (any confidence), conversation_context_required")
    print("    - Production behavior: unchanged (shadow mode only)")
    print()


if __name__ == "__main__":
    main()
