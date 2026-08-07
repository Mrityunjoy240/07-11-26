import json
c = json.loads(open('data/benchmark/conversations/admission/BENCH_V21_000006.json', encoding='utf-8').read())
print(json.dumps(c['turns'][2]['expected'], indent=2, ensure_ascii=False))
