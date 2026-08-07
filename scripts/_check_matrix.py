import json

m = json.load(open('data/benchmark/coverage/v2.1_matrix.json', encoding='utf-8'))
slots = m['v2_1_planned']['conversation_slots']

all_intents = set()
all_actions = set()
all_domains = set()
all_features = set()
diffs = {}
langs = {}
stages = set()
multi = 0

for s in slots:
    all_intents.add(s['primary_intent'])
    all_actions.add(s['primary_action'])
    all_domains.add(s['domain'])
    for f in s['features']:
        all_features.add(f)
    d = s['difficulty']
    diffs[d] = diffs.get(d, 0) + 1
    l = s['primary_language']
    langs[l] = langs.get(l, 0) + 1
    for st in s['reasoning_stages']:
        stages.add(st)
    if s['turns'] > 1:
        multi += 1

expected_intents = {
    'fee', 'admission', 'placement', 'hostel', 'scholarship', 'department',
    'contact', 'cutoff', 'seats', 'faculty', 'hod', 'safety', 'timings',
    'repeat', 'greeting', 'sports_quota', 'transfer', 'distance_education',
    'grievance', 'counseling_info', 'career_confusion', 'lateral_entry',
    'management_quota', 'nri_admission', 'unknown', 'recommendation', 'loan', 'document'
}
expected_actions = {
    'collect_profile', 'encourage_and_collect_profile', 'recommend_branches',
    'provide_admission_guidance', 'provide_fee_info', 'provide_placement_info',
    'provide_hostel_info', 'provide_scholarship_info', 'provide_cutoff_info',
    'provide_branch_guidance', 'reassure', 'clarify', 'provide_guidance',
    'provide_distance_ed_info', 'provide_nri_admission_info',
    'explain_management_quota_policy', 'provide_grievance_process',
    'provide_transfer_info', 'provide_sports_quota_info',
    'provide_career_guidance', 'provide_counseling_schedule',
    'provide_lateral_entry_info'
}

missing_intents = expected_intents - all_intents
missing_actions = expected_actions - all_actions
extra_intents = all_intents - expected_intents
extra_actions = all_actions - expected_actions

print(f"Total conversations: {len(slots)}")
total_turns = sum(s['turns'] for s in slots)
print(f"Total turns: {total_turns}")
print(f"Domains: {len(all_domains)}")
print(f"Multi-turn: {multi}/{len(slots)} = {multi/len(slots):.0%}")
print()
print(f"Intent coverage: {len(all_intents & expected_intents)}/{len(expected_intents)}")
if missing_intents:
    print(f"  MISSING: {missing_intents}")
if extra_intents:
    print(f"  EXTRA (new): {extra_intents}")
print()
print(f"Action coverage: {len(all_actions & expected_actions)}/{len(expected_actions)}")
if missing_actions:
    print(f"  MISSING: {missing_actions}")
if extra_actions:
    print(f"  EXTRA (new): {extra_actions}")
print()
print(f"Difficulty: {dict(sorted(diffs.items()))}")
print(f"Languages: {langs}")
print(f"Reasoning stages: {sorted(stages)}")
print(f"Features: {sorted(all_features)}")

# Check targets
print()
print("--- TARGET CHECKS ---")
targets = m['targets']
print(f"Conversations >= {targets['conversations']}: {len(slots)} {'PASS' if len(slots) >= targets['conversations'] else 'FAIL'}")
print(f"Turns 120-180: {total_turns} {'PASS' if 120 <= total_turns <= 180 else 'FAIL'}")
print(f"Domains >= {targets['domains_min']}: {len(all_domains)} {'PASS' if len(all_domains) >= targets['domains_min'] else 'FAIL'}")
print(f"Intent coverage 100%: {len(missing_intents) == 0} {'PASS' if len(missing_intents) == 0 else 'FAIL'}")
print(f"Action coverage 100%: {len(missing_actions) == 0} {'PASS' if len(missing_actions) == 0 else 'FAIL'}")
print(f"Multi-turn >= 60%: {multi/len(slots):.0%} {'PASS' if multi/len(slots) >= 0.6 else 'FAIL'}")
