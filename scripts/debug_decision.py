"""Debug Phase 4 decision issues."""
import json
from pathlib import Path

baseline = json.loads(Path('data/benchmark/evaluation/v2.1/pipeline_v1.json').read_text(encoding='utf-8'))
CONVS_DIR = Path('data/benchmark/conversations')

# Find recommend_branches→provide_admission_guidance and provide_guidance→counseling
targets = [
    ('recommend_branches', 'provide_admission_guidance', 'C: brain not overriding'),
    ('provide_guidance', 'provide_counseling_schedule', 'C: counseling text routing'),
]

for expected, actual, label in targets:
    print(f'\n{"="*70}')
    print(f'{label}: expected={expected} actual={actual}')
    print(f'{"="*70}')
    for conv_id, data in sorted(baseline['per_conversation'].items()):
        for turn in data.get('turns_detail', []):
            if turn['expected_action'] == expected and turn['actual_action'] == actual:
                for fp in CONVS_DIR.rglob(f'{conv_id}.json'):
                    gold = json.loads(fp.read_text(encoding='utf-8'))
                    gold_turn = gold['turns'][turn['turn']]
                    text = gold_turn['student']
                    print(f'\n  {conv_id} turn {turn["turn"]}:')
                    print(f'  Text: {text}')
                    print(f'  Ground intent: {gold_turn.get("intent", "?")}')
                    print(f'  Ground action: {gold_turn.get("action", "?")}')
                    print(f'  Actual intent: {turn.get("actual_intent", "?")}')
                    print(f'  Actual action: {turn.get("actual_action", "?")}')
                    print(f'  Profile: {json.dumps(gold.get("ground_truth", {}), indent=2)[:200]}')
