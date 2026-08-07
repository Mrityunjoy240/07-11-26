"""
Failure Triage: Classify every remaining failed turn.

Reads the latest baseline + all gold conversation files.
Outputs a table classifying each failure into:
  - Pipeline: implementation bug in understanding/reasoning/decision/planner
  - Gold: benchmark annotation contradicts pipeline logic or itself
  - Ontology: vocabulary mismatch (action equivalence)
  - Product: pipeline behavior is a deliberate design choice
"""
import json
from pathlib import Path

BASELINE = Path('data/benchmark/evaluation/v2.1/pipeline_v1.json')
CONVS_DIR = Path('data/benchmark/conversations')

baseline = json.loads(BASELINE.read_text(encoding='utf-8'))

FAILED_CONVS = set()
for conv_id, data in baseline['per_conversation'].items():
    for t in data.get('turns_detail', []):
        if not t['action_match'] or not t['intent_match']:
            FAILED_CONVS.add(conv_id)

print(f'Total failed conversations: {len(FAILED_CONVS)}')
print(f'Failed: {sorted(FAILED_CONVS)}')
print()

# Load all gold conversations
GOLDS = {}
for fp in CONVS_DIR.rglob('*.json'):
    cid = fp.stem
    GOLDS[cid] = json.loads(fp.read_text(encoding='utf-8'))

