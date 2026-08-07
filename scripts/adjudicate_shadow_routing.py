"""Adjudicate shadow routing telemetry — review routed events and calculate metrics.

Workflow:
  1. Run traffic → telemetry accumulates at data/telemetry/shadow_routing.jsonl
  2. python scripts/adjudicate_shadow_routing.py              # quick summary
  3. python scripts/adjudicate_shadow_routing.py --export     # create adjudication template
  4. Edit data/telemetry/shadow_routing_adjudicated.jsonl
     Set adjudicated_label: "tp" | "fp" | "unsure"
  5. python scripts/adjudicate_shadow_routing.py --adjudicate # stratified report
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from src.reasoning.shadow_routing import load_telemetry, telemetry_summary, _confidence_band

TELEMETRY_PATH = Path("data/telemetry/shadow_routing.jsonl")
ADJUDICATION_PATH = Path("data/telemetry/shadow_routing_adjudicated.jsonl")


# ── Helpers ───────────────────────────────────────────────────────────

def _detect_language(text: str) -> str:
    """Simple language hint based on script detection."""
    devanagari = set("अआइईउऊएऐओऔकखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहािीुूृेैोौंः")
    bengali = set("অআইঈউঊএঐওঔকখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহিীুূৃেৈোৌংঃ")
    if set(text) & devanagari:
        return "hindi"
    if set(text) & bengali:
        return "bengali"
    return "english"


def _summarize_adj(records: list[dict]) -> dict:
    """Aggregate adjudicated records into a summary dict."""
    tp = [r for r in records if r.get("adjudicated_label") == "tp"]
    fp = [r for r in records if r.get("adjudicated_label") == "fp"]
    unsure = [r for r in records if r.get("adjudicated_label") == "unsure"]
    total_adj = len(tp) + len(fp) + len(unsure)
    precision = len(tp) / (len(tp) + len(fp)) * 100 if (len(tp) + len(fp)) > 0 else None

    # Per signal type
    by_signal: dict[str, dict] = defaultdict(lambda: {"tp": 0, "fp": 0, "unsure": 0})
    for r in tp:
        by_signal[r.get("signal_type", "unknown")]["tp"] += 1
    for r in fp:
        by_signal[r.get("signal_type", "unknown")]["fp"] += 1
    for r in unsure:
        by_signal[r.get("signal_type", "unknown")]["unsure"] += 1

    # Per confidence band
    by_band: dict[str, dict] = defaultdict(lambda: {"tp": 0, "fp": 0, "unsure": 0})
    for r in tp:
        band = r.get("confidence_band") or _confidence_band(r.get("signal_confidence", 0))
        by_band[band]["tp"] += 1
    for r in fp:
        band = r.get("confidence_band") or _confidence_band(r.get("signal_confidence", 0))
        by_band[band]["fp"] += 1
    for r in unsure:
        band = r.get("confidence_band") or _confidence_band(r.get("signal_confidence", 0))
        by_band[band]["unsure"] += 1

    # Per language
    by_lang: dict[str, dict] = defaultdict(lambda: {"tp": 0, "fp": 0, "unsure": 0})
    for r in tp:
        lang = r.get("language_hint", _detect_language(r.get("text", "")))
        by_lang[lang]["tp"] += 1
    for r in fp:
        lang = r.get("language_hint", _detect_language(r.get("text", "")))
        by_lang[lang]["fp"] += 1
    for r in unsure:
        lang = r.get("language_hint", _detect_language(r.get("text", "")))
        by_lang[lang]["unsure"] += 1

    # Per scope
    by_scope: dict[str, dict] = defaultdict(lambda: {"tp": 0, "fp": 0, "unsure": 0})
    for r in tp:
        by_scope[r.get("scope", "unknown")]["tp"] += 1
    for r in fp:
        by_scope[r.get("scope", "unknown")]["fp"] += 1
    for r in unsure:
        by_scope[r.get("scope", "unknown")]["unsure"] += 1

    return {
        "total_all": len(records),
        "total_adj": total_adj,
        "tp": len(tp),
        "fp": len(fp),
        "unsure": len(unsure),
        "precision": round(precision, 1) if precision is not None else None,
        "fp_rate": round(len(fp) / total_adj * 100, 1) if total_adj > 0 else None,
        "unsure_rate": round(len(unsure) / total_adj * 100, 1) if total_adj > 0 else None,
        "by_signal": {k: dict(v) for k, v in sorted(by_signal.items())},
        "by_band": {k: dict(v) for k, v in sorted(by_band.items())},
        "by_lang": {k: dict(v) for k, v in sorted(by_lang.items())},
        "by_scope": {k: dict(v) for k, v in sorted(by_scope.items())},
    }


def _print_section(label: str, data: dict) -> None:
    """Print a stratified breakdown section."""
    print(f"  {label}")
    print(f"  {'':─<{len(label)+2}}")
    print(f"  {'Category':20s} {'TP':>4s}  {'FP':>4s}  {'Unsure':>7s}  {'Prec':>6s}")
    print(f"  {'-'*45}")
    for key, counts in sorted(data.items()):
        t = counts["tp"]
        f = counts["fp"]
        u = counts["unsure"]
        p = t / (t + f) * 100 if (t + f) > 0 else 0
        print(f"  {key:20s} {t:>4d}  {f:>4d}  {u:>7d}  {p:>5.1f}%")
    print()


# ── Commands ──────────────────────────────────────────────────────────

def cmd_summary() -> None:
    """Print a summary of current shadow routing telemetry."""
    records = load_telemetry(TELEMETRY_PATH)
    if not records:
        print("No shadow routing telemetry found.")
        return

    summary = telemetry_summary(records)

    print("=" * 60)
    print("  Shadow Routing Telemetry Summary")
    print("=" * 60)
    print(f"  Total turns logged:   {summary['total_turns']}")
    print(f"  Would-route events:   {summary['would_route']} ({summary['would_route_pct']}%)")
    print(f"  Threshold:            {summary['threshold']}")
    print()
    print(f"  By signal type:")
    for sig, count in sorted(summary["by_signal"].items()):
        print(f"    {sig}: {count}")
    print()

    # Check if adjudication exists
    if ADJUDICATION_PATH.exists():
        adj_records = load_telemetry(ADJUDICATION_PATH)
        if adj_records:
            adj_summary = _summarize_adj(adj_records)
            print(f"  Adjudicated: {adj_summary['total_adj']} events")
            print(f"    TP: {adj_summary['tp']}  FP: {adj_summary['fp']}  "
                  f"Unsure: {adj_summary['unsure']}")
            if adj_summary["precision"] is not None:
                print(f"    Precision: {adj_summary['precision']}%")


def cmd_export() -> None:
    """Export routed events as an adjudication template."""
    records = load_telemetry(TELEMETRY_PATH)
    routed = [r for r in records if r.get("would_route")]

    if not routed:
        print("No routed events to export.")
        return

    # Load existing adjudications to avoid duplicates
    already = set()
    if ADJUDICATION_PATH.exists():
        for r in load_telemetry(ADJUDICATION_PATH):
            already.add(r.get("observation_id"))

    new_events = [r for r in routed if r["observation_id"] not in already]

    if not new_events:
        print("All routed events are already adjudicated.")
        return

    with open(ADJUDICATION_PATH, "a", encoding="utf-8") as f:
        for r in new_events:
            text = r.get("text", "")[:120]
            scope = r.get("scope", "utterance_local")
            lang = r.get("language_hint") or _detect_language(text)
            band = r.get("confidence_band") or _confidence_band(r.get("signal_confidence", 0))
            entry = {
                "observation_id": r["observation_id"],
                "signal_type": r.get("signal_type"),
                "signal_confidence": r.get("signal_confidence"),
                "confidence_band": band,
                "language_hint": lang,
                "scope": scope,
                "text": text,
                "identified_problem": r.get("identified_problem", ""),
                "intent_primary": r.get("intent_primary", ""),
                # Fill these in:
                "adjudicated_label": None,  # "tp" | "fp" | "unsure"
                "adjudicator_notes": "",
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"Exported {len(new_events)} routed events for adjudication: {ADJUDICATION_PATH}")
    print()
    print("Edit the file and fill in:")
    print('  "adjudicated_label": "tp" | "fp" | "unsure"')
    print('  "adjudicator_notes": "optional context"')
    print()
    print("Then run: python scripts/adjudicate_shadow_routing.py --adjudicate")


def cmd_adjudicate() -> None:
    """Calculate stratified metrics from adjudicated events."""
    if not ADJUDICATION_PATH.exists():
        print(f"No adjudication file found at {ADJUDICATION_PATH}")
        print("Run with --export first.")
        return

    records = load_telemetry(ADJUDICATION_PATH)
    adjudicated = [r for r in records if r.get("adjudicated_label") is not None]
    pending = [r for r in records if r.get("adjudicated_label") is None]

    if not adjudicated:
        print("No adjudicated events. Fill in adjudicated_label values first.")
        return

    if pending:
        print(f"WARNING: {len(pending)} events still pending adjudication (skipped).")
        print()

    summary = _summarize_adj(adjudicated)

    print("=" * 70)
    print("  Shadow Routing — Adjudication Results")
    print("=" * 70)
    print()
    print(f"  Total routed events logged:   {summary['total_all']}")
    print(f"  Total adjudicated:            {summary['total_adj']}")
    print(f"    True positives:             {summary['tp']}")
    print(f"    False positives:            {summary['fp']}")
    print(f"    Unsure:                     {summary['unsure']}")
    print()
    if summary["precision"] is not None:
        print(f"  Precision:   {summary['precision']}%")
    if summary["fp_rate"] is not None:
        print(f"  FP rate:     {summary['fp_rate']}%")
    if summary["unsure_rate"] is not None:
        print(f"  Unsure rate: {summary['unsure_rate']}%")
    print()

    # Stratified breakdowns
    print("── Stratified breakdown ──")
    print()
    _print_section("By signal type", summary["by_signal"])
    _print_section("By confidence band", summary["by_band"])
    _print_section("By language", summary["by_lang"])
    _print_section("By scope", summary["by_scope"])

    # Decision recommendation
    print("── Recommendation ──")
    print()
    if summary["precision"] is not None and summary["total_adj"] >= 10:
        if summary["precision"] >= 90:
            print(f"  Precision {summary['precision']}% on {summary['total_adj']} adjudicated events:")
            print("  → Threshold 0.8 validated. Ready to enable narrow routing")
            print("    (emotion + grievance, utterance-local).")
        elif summary["precision"] >= 75:
            print(f"  Precision {summary['precision']}% on {summary['total_adj']} adjudicated events:")
            print("  → Borderline. Consider lowering or keeping shadow mode.")
        else:
            print(f"  Precision {summary['precision']}% on {summary['total_adj']} adjudicated events:")
            print("  → Too many false positives. Keep shadow mode,")
            print("    raise threshold to 0.85 or fix detector pattern.")
    else:
        remaining = max(0, 10 - summary["total_adj"])
        print(f"  Need {remaining} more adjudicated events before routing decision.")
        print(f"  Target: ≥10 adjudicated (currently {summary['total_adj']}).")
    print()


def main() -> None:
    if len(sys.argv) < 2:
        cmd_summary()
        return

    cmd = sys.argv[1]
    if cmd == "--export":
        cmd_export()
    elif cmd == "--adjudicate":
        cmd_adjudicate()
    elif cmd == "--help":
        print(__doc__)
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python scripts/adjudicate_shadow_routing.py [--export | --adjudicate | --help]")


if __name__ == "__main__":
    main()
