"""Pass 2 adjudication: compare human labels against detector output.

Produces adjudicated.jsonl with resolved disagreements and final gold labels.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def main() -> None:
    inpath = Path("data/evaluation/structured_signals/annotations.jsonl")
    entries = [json.loads(l) for l in inpath.read_text(encoding="utf-8").strip().split("\n")]

    adjudicated = []
    disagreements: dict[str, list[str]] = {"emotion": [], "grievance": [], "decision": []}

    for e in entries:
        label = e["labels"]
        det = e["detector_output"]
        text_short = e["text"][:60]

        dispute = {"emotion": False, "grievance": False, "decision": False}
        resolution = {}

        for sig in ["emotion", "grievance", "decision"]:
            human_present = label[sig]["present"]
            det_present = det[sig]["value"] is not None

            if human_present and not det_present:
                dispute[sig] = True
                resolution[sig] = f"Miss: detector returned None, human says {label[sig]['subtype']} (conf={label[sig]['confidence']})"
                disagreements[sig].append(f"{e['conversation_id']}:{e['turn_id']} - {resolution[sig]}")
            elif not human_present and det_present:
                dispute[sig] = True
                resolution[sig] = f"FP: detector returned {det[sig]['value']} (conf={det[sig]['confidence']}), human says absent"
                disagreements[sig].append(f"{e['conversation_id']}:{e['turn_id']} - {resolution[sig]}")
            elif human_present and det_present:
                subtype_match = label[sig]["subtype"] == det[sig]["value"]
                if not subtype_match:
                    resolution[sig] = f"Subtype mismatch: human={label[sig]['subtype']}, detector={det[sig]['value']}"
                    disagreements[sig].append(f"{e['conversation_id']}:{e['turn_id']} - {resolution[sig]}")

        adjudicated_entry = {
            **e,
            "adjudication": {
                "has_dispute": any(dispute.values()),
                "disputes": dispute,
                "resolution": resolution or None,
            },
            "annotation_pass": 2,
            "gold_labels": label,
        }
        adjudicated.append(adjudicated_entry)

    outpath = Path("data/evaluation/structured_signals/adjudicated.jsonl")
    with open(outpath, "w", encoding="utf-8") as f:
        for a in adjudicated:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    print(f"Written: {outpath} ({len(adjudicated)} entries)")

    # Summary
    total_disputes = sum(1 for a in adjudicated if a["adjudication"]["has_dispute"])
    print(f"\n=== Adjudication Summary ===")
    print(f"Total entries: {len(adjudicated)}")
    print(f"Entries with disputes: {total_disputes}")
    print()

    for sig in ["emotion", "grievance", "decision"]:
        if disagreements[sig]:
            print(f"--- {sig} disagreements ({len(disagreements[sig])}) ---")
            for d in disagreements[sig]:
                print(f"  {d}")
            print()

    # Per-scope gold-label detection rate
    print("=== Final Gold-Label Performance (per scope) ===")
    for scope_name in ["utterance_local", "conversation_context_required", "ambiguous"]:
        scope_entries = [a for a in adjudicated if a["scope"] == scope_name]
        if not scope_entries:
            continue
        hits = 0
        misses = 0
        fps = 0
        for a in scope_entries:
            l = a["gold_labels"]
            d = a["detector_output"]
            for sig in ["emotion", "grievance", "decision"]:
                if l[sig]["present"]:
                    if d[sig]["value"] is not None:
                        hits += 1
                    else:
                        misses += 1
                elif d[sig]["value"] is not None:
                    fps += 1
        total_signals = hits + misses
        pct = 100.0 * hits / total_signals if total_signals > 0 else 0
        print(f"  {scope_name:35s} hits={hits} misses={misses} fps={fps}   detection_rate={pct:.0f}%")

    # Overall metrics
    total_hits = 0
    total_misses = 0
    total_fps = 0
    for a in adjudicated:
        l = a["gold_labels"]
        d = a["detector_output"]
        for sig in ["emotion", "grievance", "decision"]:
            if l[sig]["present"]:
                if d[sig]["value"] is not None:
                    total_hits += 1
                else:
                    total_misses += 1
            elif d[sig]["value"] is not None:
                total_fps += 1
    precision = total_hits / (total_hits + total_fps) if (total_hits + total_fps) > 0 else 0
    recall = total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print()
    print("=== Aggregate Metrics ===")
    print(f"  Hits:  {total_hits}")
    print(f"  Misses: {total_misses}")
    print(f"  FPs:   {total_fps}")
    print(f"  Precision: {precision:.2f}")
    print(f"  Recall:    {recall:.2f}")
    print(f"  F1:        {f1:.2f}")


if __name__ == "__main__":
    main()
