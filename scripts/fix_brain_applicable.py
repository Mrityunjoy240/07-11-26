#!/usr/bin/env python3
"""Fix brain applicable=True when rank is provided."""
import json
from pathlib import Path

for version_dir in sorted(Path("data/benchmark").glob("v*")):
    if not version_dir.is_dir():
        continue
    for f in sorted(version_dir.glob("*.json")):
        data = json.loads(f.read_text())
        if not isinstance(data, dict) or "id" not in data:
            continue

        changed = False
        rank = None

        for i, turn in enumerate(data.get("turns", [])):
            facts = turn.get("expected", {}).get("understanding", {}).get("facts", {})
            if facts.get("rank") is not None:
                rank = facts["rank"]

            brain = turn.get("expected", {}).get("brain", {})
            # Brain is applicable if rank is provided (per brain engine logic)
            if rank is not None and brain.get("applicable") is False:
                print(f"  {data['id']} T{i+1}: applicable False -> True (rank={rank})")
                brain["applicable"] = True
                changed = True

        if changed:
            f.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            print(f"    -> Updated {f.name}")
