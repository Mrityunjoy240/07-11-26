"""Extract failing queries from benchmark final results."""
import json

results = json.load(open(
    r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend\benchmarks\eval_reports\demo_eval_20260711_190204.json',
    encoding='utf-8'
))

fails = [r for r in results if "i'm sorry" in r.get('answer', '').lower() or 'having trouble' in r.get('answer', '').lower()]

print(f'Total failures: {len(fails)}')
print()
for r in fails:
    print(f'#{r["num"]:3d} [{r["lang"]:8s}/{r["category"]:12s}] src={r["source"]:30s} lat={r["latency_ms"]:8.0f}ms')
    print(f'  Q: {r["query"][:80]}')
    print(f'  A: {r["answer"][:200]}')
    print()
