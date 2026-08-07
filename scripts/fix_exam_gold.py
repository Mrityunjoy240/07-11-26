#!/usr/bin/env python3
"""Remove 'exam' from facts when student doesn't mention it and ground_truth exam is N/A."""
import json
from pathlib import Path

for version_dir in sorted(Path("data/benchmark").glob("v*")):
    if not version_dir.is_dir():
        continue
    for f in sorted(version_dir.glob("*.json")):
        data = json.loads(f.read_text())
        if not isinstance(data, dict) or "id" not in data:
            continue

        gt_exam = data.get("ground_truth", {}).get("exam")
        changed = False

        for i, turn in enumerate(data.get("turns", [])):
            facts = turn.get("expected", {}).get("understanding", {}).get("facts", {})
            if "exam" in facts and gt_exam is None:
                # Student didn't mention exam and ground_truth has no exam
                # Check if student text actually mentions an exam
                student = turn.get("student", "").lower()
                mentions_exam = any(w in student for w in ["wbjee", "wb jee", "jee", "jelet", "jexpo", "nata", "cuet"])
                if not mentions_exam:
                    print(f"  {data['id']} T{i+1}: removing exam='{facts['exam']}' from facts (not mentioned by student)")
                    del facts["exam"]
                    changed = True

        if changed:
            f.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            print(f"    -> Updated {f.name}")
