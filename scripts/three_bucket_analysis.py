"""Three-bucket failure classification for v2.1 baseline."""
import json
from pathlib import Path
from collections import Counter, defaultdict

baseline = json.loads(Path('data/benchmark/evaluation/v2.1/pipeline_v1.json').read_text(encoding='utf-8'))
per_conv = baseline['per_conversation']

CONVS_DIR = Path('data/benchmark/conversations')
conv_files = {}
for domain_dir in CONVS_DIR.iterdir():
    if domain_dir.is_dir():
        for fp in domain_dir.glob('BENCH_V21_*.json'):
            conv = json.loads(fp.read_text(encoding='utf-8'))
            conv_files[conv['id']] = conv

# Define semantically equivalent action pairs
# Key = gold action, Value = set of pipeline actions that are acceptable
EQUIVALENT_ACTIONS = {
    'provide_program_info': {
        'provide_distance_ed_info',
        'provide_sports_quota_info',
        'provide_transfer_info',
        'provide_nri_admission_info',
        'provide_lateral_entry_info',
        'provide_admission_guidance',
        'provide_branch_guidance',
        'explain_policy',
    },
    'explain_policy': {
        'explain_management_quota_policy',
        'provide_nri_admission_info',
        'provide_lateral_entry_info',
        'provide_program_info',
    },
    'provide_fee_info': set(),
    'provide_hostel_info': set(),
    'provide_placement_info': set(),
    'provide_scholarship_info': set(),
    'provide_cutoff_info': set(),
    'provide_career_guidance': set(),
    'provide_grievance_process': set(),
    'collect_profile': set(),
    'recommend_branches': set(),
    'reassure': {
        'provide_admission_guidance',
    },
    'provide_admission_guidance': {
        'reassure',
        'provide_program_info',
    },
    'clarify': set(),
    'encourage_and_collect_profile': set(),
    'provide_guidance': set(),
    'escalate_to_human': set(),
}

def is_action_equivalent(gold_action, pipeline_action):
    if gold_action == pipeline_action:
        return True
    equivalents = EQUIVALENT_ACTIONS.get(gold_action, set())
    return pipeline_action in equivalents

# Classify every turn
bucket_a = []  # Intent wrong
bucket_b = []  # Intent correct, action equivalent
bucket_c = []  # Intent correct, action genuinely wrong
bucket_d = []  # Intent correct, action correct (pass)

for conv_id, data in sorted(per_conv.items()):
    gold_conv = conv_files.get(conv_id, {})
    for turn in data.get('turns_detail', []):
        gold_turn = gold_conv.get('turns', [])[turn['turn']]['expected']
        
        entry = {
            'conv': conv_id,
            'turn': turn['turn'],
            'domain': gold_conv.get('domain', '?'),
            'difficulty': gold_conv.get('difficulty', 0),
            'features': gold_conv.get('features', []),
            'expected_intent': turn['expected_intent'],
            'actual_intent': turn['actual_intent'],
            'expected_action': turn['expected_action'],
            'actual_action': turn['actual_action'],
            'student': turn.get('student', '')[:60],
        }
        
        if turn['intent_match'] and turn['action_match']:
            bucket_d.append(entry)
        elif not turn['intent_match']:
            bucket_a.append(entry)
        elif turn['intent_match'] and is_action_equivalent(turn['expected_action'], turn['actual_action']):
            bucket_b.append(entry)
        else:
            bucket_c.append(entry)

total = len(bucket_a) + len(bucket_b) + len(bucket_c) + len(bucket_d)

print('=' * 70)
print('THREE-BUCKET FAILURE CLASSIFICATION')
print('=' * 70)
print()
print(f'  Bucket A — Intent wrong:                          {len(bucket_a):3d} turns ({len(bucket_a)/total:.1%})')
print(f'  Bucket B — Intent correct, action equivalent:     {len(bucket_b):3d} turns ({len(bucket_b)/total:.1%})')
print(f'  Bucket C — Intent correct, action genuinely wrong:{len(bucket_c):3d} turns ({len(bucket_c)/total:.1%})')
print(f'  Bucket D — Everything correct (pass):             {len(bucket_d):3d} turns ({len(bucket_d)/total:.1%})')
print(f'  {"─" * 60}')
print(f'  Total:                                             {total:3d}')
print()

