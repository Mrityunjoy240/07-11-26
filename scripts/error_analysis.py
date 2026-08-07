"""Phase A: Forensic error analysis of v2.1 baseline failures."""
import json
from pathlib import Path
from collections import Counter, defaultdict

baseline = json.loads(Path('data/benchmark/evaluation/v2.1/pipeline_v1.json').read_text(encoding='utf-8'))
per_conv = baseline['per_conversation']

# Load all conversation gold data
CONVS_DIR = Path('data/benchmark/conversations')
conv_files = {}
for domain_dir in CONVS_DIR.iterdir():
    if domain_dir.is_dir():
        for fp in domain_dir.glob('BENCH_V21_*.json'):
            conv = json.loads(fp.read_text(encoding='utf-8'))
            conv_files[conv['id']] = conv

# Collect all failures
all_turns = []
for conv_id, data in sorted(per_conv.items()):
    for turn in data.get('turns_detail', []):
        gold = conv_files.get(conv_id, {}).get('turns', [])[turn['turn']]['expected']
        all_turns.append({
            'conv': conv_id,
            'turn_idx': turn['turn'],
            'expected_intent': turn['expected_intent'],
            'actual_intent': turn['actual_intent'],
            'intent_match': turn['intent_match'],
            'expected_action': turn['expected_action'],
            'actual_action': turn['actual_action'],
            'action_match': turn['action_match'],
            'domain': conv_files.get(conv_id, {}).get('domain', '?'),
            'difficulty': conv_files.get(conv_id, {}).get('difficulty', 0),
            'features': conv_files.get(conv_id, {}).get('features', []),
            'stage': gold.get('reasoning', {}).get('stage', '?'),
            'profile_completeness': gold.get('reasoning', {}).get('profile_completeness', 0),
        })

total_turns = len(all_turns)
failed_turns = [t for t in all_turns if not t['intent_match'] or not t['action_match']]
failed_convs = set(t['conv'] for t in failed_turns)

print('=' * 70)
print('PHASE A: FORENSIC ERROR ANALYSIS')
print('=' * 70)
print()
print(f'Total turns: {total_turns}')
print(f'Turns with any error: {len(failed_turns)} ({len(failed_turns)/total_turns:.1%})')
print(f'Failed conversations: {len(failed_convs)}/50')
print()

# ── FAILURE TYPE 1: Intent vs Action ──
print('─' * 70)
print('FAILURE TYPE BREAKDOWN (per-turn)')
print('─' * 70)

intent_only = [t for t in failed_turns if not t['intent_match'] and t['action_match']]
action_only = [t for t in failed_turns if t['intent_match'] and not t['action_match']]
both = [t for t in failed_turns if not t['intent_match'] and not t['action_match']]

print(f'  Wrong intent (action may or may not match gold):  {len(intent_only)} turns')
print(f'  Wrong action only (intent correct):                {len(action_only)} turns')
print(f'  Both wrong:                                        {len(both)} turns')
print()

# ── INTENT CONFUSION MATRIX ──
print('─' * 70)
print('INTENT CONFUSION (top confused pairs)')
print('─' * 70)

intent_errors = [t for t in failed_turns if not t['intent_match']]
confusion = Counter()
for t in intent_errors:
    confusion[(t['expected_intent'], t['actual_intent'])] += 1

for (exp, act), count in confusion.most_common(15):
    print(f'  {exp:25s} → {act:25s}  ({count}x)')
print()

# ── ACTION CONFUSION MATRIX ──
print('─' * 70)
print('ACTION CONFUSION (top confused pairs)')
print('─' * 70)

action_errors = [t for t in failed_turns if not t['action_match']]
action_confusion = Counter()
for t in action_errors:
    action_confusion[(t['expected_action'], t['actual_action'])] += 1

for (exp, act), count in action_confusion.most_common(15):
    print(f'  {exp:30s} → {act:30s}  ({count}x)')
print()

# ── FAILURE BY DOMAIN ──
print('─' * 70)
print('FAILURE RATE BY DOMAIN')
print('─' * 70)

domain_total = Counter()
domain_fail = Counter()
for t in all_turns:
    domain_total[t['domain']] += 1
for t in failed_turns:
    domain_fail[t['domain']] += 1

