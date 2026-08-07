import json, sys
base = json.loads(open('data/benchmark/evaluation/v2.1/pipeline_v1.json', encoding='utf-8').read())
conv = base['per_conversation'].get('BENCH_V21_000039', {})
for t in conv.get('turns_detail', []):
    tn = t['turn']
    ei = t['expected_intent']
    ai = t['actual_intent']
    ea = t['expected_action']
    aa = t['actual_action']
    im = t['intent_match']
    am = t['action_match']
    print(f'Turn {tn}: expected=({ei},{ea}) actual=({ai},{aa}) intent_match={im} action_match={am}')
