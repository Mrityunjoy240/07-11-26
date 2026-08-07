"""Create annotation template for Pass 2: 44 new candidates not yet labeled.

Produces: data/evaluation/structured_signals/annotations_new.jsonl

Each entry has empty labels field which the annotator fills in.
"""
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    # Load existing annotations
    existing: dict[tuple[str, int], dict] = {}
    apath = Path("data/evaluation/structured_signals/annotations.jsonl")
    if apath.exists():
        for line in apath.read_text(encoding="utf-8").strip().split("\n"):
            e = json.loads(line)
            existing[(e["conversation_id"], e["turn_id"])] = e

    # Load new mined candidates
    mpath = Path("data/evaluation/structured_signals/mined_candidates.jsonl")
    mined = [json.loads(l) for l in mpath.read_text(encoding="utf-8").strip().split("\n")]

    # Build new entries
    new_entries = []
    for r in mined:
        key = (r["conversation_id"], r["turn_id"])
        if key in existing:
            continue

        entry = {
            "conversation_id": r["conversation_id"],
            "turn_id": r["turn_id"],
            "text": r["text"],
            "domain": r["domain"],
            "scope": r["scope"],
            "has_signal_cue": r["has_signal_cue"],
            "mining_scores": r["overall_likelihood"],
            "downweighted_likelihood": r["downweighted_likelihood"],
            "detector_output": r["detector_output"],
            "source": r["source"],
            "annotation_pass": 2,
            # Fill these in:
            "labels": {
                "emotion": {"present": False, "subtype": None, "confidence": 0.0},
                "grievance": {"present": False, "subtype": None, "confidence": 0.0},
                "decision": {"present": False, "subtype": None, "confidence": 0.0},
                "evidence_type": None,
            },
            "annotator_notes": "",
        }
        new_entries.append(entry)

    outpath = Path("data/evaluation/structured_signals/annotations_new.jsonl")
    with open(outpath, "w", encoding="utf-8") as f:
        for e in new_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    signal_name = {0: "neg", 1: "grievance", 2: "decision", 3: "emotion"}
    print(f"Written: {outpath} ({len(new_entries)} entries)")
    print()
    print("=== Pass 2 Annotation Template ===")
    print(f"Total entries to annotate: {len(new_entries)}")
    print()

    # Group by signal cue / scope
    signal_entries = [e for e in new_entries if e["has_signal_cue"]]
    neg_entries = [e for e in new_entries if not e["has_signal_cue"]]
    print(f"  Miner-flagged (likely signal): {len(signal_entries)}")
    print(f"  Negatives (contrast):          {len(neg_entries)}")
    print()

    # Per signal type for signal_entries
    from collections import Counter
    sig_types = Counter()
    for e in signal_entries:
        ol = e["mining_scores"]
        best = max(["grievance", "decision", "emotion"], key=lambda s: ol.get(s, 0))
        sig_types[best] += 1
    print(f"  Signal types: {dict(sig_types)}")

    # Detector overlap
    det_hits = sum(
        1 for e in new_entries
        if any(e["detector_output"][s]["value"] for s in ["emotion", "grievance", "decision"])
    )
    print(f"  Detected by current detectors: {det_hits}")

    print()
    print("--- New entries ---")
    for e in sorted(new_entries, key=lambda e: (not e["has_signal_cue"], e["conversation_id"], e["turn_id"])):
        ol = e["mining_scores"]
        best = max(["grievance", "decision", "emotion"], key=lambda s: ol.get(s, 0))
        best_score = ol.get(best, 0)
        det_str = " ".join(
            f"{s}={e['detector_output'][s]['value'] or '—'}"
            for s in ["emotion", "grievance", "decision"]
        )
        print(f"  [{e['has_signal_cue'] and 'SIG' or 'NEG'}] "
              f"{e['conversation_id']}:{e['turn_id']} "
              f"[{best}:{best_score:.1f}] [{e['scope'][:15]}] "
              f"detect: {det_str} | {e['text'][:80]}")


if __name__ == "__main__":
    main()