for domain in sorted(domain_total.keys()):
    total = domain_total[domain]
    fail = domain_fail[domain]
    rate = fail / total if total else 0
    bar = '█' * int(rate * 30)
    print(f'  {domain:15s} {fail:3d}/{total:3d} ({rate:.0%}) {bar}')
print()

# ── FAILURE BY DIFFICULTY ──
print('─' * 70)
print('FAILURE RATE BY DIFFICULTY')
print('─' * 70)

diff_total = Counter()
diff_fail = Counter()
for t in all_turns:
    diff_total[t['difficulty']] += 1
for t in failed_turns:
    diff_fail[t['difficulty']] += 1

for diff in sorted(diff_total.keys()):
    total = diff_total[diff]
    fail = diff_fail[diff]
    rate = fail / total if total else 0
    bar = '█' * int(rate * 30)
    print(f'  Difficulty {diff}  {fail:3d}/{total:3d} ({rate:.0%}) {bar}')
print()

# ── FAILURE BY FEATURE ──
print('─' * 70)
print('FAILURE RATE BY FEATURE')
print('─' * 70)

feat_total = Counter()
feat_fail = Counter()
for t in all_turns:
    for f in t['features'] or ['(none)']:
        feat_total[f] += 1
for t in failed_turns:
    for f in t['features'] or ['(none)']:
        feat_fail[f] += 1

for feat in sorted(feat_total.keys()):
    total = feat_total[feat]
    fail = feat_fail[feat]
    rate = fail / total if total else 0
    bar = '█' * int(rate * 30)
    print(f'  {feat:18s} {fail:3d}/{total:3d} ({rate:.0%}) {bar}')
print()

# ── FAILURE BY REASONING STAGE ──
print('─' * 70)
print('FAILURE RATE BY REASONING STAGE')
print('─' * 70)

stage_total = Counter()
stage_fail = Counter()
for t in all_turns:
    stage_total[t['stage']] += 1
for t in failed_turns:
    stage_fail[t['stage']] += 1

for stage in sorted(stage_total.keys()):
    total = stage_total[stage]
    fail = stage_fail[stage]
    rate = fail / total if total else 0
    bar = '█' * int(rate * 30)
    print(f'  {stage:18s} {fail:3d}/{total:3d} ({rate:.0%}) {bar}')
print()

# ── ACTION MAPPING GAPS ──
print('─' * 70)
print('ACTION ROUTING: CORRECT INTENT BUT WRONG ACTION')
print('─' * 70)

action_only_and_both = [t for t in failed_turns if not t['action_match']]
routing_gaps = Counter()
for t in action_only_and_both:
    routing_gaps[(t['expected_intent'], t['expected_action'], t['actual_action'])] += 1

for (intent, exp_act, act_act), count in routing_gaps.most_common(20):
    print(f'  intent={intent:22s} expected={exp_act:30s} got={act_act}')
print(f'  ... total routing failures: {len(action_only_and_both)}')
print()

# ── SUMMARY TABLE ──
print('=' * 70)
print('SUMMARY: FAILURE TAXONOMY')
print('=' * 70)

total_fail_turns = len(failed_turns)
intent_fail = len(intent_only) + len(both)
action_fail_after_correct_intent = len(action_only)
action_fail_after_wrong_intent = len(both)
planner_fail = 0  # Would need deeper analysis
memory_fail = 0
retrieval_fail = 0

print(f'')
print(f'  Category                          Turns    % of failures')
print(f'  {"─" * 55}')
print(f'  Intent classification error       {intent_fail:4d}     {intent_fail/total_fail_turns:.1%}')
print(f'  Action routing (correct intent)   {action_fail_after_correct_intent:4d}     {action_fail_after_correct_intent/total_fail_turns:.1%}')
print(f'  Both intent + action wrong        {len(both):4d}     {len(both)/total_fail_turns:.1%}')
print(f'  {"─" * 55}')
print(f'  TOTAL                             {total_fail_turns:4d}')
print()
print(f'  HIGHEST LEVERAGE FIX:')
if action_fail_after_correct_intent >= intent_fail:
    print(f'  → Decision engine (action routing): {action_fail_after_correct_intent} turns')
    print(f'    Intent is correct but action is wrong.')
    print(f'    Fixing this alone could recover {action_fail_after_correct_intent} turns.')
else:
    print(f'  → Understanding (intent classification): {intent_fail} turns')
    print(f'    Wrong intent cascades to wrong action.')
