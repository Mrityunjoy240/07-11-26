"""Evaluate detector fixes against gold-labeled evaluation set.

Reads from annotations_merged.jsonl (Pass 1 + Pass 2 combined).
Runs CURRENT detectors on every entry, compares against gold labels.
Produces detailed metrics for routing decision analysis.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from src.understanding.signals.emotion import detect_emotion
from src.understanding.signals.decision import detect_decision_intent as detect_decision
from src.understanding.signals.grievance import detect_grievance


def main() -> None:
    # Try merged first, fall back to pass 1 only
    merged_path = Path("data/evaluation/structured_signals/annotations_merged.jsonl")
    pass1_path = Path("data/evaluation/structured_signals/annotations.jsonl")
    if merged_path.exists():
        inpath = merged_path
    else:
        inpath = pass1_path
    entries = [json.loads(l) for l in inpath.read_text(encoding="utf-8").strip().split("\n")]

    # Separate pass 1 and pass 2
    pass1_entries = [e for e in entries if e.get("annotation_pass") != 2]
    pass2_entries = [e for e in entries if e.get("annotation_pass") == 2]

    results: list[dict] = []
    hits_total = 0
    misses_total = 0
    fps_total = 0
    sig_hits: dict[str, int] = {"emotion": 0, "grievance": 0, "decision": 0}
    sig_misses: dict[str, int] = {"emotion": 0, "grievance": 0, "decision": 0}
    sig_fps: dict[str, int] = {"emotion": 0, "grievance": 0, "decision": 0}
    scope_hits: dict[str, int] = {}
    scope_total: dict[str, int] = {}

    for e in entries:
        gold = e["labels"]
        text = e["text"]

        # Run current detectors
        cur_emotion = detect_emotion(text)
        cur_grievance = detect_grievance(text)
        cur_decision = detect_decision(text)
        current = {
            "emotion": {"value": cur_emotion.value if cur_emotion else None, "confidence": cur_emotion.confidence if cur_emotion else 0.0},
            "grievance": {"value": cur_grievance.value if cur_grievance else None, "confidence": cur_grievance.confidence if cur_grievance else 0.0},
            "decision": {"value": cur_decision.value if cur_decision else None, "confidence": cur_decision.confidence if cur_decision else 0.0},
        }

        scope = e["scope"]
        if scope not in scope_hits:
            scope_hits[scope] = 0
            scope_total[scope] = 0

        row = {
            "conversation_id": e["conversation_id"],
            "turn_id": e["turn_id"],
            "text": text[:80],
            "scope": scope,
            "gold": {s: gold[s] for s in ["emotion", "grievance", "decision"]},
            "old_detector": e["detector_output"],
            "current_detector": current,
            "per_signal": {},
        }

        for sig in ["emotion", "grievance", "decision"]:
            human = gold[sig]["present"]
            cur = current[sig]["value"] is not None
            old = e["detector_output"][sig]["value"] is not None

            if human and cur:
                status = "hit"
                hits_total += 1
                sig_hits[sig] += 1
                scope_hits[scope] += 1
            elif human and not cur:
                status = "miss"
                misses_total += 1
                sig_misses[sig] += 1
            elif not human and cur:
                status = "fp"
                fps_total += 1
                sig_fps[sig] += 1
            else:
                status = "tn"

            if human:
                scope_total[scope] += 1

            improved = not human and old and not cur
            regressed = human and old and not cur
            row["per_signal"][sig] = {
                "status": status,
                "improved": improved,
                "regressed": regressed,
                "gold_subtype": gold[sig]["subtype"],
                "old_value": e["detector_output"][sig]["value"],
                "current_value": current[sig]["value"],
            }
        results.append(row)

    # ── Overall Summary ──
    print("=" * 70)
    print("  Detector Fix Evaluation — Merged Gold Labels (Pass 1 + Pass 2)")
    print("=" * 70)
    print()
    print(f"  Pass 1 entries: {len(pass1_entries)}  |  Pass 2 entries: {len(pass2_entries)}  |  Total: {len(entries)}")
    print()

    per_sig = ["emotion", "grievance", "decision"]
    total_f1 = 0
    total_prec = 0
    total_recall = 0

    print(f"  {'Signal':12s} {'Hits':>6s} {'Misses':>8s} {'FalsePos':>9s} {'Recall':>7s} {'Prec':>7s} {'F1':>6s}")
    print("  " + "-" * 56)
    for sig in per_sig:
        h = sig_hits[sig]
        m = sig_misses[sig]
        fp = sig_fps[sig]
        recall = h / (h + m) * 100 if (h + m) > 0 else 0
        prec = h / (h + fp) * 100 if (h + fp) > 0 else 0
        f1 = 2 * prec * recall / (prec + recall) if (prec + recall) > 0 else 0
        print(f"  {sig:12s} {h:6d} {m:8d} {fp:9d} {recall:6.1f}% {prec:6.1f}% {f1:5.1f}")
    print("  " + "-" * 56)
    total_recall = hits_total / (hits_total + misses_total) * 100 if (hits_total + misses_total) > 0 else 0
    total_prec = hits_total / (hits_total + fps_total) * 100 if (hits_total + fps_total) > 0 else 0
    total_f1 = 2 * total_prec * total_recall / (total_prec + total_recall) if (total_prec + total_recall) > 0 else 0
    print(f"  {'TOTAL':12s} {hits_total:6d} {misses_total:8d} {fps_total:9d} {total_recall:6.1f}% {total_prec:6.1f}% {total_f1:5.1f}")
    print()

    # ── Precision (routing safety) ──
    print(f"[PRECISION] {total_prec:.1f}%  — When detector fires, signal is present {total_prec:.0f}% of the time")
    print(f"  → {'SAFE for routing' if total_prec >= 90 else 'WARNING: too many false positives'} (threshold: 90%)")
    print()

    # ── Per-signal precision ──
    for sig in per_sig:
        h = sig_hits[sig]
        fp = sig_fps[sig]
        prec = h / (h + fp) * 100 if (h + fp) > 0 else 0
        print(f"  {sig} precision: {prec:.1f}% ({h}/{h+fp})")

    print()

    # ── Utterance-local recall ──
    ul_hits = scope_hits.get("utterance_local", 0)
    ul_total = scope_total.get("utterance_local", 0)
    ul_recall = ul_hits / ul_total * 100 if ul_total > 0 else 0
    print(f"[UTTERANCE-LOCAL RECALL] {ul_recall:.1f}% ({ul_hits}/{ul_total})")
    print(f"  → {'GOOD for routing decisions' if ul_recall >= 85 else 'MISSES too many single-turn signals'} (threshold: 85%)")
    print()

    # ── False-positive rate (negative-specific) ──
    # Count FPs on entries where human labeled NO signals at all
    fp_neg_entries = 0
    total_neg_entries = 0
    for r in results:
        all_none = all(
            not r["per_signal"][s]["status"] in ("hit", "miss")
            for s in per_sig
        )
        if all_none:
            total_neg_entries += 1
            any_fp = any(r["per_signal"][s]["status"] == "fp" for s in per_sig)
            if any_fp:
                fp_neg_entries += 1
    fp_rate = fp_neg_entries / total_neg_entries * 100 if total_neg_entries > 0 else 0
    print(f"[FALSE-POSITIVE RATE on negatives] {fp_rate:.1f}% ({fp_neg_entries}/{total_neg_entries} entries)")
    print(f"  → {'Very low — factual queries are correctly ignored' if fp_rate <= 5 else 'OK' if fp_rate <= 10 else 'Too many factual queries trigger routing'}")
    print()

    # ── Detector-miss recall ──
    signal_cue_candidates = [r for r in results if r.get("has_signal_cue", True)]
    detector_miss_hits = 0
    detector_miss_total = 0
    for r in signal_cue_candidates:
        for sig in per_sig:
            if r["per_signal"][sig]["status"] == "hit":
                detector_miss_hits += 1
                detector_miss_total += 1
            elif r["per_signal"][sig]["status"] == "miss":
                detector_miss_total += 1
    dm_recall = detector_miss_hits / detector_miss_total * 100 if detector_miss_total > 0 else 0
    print(f"[DETECTOR-MISS RECALL] {dm_recall:.1f}% ({detector_miss_hits}/{detector_miss_total})")
    print(f"  → {'Miners mostly flag what detectors catch' if dm_recall >= 80 else 'Miners expose blind spots — valuable for gap analysis'}")
    print()

    # ── Per-scope recall ──
    print(f"  {'Scope':35s} {'Hits':>6s} {'Misses':>8s} {'Rate':>7s}")
    print("  " + "-" * 56)
    for scope in sorted(scope_hits):
        h = scope_hits[scope]
        t = scope_total[scope]
        rate = h / t * 100 if t > 0 else 0
        print(f"  {scope:35s} {h:6d} {t - h:8d} {rate:6.1f}%")
    print()

    # ── Context-dependent should be separate ──
    ctx_hits = scope_hits.get("conversation_context_required", 0)
    ctx_total = scope_total.get("conversation_context_required", 0)
    ctx_recall = ctx_hits / ctx_total * 100 if ctx_total > 0 else 0
    print(f"[CONTEXT-DEPENDENT RECALL] {ctx_recall:.1f}% ({ctx_hits}/{ctx_total})")
    print(f"  → {'Part of expected architecture gap' if ctx_recall < 20 else 'Surprising — context-dependent signals are being caught utterance-locally'}")
    print()

    # ── Pass 1 vs Pass 2 comparison ──
    for pass_label, pass_ents in [("Pass 1", pass1_entries), ("Pass 2", pass2_entries)]:
        if not pass_ents:
            continue
        p_hits = {"emotion": 0, "grievance": 0, "decision": 0}
        p_misses = {"emotion": 0, "grievance": 0, "decision": 0}
        p_fps = {"emotion": 0, "grievance": 0, "decision": 0}
        for e in pass_ents:
            for sig in per_sig:
                l = e.get("labels", {}).get(sig, {})
                d_old = e.get("detector_output", {}).get(sig, {}).get("value")
                human = l.get("present", False)
                if human and d_old is not None:
                    p_hits[sig] += 1
                elif human and d_old is None:
                    p_misses[sig] += 1
                elif not human and d_old is not None:
                    p_fps[sig] += 1
        p_total_hits = sum(p_hits.values())
        p_total_misses = sum(p_misses.values())
        p_total_fps = sum(p_fps.values())
        p_recall = p_total_hits / (p_total_hits + p_total_misses) * 100 if (p_total_hits + p_total_misses) > 0 else 0
        p_prec = p_total_hits / (p_total_hits + p_total_fps) * 100 if (p_total_hits + p_total_fps) > 0 else 0
        print(f"[{pass_label} only] hits={p_total_hits} misses={p_total_misses} fps={p_total_fps} "
              f"recall={p_recall:.1f}% prec={p_prec:.1f}%")

    print()

    # ── Improvements and regressions (only meaningful on pass 1 entries) ──
    improved = sum(1 for r in results for s in per_sig if r["per_signal"][s].get("improved", False))
    regressed = sum(1 for r in results for s in per_sig if r["per_signal"][s].get("regressed", False))
    if improved + regressed > 0:
        print(f"  Cases improved vs old detector (FP eliminated): {improved}")
        print(f"  Cases regressed vs old detector (hit → miss):   {regressed}")
        print()
    if improved > 0:
        print("  --- Fixed FPs ---")
        for r in results:
            for sig in per_sig:
                if r["per_signal"][sig].get("improved", False):
                    print(f"    {r['conversation_id']}:{r['turn_id']} {sig}: {r['per_signal'][sig]['old_value']} → None")
        print()

    # ── Detector-miss case analysis (pass 1 only, where we have old output) ──
    miss_cases = []
    for r in results:
        for sig in per_sig:
            if r["per_signal"][sig]["status"] == "miss":
                old_val = r["per_signal"][sig].get("old_value")
                cur_val = r["per_signal"][sig].get("current_value")
                miss_cases.append((r["conversation_id"], r["turn_id"], sig, old_val, cur_val, r.get("text", "")[:80]))
    if miss_cases:
        print(f"--- Remaining Misses ({len(miss_cases)} cases) ---")
        for cid, tid, sig, old, cur, txt in sorted(miss_cases):
            print(f"  {cid}:{tid} {sig}: old={old} cur={cur} | {txt}")
        print()

    # ── False positive case analysis ──
    fp_cases = []
    for r in results:
        for sig in per_sig:
            if r["per_signal"][sig]["status"] == "fp":
                cur_val = r["per_signal"][sig].get("current_value")
                fp_cases.append((r["conversation_id"], r["turn_id"], sig, cur_val, r.get("text", "")[:80]))
    if fp_cases:
        print(f"--- Current False Positives ({len(fp_cases)} cases) ---")
        for cid, tid, sig, cur, txt in sorted(fp_cases):
            print(f"  {cid}:{tid} {sig}={cur} | {txt}")
        print()

    # ── Routing decision recommendation ──
    print("=" * 70)
    print("  ROUTING DECISION ANALYSIS")
    print("=" * 70)
    print()
    print(f"  Metric                     Value    Threshold    Verdict")
    print(f"  {'─'*56}")
    verdict_prec = "PASS" if total_prec >= 90 else "FAIL"
    verdict_ul = "PASS" if ul_recall >= 85 else "FAIL"
    verdict_fp = "PASS" if fp_rate <= 5 else "WARN"
    print(f"  Precision                  {total_prec:5.1f}%    ≥90%         {verdict_prec}")
    print(f"  Utterance-local recall     {ul_recall:5.1f}%    ≥85%         {verdict_ul}")
    print(f"  FP rate on negatives       {fp_rate:5.1f}%    ≤5%          {verdict_fp}")
    print(f"  Context-dependent recall   {ctx_recall:5.1f}%    N/A (gap)    EXPECTED")
    print()
    passes = (verdict_prec == "PASS") + (verdict_ul == "PASS") + (verdict_fp == "PASS")
    if passes >= 2:
        print("  → SHADOW-MODE RECOMMENDED — Enable signal-aware routing in shadow mode")
        print("    with a conservative confidence threshold (≥0.8). Monitor FP rate.")
    else:
        print("  → HOLD — Insufficient metrics for shadow-mode routing. Address gaps first.")
    print()


if __name__ == "__main__":
    main()
