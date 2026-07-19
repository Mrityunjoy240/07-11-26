#!/usr/bin/env python3
"""Analyze content_contains keywords across all benchmark conversations."""
import json
from pathlib import Path
from collections import Counter

# Generic filler words that should NOT be in content_contains
GENERIC_WORDS = {
    "like", "know", "more", "next", "any", "question", "help", "think",
    "tell", "share", "consider", "want", "need", "good", "best", "please",
    "would", "could", "should", "also", "about", "that", "this", "what",
    "how", "when", "where", "which", "who", "why", "yes", "no", "ok",
    "sure", "right", "well", "very", "really", "just", "actually",
}

all_keywords = Counter()
generic_found = []

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
                for kw in pt.get("content_contains", []):
                    all_keywords[kw.lower()] += 1
                    if kw.lower() in GENERIC_WORDS:
                        generic_found.append((data["id"], i+1, j, kw))

print(f"  Total unique keywords: {len(all_keywords)}")
print(f"  Total keyword occurrences: {sum(all_keywords.values())}")
print(f"  Generic filler words found: {len(generic_found)}")
print()

if generic_found:
    print("  Generic keywords to remove:")
    for conv_id, turn, plan_idx, kw in generic_found:
        print(f"    {conv_id} T{turn} planner[{plan_idx}]: '{kw}'")

print()
print("  Top 30 most common keywords:")
for kw, count in all_keywords.most_common(30):
    marker = " [GENERIC]" if kw in GENERIC_WORDS else ""
    print(f"    {kw:25s} {count:3d}{marker}")
