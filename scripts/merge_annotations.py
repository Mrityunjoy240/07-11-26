"""Merge Pass 1 (37 entries) and Pass 2 (44 entries) annotations.

Output: data/evaluation/structured_signals/annotations_merged.jsonl
"""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    merged: dict[tuple[str, int], dict] = {}

    # Load Pass 1
    p1 = Path("data/evaluation/structured_signals/annotations.jsonl")
    if p1.exists():
        for line in p1.read_text(encoding="utf-8").strip().split("\n"):
            e = json.loads(line)
            merged[(e["conversation_id"], e["turn_id"])] = e

    # Load Pass 2
    p2 = Path("data/evaluation/structured_signals/annotations_new.jsonl")
    if p2.exists():
        for line in p2.read_text(encoding="utf-8").strip().split("\n"):
            e = json.loads(line)
            key = (e["conversation_id"], e["turn_id"])
            if key in merged:
                print(f"WARNING: Duplicate key {key}, Pass 2 overwriting Pass 1")
            merged[key] = e

    # Write merged
    entries = sorted(merged.values(), key=lambda e: (e["conversation_id"], e["turn_id"]))
    outpath = Path("data/evaluation/structured_signals/annotations_merged.jsonl")
    with open(outpath, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    # Stats
    sig_counts = {"emotion": 0, "grievance": 0, "decision": 0}
    multi = 0
    none_count = 0
    p1_count = 0
    p2_count = 0
    for e in entries:
        if e.get("annotation_pass") == 2:
            p2_count += 1
        else:
            p1_count += 1
        l = e.get("labels", {})
        present = [k for k in ["emotion", "grievance", "decision"] if l.get(k, {}).get("present", False)]
        if len(present) >= 2:
            multi += 1
        if len(present) == 0:
            none_count += 1
        for k in present:
            sig_counts[k] += 1

    print(f"Written: {outpath} ({len(entries)} entries)")
    print(f"  Pass 1: {p1_count}")
    print(f"  Pass 2: {p2_count}")
    print(f"\n=== Merged Annotation Summary ===")
    print(f"Emotion: {sig_counts['emotion']}")
    print(f"Grievance: {sig_counts['grievance']}")
    print(f"Decision: {sig_counts['decision']}")
    print(f"Multi-signal turns: {multi}")
    print(f"No-signal turns: {none_count}")
    print(f"Total positive signals: {sum(sig_counts.values())}")


if __name__ == "__main__":
    main()
