import json
c = json.loads(open('data/benchmark/conversations/admission/BENCH_V21_000018.json', encoding='utf-8').read())
for i, t in enumerate(c['turns']):
    exp = t.get('expected', {})
    action = exp.get('decision', {}).get('action', '?')
    brain_el = exp.get('brain', {}).get('eligible_branches', [])
    problem = exp.get('reasoning', {}).get('current_problem', '?')
    print(f'Turn {i}: problem={problem} action={action} eligible={brain_el}')