def classify(conv_id, turn_num, ei, ai, ea, aa, gold_turn, gold, full_trace=None):
    """
    Returns (category, reason_sentence).
    Categories: Pipeline, Gold, Ontology, Product
    """
    student_text = gold_turn['student']
    exp = gold_turn.get('expected', {})
    gold_reasoning = exp.get('reasoning', {})
    gold_decision = exp.get('decision', {})
    gold_brain = exp.get('brain', {})
    gold_intent = exp.get('understanding', {}).get('intent', '?')
    gold_problem = gold_reasoning.get('current_problem', '?')
    gold_completeness = gold_reasoning.get('profile_completeness', 0.0)
    gold_eligible = gold_brain.get('eligible_branches', [])
    gold_applicable = gold_brain.get('applicable', False)

    # =========================================================
    # 1. INTENT MISMATCH
    # =========================================================
    if ei != ai:
        # a) If the gold intent contradicts what the text says
        # Check if the text clearly matches a different intent pattern
        txt_lower = student_text.lower()

        if ai == 'unknown' and ei != 'unknown':
            return ('Pipeline', f'Pipeline failed to detect any intent for text that is clearly about "{ei}"')

        if ai == 'fee' and ei == 'admission':
            # Check if the text is about profile/greetings
            if any(w in txt_lower for w in ['hello', 'hi', 'thank', 'general', 'category']):
                return ('Gold', f'Gold says intent=admission for a profile/thank-you statement; pipeline says fee (context-dependent)')
            return ('Pipeline', f'Pipeline misclassifies admission text as fee')

        if ai == 'fee' and ei == 'scholarship':
            if 'concession' in txt_lower:
                return ('Pipeline', f'Pipeline still classifies "concession" text as fee instead of scholarship (concession moved to fee pattern)')
            return ('Gold', f'Gold says intent=scholarship for text about fee')

        if ai == 'scholarship' and ei == 'fee':
            return ('Pipeline', f'Pipeline classifies fee text as scholarship')

        if ai == 'admission' and ei == 'cutoff':
            return ('Pipeline', f'Pipeline classifies cutoff text as admission')

        if ai == 'transfer' and ei == 'lateral_entry':
            return ('Ontology', f'lateral_entry → transfer is an ontology merge; equivalence mapping needed')

        if ai == 'admission' and ei == 'department':
            return ('Pipeline', f'Pipeline classifies department text as admission')

        if ai == 'admission' and ei == 'document':
            return ('Pipeline', f'Pipeline classifies document text as admission')

        if ai == 'admission' and ei == 'safety':
            return ('Pipeline', f'Pipeline classifies safety text as admission')

        if ai == 'admission' and ei == 'career_confusion':
            return ('Pipeline', f'Pipeline classifies career_confusion as admission')

        if ai == 'contact' and ei == 'institution':
            return ('Pipeline', f'Pipeline classifies institution text as contact')

        if ai == 'admission' and ei == 'unknown':
            return ('Pipeline', f'Pipeline sees admission where text is unintelligible')

        return ('Pipeline', f'Intent mismatch: expected={ei} actual={ai}')

    # =========================================================
    # 2. ACTION MISMATCH
    # =========================================================
    if ea != aa:
        # 2a: Gold label self-consistency check
        completeness = gold_completeness
        problem = gold_problem

        # Check if gold action contradicts Step 3 gate
        if problem == 'needs_admission_guidance' and completeness is not None and completeness < 0.3:
            if ea == 'provide_guidance':
                return ('Gold', f'Problem={problem} + completeness={completeness} < 0.3 → Step 3 forces collect_profile, gold expects {ea}. Gold is inconsistent with itself.')
            if ea == 'encourage_and_collect_profile':
                return ('Gold', f'Problem={problem} + completeness={completeness} < 0.3 → Step 3 forces collect_profile, gold expects {ea}. Gold inconsistent.')
            if ea == 'reassure':
                return ('Gold', f'Problem={problem} + completeness={completeness} < 0.3 → Step 3 forces collect_profile, gold expects {ea}. Gold inconsistent.')

        # Check if gold action contradicts completeness fallback for unknown problem
        if problem not in ('needs_profile_initial', 'needs_profile_completion',
                           'needs_personalized_guidance', 'needs_admission_guidance',
                           'needs_branch_guidance', 'needs_fee_information',
                           'needs_placement_information', 'needs_hostel_information',
                           'needs_scholarship_information', 'needs_cutoff_information',
                           'needs_reassurance', 'needs_clarification',
                           'needs_institution_info', 'needs_seat_info', 'needs_loan_info',
                           'needs_document_info', 'needs_safety_info', 'needs_career_guidance'):
            # Unknown problem → falls through to completeness
            if completeness is not None and completeness < 0.3:
                return ('Gold', f'Unknown problem "{problem}" → completeness={completeness} < 0.3 → needs_profile_initial → collect_profile. Gold expects {ea}. Benchmark bug.')

        # 2b: Brain override logic check
        # expected action = recommend_branches but pipeline doesn't fire brain override
        if ea == 'recommend_branches' and aa != 'recommend_branches':
            if not gold_eligible:
                return ('Gold', f'Gold expects recommend_branches but eligible_branches=[]. Brain override requires non-empty eligible_branches. Benchmark bug.')
            if completeness is not None and completeness < 0.5:
                return ('Gold', f'Gold expects recommend_branches but completeness={completeness} < 0.5. Brain override requires >=0.5. Benchmark bug.')
            if 'counseling' in student_text.lower():
                return ('Product', f'counseling in text blocks brain override via _has_empathy_context. Gold expects recommend_branches. This is a product decision.')
            # Otherwise it's a pipeline issue
            return ('Pipeline', f'Brain override should fire (eligible={gold_eligible}, completeness>=0.5) but pipeline produces {aa} instead of recommend_branches')

        # 2c: collect_profile over-triggering
        if aa == 'collect_profile' and ea != 'collect_profile':
            if problem == 'needs_admission_guidance' and completeness is not None and completeness < 0.3:
                return ('Pipeline', f'Step 3 gate: problem={problem} + completeness={completeness} < 0.3 forces collect_profile. Gold expects {ea}. The gate is correct per product policy.')
            return ('Pipeline', f'collect_profile over-triggering: pipeline collects profile when gold expects {ea}')

        # 2d: Action equivalence / vocabulary
        equiv_groups = {
            ('provide_program_info', 'provide_counseling_schedule'),
            ('provide_program_info', 'provide_lateral_entry_info'),
            ('provide_program_info', 'provide_distance_ed_info'),
            ('provide_program_info', 'provide_sports_quota_info'),
            ('provide_program_info', 'provide_grievance_process'),
            ('explain_policy', 'explain_management_quota_policy'),
            ('explain_policy', 'provide_nri_admission_info'),
            ('explain_policy', 'provide_transfer_info'),
            ('explain_policy', 'provide_lateral_entry_info'),
            ('reassure', 'provide_admission_guidance'),
        }
        if (ea, aa) in equiv_groups or (aa, ea) in equiv_groups:
            return ('Ontology', f'Action equivalence: {ea} ↔ {aa}. Extend equivalence mapping.')

        # 2e: admission_info vs admission_guidance
        if ea == 'provide_admission_info' and aa == 'provide_admission_guidance':
            return ('Ontology', f'provide_admission_info vs provide_admission_guidance — same semantics, different naming.')

        # 2f: Gold expects a specific action that pipeline produces differently
        if ea == 'provide_counseling_schedule' and aa != 'provide_counseling_schedule':
            return ('Pipeline', f'Pipeline should produce provide_counseling_schedule for counseling intent but produces {aa}')

        # 2g: Reassure vs something else
        if ea == 'reassure' and aa != 'reassure':
            if completeness is not None and completeness < 0.3:
                return ('Pipeline', f'Anxiety/confidence signal not detected strongly enough. Pipeline produces {aa} instead of reassure.')

        # 2h: Fallback: check if problem is correctly identified
        if problem not in ('needs_profile_initial', 'needs_profile_completion', 'needs_personalized_guidance'):
            # Problem is known but pipeline doesn't produce gold action
            return ('Pipeline', f'Pipeline produces {aa} instead of gold action {ea} for problem "{problem}"')

        return ('Pipeline', f'Action mismatch: expected={ea} actual={aa}. Problem={problem}, completeness={completeness}')

    return ('Pass', '')


