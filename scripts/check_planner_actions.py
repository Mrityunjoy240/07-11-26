#!/usr/bin/env python3
"""Check what planner actions are used in the benchmark vs standard vocabulary."""
import json
from pathlib import Path

# Planner actions the pipeline can produce
PLANNER_ACTIONS = {
    "recommend", "ask", "inform", "reassure", "encourage",
    "collect", "clarify", "escalate",
}

for version_dir in sorted(Path("data/benchmark").glob("v*")):
    if not version_dir.is_dir():
        continue
    for f in sorted(version_dir.glob("*.json")):
        data = json.loads(f.read_text())
        if not isinstance(data, dict) or "id" not in data:
            continue

        for i, turn in enumerate(data.get("turns", [])):
            p_exp = turn.get("expected", {}).get("planner", {})
            for j, pt in enumerate(p_exp.get("turns", [])):
                action = pt.get("action", "")
                if action and action not in PLANNER_ACTIONS:
                    print(f"  {data['id']} T{i+1} planner[{j}]: action=\"{action}\"")
