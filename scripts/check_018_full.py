import json
c = json.loads(open('data/benchmark/conversations/admission/BENCH_V21_000018.json', encoding='utf-8').read())
print(json.dumps(c['turns'][1]['expected'], indent=2, ensure_ascii=False))
