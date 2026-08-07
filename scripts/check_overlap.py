from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

annotations = {}
apath = Path("data/evaluation/structured_signals/annotations.jsonl")
if apath.exists():
    for line in apath.read_text(encoding="utf-8").strip().split("\n"):
        e = json.loads(line)
        annotations[(e["conversation_id"], e["turn_id"])] = e

mpath = Path("data/evaluation/structured_signals/mined_candidates.jsonl")
mined = [json.loads(l) for l in mpath.read_text(encoding="utf-8").strip().split("\n")]

new_candidates = []
overlap = []
for r in mined:
    key = (r["conversation_id"], r["turn_id"])
    if key in annotations:
        overlap.append(key)
    else:
        new_candidates.append(r)

print(f"Existing annotations: {len(annotations)}")
print(f"New mined candidates: {len(mined)}")
print(f"Overlap: {len(overlap)}")
print(f"New (not yet annotated): {len(new_candidates)}")
n_sig = sum(1 for r in new_candidates if r.get("has_signal_cue", False))
n_neg = sum(1 for r in new_candidates if not r.get("has_signal_cue", False))
print(f"  Signal-bearing: {n_sig}")
print(f"  Negatives: {n_neg}")

sig_types = Counter()
for r in new_candidates:
    if r.get("has_signal_cue", False):
        ol = r["overall_likelihood"]
        best = max(["grievance", "decision", "emotion"], key=lambda s: ol.get(s, 0))
        sig_types[best] += 1
print(f"  New signal by type: {dict(sig_types)}")

# Also list all new signal candidates with type and scope
print("\n--- New signal candidates ---")
for r in sorted(new_candidates, key=lambda r: r.get("has_signal_cue", False), reverse=True):
    if r.get("has_signal_cue", False):
        ol = r["overall_likelihood"]
        best = max(["grievance", "decision", "emotion"], key=lambda s: ol.get(s, 0))
        print(f"  {r['conversation_id']}:{r['turn_id']} [{best:10s}] [{r['scope']:35s}] {r['text'][:80]}")