# Build results
results = []
for conv_id in sorted(FAILED_CONVS):
    gold = GOLDS.get(conv_id, {})
    conv_data = baseline['per_conversation'].get(conv_id, {})
    for t in conv_data.get('turns_detail', []):
        tn = t['turn']
        ei = t['expected_intent']
        ai = t['actual_intent']
        ea = t['expected_action']
        aa = t['actual_action']
        im = t['intent_match']
        am = t['action_match']

        gold_turn = gold.get('turns', [{}])[tn] if gold.get('turns') else {}
        student_text = gold_turn.get('student', '?')[:80]

        if im and am:
            continue  # Pass

        cat, reason = classify(conv_id, tn, ei, ai, ea, aa, gold_turn, gold)
        results.append((conv_id, tn, cat, reason, ei, ai, ea, aa, student_text))


# Print summary
categories = {}
for r in results:
    cat = r[2]
    categories[cat] = categories.get(cat, 0) + 1

print('=' * 80)
print('FAILURE TRIAGE SUMMARY')
print('=' * 80)
for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
    print(f'  {cat}: {count}')

print()
print('=' * 80)
print('DETAILED CLASSIFICATION')
print('=' * 80)

by_conv = {}
for r in results:
    conv_id = r[0]
    if conv_id not in by_conv:
        by_conv[conv_id] = []
    by_conv[conv_id].append(r)

for conv_id in sorted(by_conv.keys()):
    conv_results = by_conv[conv_id]
    gold = GOLDS.get(conv_id, {})
    domain = gold.get('domain', '?')
    print(f'\n{conv_id} (domain={domain}):')
    for tn, conv_id, cat, reason, ei, ai, ea, aa, student_text in conv_results:
        print(f'  Turn {tn}: [{cat}] {reason}')
        print(f'           text="{student_text}"')
        print(f'           intent: {ei}→{ai}  action: {ea}→{aa}')
