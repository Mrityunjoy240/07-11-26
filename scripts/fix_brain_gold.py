#!/usr/bin/env python3
"""Recalculate brain eligible_branches using the pipeline's 15% margin threshold."""
import json
from pathlib import Path

# Same cutoffs as src/brain/admission.py
DEFAULT_CUTOFFS = {
    "general": {
        "CSE": (1, 15000), "AIML": (1, 18000), "IT": (1, 22000),
        "ECE": (1, 28000), "EE": (1, 40000), "ME": (1, 55000), "CE": (1, 70000),
    },
    "obc": {
        "CSE": (1, 22000), "AIML": (1, 26000), "IT": (1, 32000),
        "ECE": (1, 40000), "EE": (1, 55000), "ME": (1, 75000), "CE": (1, 95000),
    },
    "sc": {
        "CSE": (1, 40000), "AIML": (1, 48000), "IT": (1, 55000),
        "ECE": (1, 65000), "EE": (1, 85000), "ME": (1, 110000), "CE": (1, 140000),
    },
    "st": {
        "CSE": (1, 50000), "AIML": (1, 60000), "IT": (1, 70000),
        "ECE": (1, 85000), "EE": (1, 110000), "ME": (1, 140000), "CE": (1, 180000),
    },
}

MARGIN_THRESHOLD = 0.15


def compute_eligible(rank: int, category: str) -> list[str]:
    """Compute eligible branches using the pipeline's logic."""
    cat = category.lower().replace("ur", "general").replace("gen", "general")
    cutoffs = DEFAULT_CUTOFFS.get(cat, DEFAULT_CUTOFFS["general"])
    eligible = []
    for branch, (_, hi) in cutoffs.items():
        if rank <= hi:
            margin = (hi - rank) / hi
            if margin > MARGIN_THRESHOLD:
                eligible.append(branch)
    return sorted(eligible)


for version_dir in sorted(Path("data/benchmark").glob("v*")):
    if not version_dir.is_dir():
        continue
    for f in sorted(version_dir.glob("*.json")):
        data = json.loads(f.read_text())
        if not isinstance(data, dict) or "id" not in data:
            continue

        changed = False
        # Track cumulative facts to determine rank and category at each turn
        rank = None
        category = "general"

        for i, turn in enumerate(data.get("turns", [])):
            facts = turn.get("expected", {}).get("understanding", {}).get("facts", {})
            if facts.get("rank") is not None:
                rank = facts["rank"]
            if facts.get("category") is not None:
                category = facts["category"]

            brain = turn.get("expected", {}).get("brain", {})
            if brain.get("applicable") and rank is not None:
                correct_branches = compute_eligible(rank, category)
                old_branches = brain.get("eligible_branches", [])
                if sorted(old_branches) != correct_branches:
                    print(f"  {data['id']} T{i+1}: rank={rank} cat={category} "
                          f"branches {old_branches} -> {correct_branches}")
                    brain["eligible_branches"] = correct_branches
                    changed = True

        if changed:
            f.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            print(f"    -> Updated {f.name}")
