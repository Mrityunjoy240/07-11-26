"""Root-cause analysis of failed benchmark conversations."""
import json
from pathlib import Path
import sys
sys.path.insert(0, '.')
from src.pipeline import PipelineOrchestrator
from src.conversation.state import ConversationState

pipe = PipelineOrchestrator()
results = []

for d in sorted(Path('data/benchmark/conversations').iterdir()):
    if not d.is_dir():
        continue
    for f in sorted(d.glob('BENCH_*.json')):
        data = json.loads(f.read_text(encoding='utf-8'))
        cid = data['id']
        turns = data['turns']
        state = ConversationState(session_id=cid)
        conv_failures = []

        for i, turn in enumerate(turns):
            gold = turn.get('expected', {})
            result = pipe.run(turn['student'], state)

            failures = []

            # Check understanding
            gold_intent = gold.get('understanding', {}).get('intent', '')
            if result.understanding and result.understanding.intent.primary != gold_intent:
                failures.append(f"intent: got '{result.understanding.intent.primary}' want '{gold_intent}'")

            # Check decision
            gold_action = gold.get('decision', {}).get('action', '')
            if result.decision and result.decision.action != gold_action:
                failures.append(f"action: got '{result.decision.action}' want '{gold_action}'")

            if failures:
                conv_failures.append({
                    'turn': i,
                    'student': turn['student'][:80],
                    'failures': failures
                })

        if conv_failures:
            results.append({
                'id': cid,
                'domain': data['domain'],
                'difficulty': data['difficulty'],
                'features': data['features'],
                'turn_failures': conv_failures
            })

# Print analysis
print("=" * 70)
print("ROOT-CAUSE ANALYSIS: 11 FAILED CONVERSATIONS")
print("=" * 70)

# Categorize by failure type
intent_fails = 0
action_fails = 0
both_fails = 0
domain_fails = {}

for r in results:
    domain = r['domain']
    domain_fails[domain] = domain_fails.get(domain, 0) + 1
    for tf in r['turn_failures']:
        types = [f.split(':')[0] for f in tf['failures']]
        if 'intent' in types and 'action' in types:
            both_fails += 1
        elif 'intent' in types:
            intent_fails += 1
        elif 'action' in types:
            action_fails += 1

print(f"\nFailure breakdown:")
print(f"  Intent only: {intent_fails}")
print(f"  Action only: {action_fails}")
print(f"  Both:        {both_fails}")

print(f"\nBy domain:")
for d, c in sorted(domain_fails.items(), key=lambda x: -x[1]):
    print(f"  {d}: {c}")

print(f"\nDetailed failures:")
for r in results:
    print(f"\n--- {r['id']} ({r['domain']}, difficulty {r['difficulty']}, features: {r['features']}) ---")
    for tf in r['turn_failures']:
        print(f"  Turn {tf['turn']}: {tf['student']}")
        for f in tf['failures']:
            print(f"    -> {f}")
