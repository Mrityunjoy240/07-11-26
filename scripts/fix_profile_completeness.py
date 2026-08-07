#!/usr/bin/env python3
"""
Recalculate profile_completeness in all benchmark conversations.

The pipeline counts 7 fields:
  academic.rank, academic.pcm_percentage, academic.board,
  personal.category, career.interest, personal.budget, personal.location

Completeness = filled / 7, where filled = fields present in understanding.facts or conversation state.

This script walks through each turn, tracks which facts have been provided,
and recalculates the correct profile_completeness.
"""

from __future__ import annotations

import json
from pathlib import Path

# The 7 fields the reasoning engine checks, mapped to benchmark fact names
PIPELINE_FIELDS = ["rank", "pcm_percentage", "board", "category", "interest", "budget", "location"]

# Ground truth fields that count as "filled" if present
GROUND_TRUTH_MAP = {
    "rank": "rank",
    "pcm_percentage": "pcm_percentage",
    "board": "board",
    "category": "category",
    "interest": "interest",
    "budget": "budget",
    "location": "location",
}


def recalculate_conversation(conv: dict) -> dict:
    """Walk through turns, track cumulative facts, recalculate completeness."""
    changes = []
    ground_truth = conv.get("ground_truth", {})

    # Track which fields have been provided so far (cumulative across turns)
    provided_fields: set[str] = set()

    # Also track from ground_truth which fields are non-null
    # (these are the "known" fields for this conversation)
    known_gt_fields = set()
    for field, value in ground_truth.items():
        if value is not None and value != "" and value != 0:
            known_gt_fields.add(field)

    for i, turn in enumerate(conv.get("turns", [])):
        expected = turn.get("expected", {})
        facts = expected.get("understanding", {}).get("facts", {})

        # Add facts from this turn to cumulative set
        for field, value in facts.items():
            if value is not None and value != "" and value != 0:
                provided_fields.add(field)

        # Calculate completeness based on what's been provided so far
        filled = 0
        for pf in PIPELINE_FIELDS:
            if pf in provided_fields:
                filled += 1

        correct_completeness = round(filled / len(PIPELINE_FIELDS), 2)
        old_completeness = expected.get("reasoning", {}).get("profile_completeness")

        if old_completeness is not None and abs(old_completeness - correct_completeness) > 0.01:
            changes.append({
                "turn": i,
                "student": turn.get("student", "")[:60],
                "old": old_completeness,
                "new": correct_completeness,
                "fields_provided": sorted(provided_fields),
                "filled": filled,
            })
            if "reasoning" not in expected:
                expected["reasoning"] = {}
            expected["reasoning"]["profile_completeness"] = correct_completeness

    return {
        "id": conv["id"],
        "changes": changes,
        "conversation": conv,
    }


def main():
    benchmark_dir = Path("data/benchmark")
    all_convs = []

    for version_dir in sorted(benchmark_dir.glob("v*")):
        if not version_dir.is_dir():
            continue
        for json_file in sorted(version_dir.glob("*.json")):
            data = json.loads(json_file.read_text())
            if not isinstance(data, dict) or "id" not in data:
                continue
            conv = data
            result = recalculate_conversation(conv)

            if result["changes"]:
                print(f"\n  {result['id']}:")
                for c in result["changes"]:
                    print(f"    Turn {c['turn']+1}: {c['old']:.2f} -> {c['new']:.2f} "
                          f"(fields: {c['fields_provided']}, filled={c['filled']}/7)")
                # Write updated conversation back
                json_file.write_text(json.dumps(result["conversation"], indent=2, ensure_ascii=False))
                print(f"    -> Updated {json_file.name}")
            else:
                print(f"  {result['id']}: no changes needed")

            all_convs.append(result)

    total_changes = sum(len(r["changes"]) for r in all_convs)
    print(f"\n  Total changes: {total_changes} across {len(all_convs)} conversations")


if __name__ == "__main__":
    main()
