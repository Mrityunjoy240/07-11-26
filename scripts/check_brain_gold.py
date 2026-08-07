#!/usr/bin/env python3
"""Compare expected vs actual brain eligible_branches across all conversations."""
import json
from pathlib import Path

for vd in sorted(Path("data/benchmark").glob("v*")):
    if not vd.is_dir():
        continue
    for f in sorted(vd.glob("*.json")):
        data = json.loads(f.read_text())
        if not isinstance(data, dict) or "id" not in data:
            continue
        for i, turn in enumerate(data.get("turns", [])):
            b = turn.get("expected", {}).get("brain", {})
            branches = b.get("eligible_branches", [])
            applicable = b.get("applicable")
            if branches or applicable is not None:
                print(f"  {data['id']} T{i+1}: applicable={applicable} branches={branches}")