# ── BUCKET A: Intent wrong ──
print('─' * 70)
print(f'BUCKET A: INTENT WRONG ({len(bucket_a)} turns)')
print('─' * 70)

a_by_domain = Counter(e['domain'] for e in bucket_a)
a_confusion = Counter((e['expected_intent'], e['actual_intent']) for e in bucket_a)

print('  By domain:')
for domain, count in a_by_domain.most_common():
    print(f'    {domain:15s} {count:3d}')
print()
print('  Top confusions:')
for (exp, act), count in a_confusion.most_common(10):
    print(f'    {exp:25s} → {act:25s} ({count}x)')
print()

# ── BUCKET B: Equivalent actions ──
print('─' * 70)
print(f'BUCKET B: INTENT CORRECT, ACTION EQUIVALENT ({len(bucket_b)} turns)')
print('─' * 70)
print('  These should NOT count as failures in evaluation.')
print()

b_by_mapping = Counter((e['expected_action'], e['actual_action']) for e in bucket_b)
print('  Equivalent mappings found:')
for (exp, act), count in b_by_mapping.most_common():
    print(f'    {exp:30s} ↔ {act} ({count}x)')
print()

# ── BUCKET C: Genuinely wrong ──
print('─' * 70)
print(f'BUCKET C: INTENT CORRECT, ACTION GENUINELY WRONG ({len(bucket_c)} turns)')
print('─' * 70)

c_by_domain = Counter(e['domain'] for e in bucket_c)
c_confusion = Counter((e['expected_action'], e['actual_action']) for e in bucket_c)

print('  By domain:')
for domain, count in c_by_domain.most_common():
    print(f'    {domain:15s} {count:3d}')
print()
print('  Top confusions:')
for (exp, act), count in c_confusion.most_common(15):
    print(f'    {exp:30s} → {act:30s} ({count}x)')
print()

# ── collect_profile over-triggering ──
collect_profile_wrong = [e for e in bucket_c if e['actual_action'] == 'collect_profile']
print(f'  collect_profile over-triggering: {len(collect_profile_wrong)} turns')
for e in collect_profile_wrong:
    print(f'    {e["conv"]} turn {e["turn"]}: intent={e["expected_intent"]} expected={e["expected_action"]}')
print()

# ── RECALCULATED ACCURACY ──
print('=' * 70)
print('RECALCULATED ACCURACY (with equivalence)')
print('=' * 70)
print()

# Original
orig_intent = len(bucket_d) + len(bucket_b) + len(bucket_c)
orig_action = len(bucket_d)
print(f'  Original intent accuracy:   {orig_intent}/{total} = {orig_intent/total:.1%}')
print(f'  Original action accuracy:   {orig_action}/{total} = {orig_action/total:.1%}')
print(f'  Original turn accuracy:     {len(bucket_d)}/{total} = {len(bucket_d)/total:.1%}')
print()

# With equivalence
new_action = len(bucket_d) + len(bucket_b)
new_turn_intent = len(bucket_d) + len(bucket_b) + len(bucket_c)
print(f'  Adjusted action accuracy:   {new_action}/{total} = {new_action/total:.1%}')
print(f'  Adjusted turn accuracy:     {new_action}/{total} = {new_action/total:.1%}')
print()

# Real failures only
real_failures = len(bucket_a) + len(bucket_c)
print(f'  Real failures (A+C):        {real_failures}/{total} = {real_failures/total:.1%}')
print(f'  Equivalent (B, not real):   {len(bucket_b)}/{total} = {len(bucket_b)/total:.1%}')
print()

# ── PHASE 1 TARGET ──
print('=' * 70)
print('PHASE 1 TARGET: Fix Bucket A (intent wrong)')
print('=' * 70)
print()
print(f'  Bucket A turns: {len(bucket_a)}')
print(f'  If all fixed: intent accuracy → {(orig_intent + len(bucket_a) - len(bucket_a))/total:.1%} (no change, they already count)')
print(f'  But fixing A also fixes cascading action errors in some cases')
print(f'  Net improvement: ~{len(bucket_a)} intent fixes → ~{len(bucket_a) * 0.5:.0f} action fixes')
print()

# List all unique missing intents
missing_intents = set(e['expected_intent'] for e in bucket_a)
print(f'  Missing intents to add: {sorted(missing_intents)}')
