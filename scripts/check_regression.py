import json
base = json.loads(open('data/benchmark/evaluation/v2.1/pipeline_v1.json', encoding='utf-8').read())
# Show NEW failures (conversations that were PASS before)
prev_pass = {"BENCH_V21_000010", "BENCH_V21_000020"}
for conv_id in sorted(base['per_conversation']):
    data = base['per_conversation'][conv_id]
    turns = data.get('turns_detail', [])
    for t in turns:
        if not t['action_match']:
            print(f'{conv_id} turn {t["turn"]}: exp=({t["expected_intent"]},{t["expected_action"]}) actual=({t["actual_intent"]},{t["actual_action"]})')
