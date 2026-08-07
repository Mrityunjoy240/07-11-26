import json
c = json.loads(open('data/benchmark/conversations/admission/BENCH_V21_000039.json', encoding='utf-8').read())
for i, t in enumerate(c['turns']):
    s = t['student'][:100]
    intent = t.get('intent', '?')
    action = t.get('action', '?')
    print(f'Turn {i}: {s} | intent={intent} action={action}')
