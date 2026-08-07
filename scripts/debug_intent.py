"""Debug fee→scholarship confusion and admission→fee confusion."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, '.')

from src.understanding.engine import UnderstandingEngine
from src.engines.interfaces import UnderstandingInput

baseline = json.loads(Path('data/benchmark/evaluation/v2.1/pipeline_v1.json').read_text(encoding='utf-8'))
CONVS_DIR = Path('data/benchmark/conversations')

ue = UnderstandingEngine()

# Find fee→scholarship and admission→fee failures
targets = [
    ('fee', 'scholarship'),
    ('admission', 'fee'),
    ('department', 'admission'),
]

for expected, actual in targets:
    print(f'\n{"="*70}')
    print(f'{expected} → {actual} failures')
    print(f'{"="*70}')
    for conv_id, data in sorted(baseline['per_conversation'].items()):
        for turn in data.get('turns_detail', []):
            if turn['expected_intent'] == expected and turn['actual_intent'] == actual:
                for fp in CONVS_DIR.rglob(f'{conv_id}.json'):
                    gold = json.loads(fp.read_text(encoding='utf-8'))
                    gold_turn = gold['turns'][turn['turn']]
                    text = gold_turn['student']
                    
                    result = ue.process(UnderstandingInput(text=text))
                    top3 = sorted(result.intent.all_scores.items(), key=lambda x: -x[1])[:5]
                    
                    print(f'\n  {conv_id} turn {turn["turn"]}:')
                    print(f'  Text: {text[:80]}')
                    print(f'  Scores: {top3}')
                    print(f'  Expected: {expected}, Got: {actual}')
