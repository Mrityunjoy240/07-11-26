import json
c = json.loads(open('data/benchmark/conversations/admission/BENCH_V21_000006.json', encoding='utf-8').read())
for i, t in enumerate(c['turns']):
    s = t['student'][:80]
    exp = t.get('expected', {})
    action = exp.get('decision', {}).get('action', '?')
    problem = exp.get('reasoning', {}).get('current_problem', '?')
    print(f'Turn {i}: {s}')
    print(f'  exp: problem={problem} action={action}')
