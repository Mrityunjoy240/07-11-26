#!/usr/bin/env python3
"""Check student text vs gold exam field for conversations where exam extraction fails."""
import json
from pathlib import Path

convs_to_check = ['ADM_LOWCONFIDENCE_001', 'ADM_MANAGEMENT_001', 'FEES_PARENT_001', 'TRANSFER_001']
for cid in convs_to_check:
    for vd in Path('data/benchmark').glob('v*'):
        f = vd / f'{cid}.json'
        if f.exists():
            data = json.loads(f.read_text())
            gt_exam = data.get("ground_truth", {}).get("exam", "N/A")
            print(f"\n  {cid}: ground_truth exam={gt_exam}")
            for i, t in enumerate(data.get('turns', [])):
                student = t['student']
                has_wbjee = 'wbjee' in student.lower() or 'wb jee' in student.lower()
                print(f"    T{i+1}: \"{student[:80]}\"  mentions_exam={has_wbjee}")
            break
