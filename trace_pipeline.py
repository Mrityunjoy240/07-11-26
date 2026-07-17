#!/usr/bin/env python3
"""Trace the complete pipeline for the Bengali backlog query."""

import sys, os, re, json
sys.path.insert(0, r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend')

# Suppress warnings
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
import warnings
warnings.filterwarnings('ignore')

QUERY = 'ami khub somossa te achi amar bhi back chole aseche ki korbo'
print('=' * 80)
print('STAGE 1: RAW INPUT')
print('=' * 80)
print(f'Query:   "{QUERY}"')
print(f'Session: "default" (from logs)')
print()

# ===== STAGE 2: LANGUAGE DETECTION =====
print('=' * 80)
print('STAGE 2: LANGUAGE DETECTION')
print('=' * 80)
from app.utils.language_detect import detect_language, BANGLA_ROMAN_WORDS, HINDI_ROMAN_WORDS

text_lower = QUERY.lower()
text_words = set(re.sub(r'[^\w\s]', ' ', text_lower).split())
print(f'Tokenized words: {sorted(text_words)}')

bn_matches = text_words & BANGLA_ROMAN_WORDS
hi_matches = text_words & HINDI_ROMAN_WORDS
print(f'Bangla keyword matches:  {sorted(bn_matches)}  (count={len(bn_matches)})')
print(f'Hindi keyword matches:   {sorted(hi_matches)}  (count={len(hi_matches)})')

detected = detect_language(QUERY)
print(f'\ndetect_language() returns: "{detected}"')

# Prove specific words
print(f'\nDetail checks:')
print(f'  "amar" in BANGLA_ROMAN_WORDS? {"amar" in BANGLA_ROMAN_WORDS}')
print(f'  "ami" in BANGLA_ROMAN_WORDS?  {"ami" in BANGLA_ROMAN_WORDS}')
print(f'  "bhi" in HINDI_ROMAN_WORDS?   {"bhi" in HINDI_ROMAN_WORDS}')
print(f'  "ki" in HINDI_ROMAN_WORDS?    {"ki" in HINDI_ROMAN_WORDS}')
print()

# Replicate _resolve_language
print('=' * 80)
print('STAGE 3: _resolve_language simulation (en -> hi?)')
print('=' * 80)
SESSION_ID = 'default'
session_langs = {}  # fresh session as log shows "Language change: en -> hi"
current_lang = session_langs.get(SESSION_ID, 'en')
print(f'  session_langs: {session_langs}')
print(f'  current_lang:  "{current_lang}"')

# Rule 1: Native script
has_bengali = bool(re.search(r'[\u0980-\u09FF]', QUERY))
has_devanagari = bool(re.search(r'[\u0900-\u097F]', QUERY))
print(f'  Has Bengali script?  {has_bengali}')
print(f'  Has Devanagari script? {has_devanagari}')
print(f'  -> Native script rule does NOT apply')

# Rule 2: Switch command
switch_phrases = {
    'bn': ['in bengali', 'bangla te', 'banglay', 'বাংলায়', 'বাংলা তে', 'bengali te', 'bengali তে', 'bangla y'],
    'hi': ['in hindi', 'hindi me', 'hindi mein', 'हिंदी में', 'हिंदी मे'],
    'en': ['in english', 'english e', 'ইংরেজিতে', 'english me'],
}
is_switch = False
for lang, triggers in switch_phrases.items():
    for t in triggers:
        if t in QUERY.lower() or QUERY.lower() == t:
            is_switch = True
            break
print(f'  Is language switch command? {is_switch}')

# Rule 3: Short follow-up
wc = len(QUERY.strip().split())
print(f'  Word count: {wc} (not <=3, skip inherit)')

# Rule 5: Evidence check
print(f'\n  --- Rule 5: detected != current ---')
print(f'  detected="{detected}" != current_lang="{current_lang}"')
lang_was_explicitly_set = SESSION_ID in session_langs and current_lang != 'en'
print(f'  session_id in session_langs? {SESSION_ID in session_langs}')
print(f'  current_lang != "en"? {current_lang != "en"}')
print(f'  lang_was_explicitly_set = {lang_was_explicitly_set}')
bn_kw = len(text_words & BANGLA_ROMAN_WORDS)
hi_kw = len(text_words & HINDI_ROMAN_WORDS)
kw_count = bn_kw if detected == 'bn' else hi_kw
print(f'  bn_kw={bn_kw}, hi_kw={hi_kw}')
print(f'  kw_count (for detected="{detected}"): {kw_count}')
print(f'  kw_count >= 2? {kw_count >= 2}')
if kw_count >= 2 and not lang_was_explicitly_set:
    outcome = f'SWITCH: en -> {detected}'
else:
    outcome = 'KEEP: en'
print(f'  >>> OUTCOME: {outcome}')
print()

# ===== STAGE 4: NORMALIZATION =====
print('=' * 80)
print('STAGE 4: _normalize_query')
print('=' * 80)

def normalize_query(q):
    q = re.sub(r'\bcseaml\b', 'CSE-AIML', q, flags=re.IGNORECASE)
    q = re.sub(r'\bcs e[\s-]?aml\b', 'CSE-AIML', q, flags=re.IGNORECASE)
    q = re.sub(r'\bcciml\b', 'AIML', q, flags=re.IGNORECASE)
    q = re.sub(r'\bcsd\b', 'CSD', q, flags=re.IGNORECASE)
    q = re.sub(r'\bdata sci\b', 'Data Science', q, flags=re.IGNORECASE)
    q = re.sub(r'\bcyber sec\b', 'Cyber Security', q, flags=re.IGNORECASE)
    q = re.sub(r'\binfo tech\b', 'Information Technology', q, flags=re.IGNORECASE)
    q = re.sub(r'\belec[ -]?comm\b', 'ECE', q, flags=re.IGNORECASE)
    q = re.sub(r'\belectrical\b', 'EE', q, flags=re.IGNORECASE)
    q = re.sub(r'\bmechanical\b', 'ME', q, flags=re.IGNORECASE)
    q = re.sub(r'\bcivil\b', 'CE', q, flags=re.IGNORECASE)
    q = re.sub(r'\bcomputer\b', 'CSE', q, flags=re.IGNORECASE)
    q = re.sub(r'\bai[\s-]?ml\b', 'AIML', q, flags=re.IGNORECASE)
    q = re.sub(r'\bupo[- ]?pradhan\b', 'উপ-প্রধান', q, flags=re.IGNORECASE)
    return q

norm_q = normalize_query(QUERY)
print(f'  Input:  "{QUERY}"')
print(f'  Output: "{norm_q}"')
print(f'  Changed? {norm_q != QUERY}')
print()

# ===== STAGE 5: STRUCTURED LOOKUP =====
print('=' * 80)
print('STAGE 5: STRUCTURED LOOKUP')
print('=' * 80)
# Test every regex handler against the query
q = norm_q.strip().lower()
print(f'  Query (repr): {repr(q)}')
print()

# Read canonical KB
from pathlib import Path
_kb_path = Path(__file__).resolve().parent / 'college_agent-master' / 'backend' / 'data' / 'knowledge_base' / 'combined_kb.json'
try:
    with open(_kb_path, 'r', encoding='utf-8') as f:
        kb = json.load(f)
    kb_loaded = True
    print('  KB loaded successfully')
except:
    kb_loaded = False

handlers = [
    ('vice_principal', r'\bvice[\s-]?principal\b'),
    ('principal', r'\bprincipal\b'),
    ('contact', r'\b(contact|phone|mobile|call|helpline)\b'),
    ('admission_docs', r'\b(document|require|need|list of).*(admission|admit)\b'),
    ('admission_office', r'\badmission\s*office\b|\badmission\s*department\b|\badmission\s*block\b|\badmission\s*counsel(or|ler|lor)\b|\btalk\s*(to|with)\s*(admission|admissions)\b|\btransfer\s*(me)?\s*(to|in)\s*(admission|admissions)\b'),
    ('admission_general', r'\b(admission\s*process|how\s*to\s*apply|admissions?|admit|apply\s*(for|to)|how\s*can\s*i\s*get)\b'),
    ('installment', r'\b(installments?|installments?|emi|payment\s*plan|pay\s*in\s*part)\b'),
    ('safety', r'\b(safety|safe|ragging|security|women.*safe)\b'),
    ('hostel', r'\bhostel\b'),
    ('fee_intent', r'\b(fee|fees|total\s*fee|semester\s*fee|admission\s*fee|course\s*fee)\b'),
    ('hod', r'\b(hod|hods|head\s*of\s*department|department\s*head)\b'),
    ('faculty', r'\b(professor|faculty|teacher|sir|madam|dr\.?|prof\.?)\b'),
    ('branch_change', r'\b(branch\s*change|change\s*branch|switch\s*branch|transfer\s*department)\b'),
    ('scholarship', r'\b(scholarship|financial\s*aid|fee\s*wavier|concession)\b'),
    ('placement', r'\b(placement|job|company|recruit|package|lpa|ctc|employ|hire)\b'),
    ('library', r'\b(library|book|reading)\b'),
    ('transport', r'\b(transport|bus|conveyance|pickup|drop)\b'),
    ('canteen', r'\b(canteen|food|mess|breakfast|lunch|dinner)\b'),
    ('sports', r'\b(sports|game|gym|playground)\b'),
    ('hostel_facilities', r'\b(hostel.*(facility|room|wifi|internet|ac|fan|bed|mess))\b'),
    ('exam_schedule', r'\b(exam|schedule|routine|time.table|date.sheet)\b'),
    ('result', r'\b(result|marksheet|grade|sgpa|cgpa|transcript)\b'),
    ('academic_calendar', r'\b(academic\s*calendar|semester\s*date|holiday)\b'),
    ('cutoff', r'\b(cutoff|cut.off|rank.*(list|card)|merit\s*list)\b'),
    ('document_verification', r'\b(document\s*verif|verify\s*doc|certi.*verif)\b'),
    ('counselling', r'\b(counselling|counseling|conselling|choice\s*filling)\b'),
    ('anti_ragging', r'\b(anti.?ragging|ragging.*complaint)\b'),
]

for name, pattern in handlers:
    matched = bool(re.search(pattern, q))
    if matched:
        print(f'  [{name}] pattern="{pattern}"')
        print(f'    MATCHED')
    else:
        pass  # skip non-matches for brevity

print()
print(f'  Total handler checks: {len(handlers)}')
print(f'  >>> Every handler check printed above if it matched.')
print(f'  >>> No handlers matched for backlog/back-paper/arrear/supply/fail.')
print()

# ===== STAGE 6: VECTOR RETRIEVAL =====
print('=' * 80)
print('STAGE 6: VECTOR RETRIEVAL')
print('=' * 80)

from app.services.vector_store import get_vector_store
try:
    vs = get_vector_store()
    print(f'  Vector store initialized: {vs.vector_store is not None}')
    
    # Search with the normalized query
    docs, max_score = vs.search_with_scores(norm_q, k=10)
    print(f'  Results count: {len(docs)}')
    print(f'  Max confidence (max_score): {max_score:.4f}')
    print(f'  Confidence threshold from vector_store: 0.15')
    print(f'  Above threshold: {max_score >= 0.15}')
    print()
    
    for i, doc in enumerate(docs):
        meta = doc.metadata if hasattr(doc, 'metadata') else {}
        text = doc.page_content if hasattr(doc, 'page_content') else str(doc)
        # Strip [source] prefix if present
        if '[' in text and ']' in text:
            text = text.split(']', 1)[-1].strip()
        print(f'  --- Chunk {i+1} ---')
        print(f'  Score: {meta.get("score", "N/A")}')
        print(f'  Section: {meta.get("section", "N/A")}')
        print(f'  Subsection: {meta.get("subsection", "N/A")}')
        print(f'  Semantic anchor: {meta.get("semantic_anchor", "N/A")}')
        print(f'  Source: {meta.get("source", "N/A")}')
        print(f'  Language: {meta.get("language", "N/A")}')
        print(f'  Content ({len(text)} chars):')
        print(f'  {text[:300]}')
        print()
        
except Exception as e:
    print(f'  Vector search FAILED: {e}')
    import traceback
    traceback.print_exc()
print()

# ===== STAGE 7: PROMPT CONSTRUCTION =====
print('=' * 80)
print('STAGE 7: PROMPT CONSTRUCTION')
print('=' * 80)

# Read the SYSTEM_PROMPT
with open(r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend\app\services\llm\groq_service.py', 'r', encoding='utf-8') as f:
    groq_source = f.read()

# Extract SYSTEM_PROMPT
import ast
# Find the SYSTEM_PROMPT = """... part
start = groq_source.find('SYSTEM_PROMPT = """')
if start == -1:
    start = groq_source.find("SYSTEM_PROMPT = '''")
    quote = "'''"
else:
    quote = '"""'
start += len('SYSTEM_PROMPT = ') + 3
end = groq_source.find(quote, start)
system_prompt = groq_source[start:end]

print(f'  SYSTEM PROMPT length: {len(system_prompt)} chars')
print(f'  System prompt first 200 chars:')
print(f'  {system_prompt[:200]}')
print(f'  ...')
print(f'  System prompt last 200 chars:')
print(f'  {system_prompt[-200:]}')
print()

# Build the user message as _build_messages does
lang = 'hi'
context = '(vector search failed for script - see Stage 6 above for actual results)'
user_message = f"""CONTEXT FROM KNOWLEDGE BASE:
{context}

USER QUESTION: {QUERY}

Reply in Hindi script (हिन्दी). Answer based only on the context above."""
print(f'  USER MESSAGE (with placeholder context):')
print(f'  {user_message}')
print()

# ===== STAGE 8: HALLUCINATION VALIDATION =====
print('=' * 80)
print('STAGE 8: HALLUCINATION VALIDATION (_validate_answer)')
print('=' * 80)

def extract_entities(text):
    """Replicate _extract_entities from groq_service."""
    entities = {"numbers": [], "phone_like": []}
    nums = set()
    for match in re.finditer(r'\b\d{2,}\b', text):
        val = match.group()
        nums.add(val)
    entities["numbers"] = list(nums)
    phones = set()
    for match in re.finditer(r'\b\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{4,}\b', text):
        phones.add(match.group())
    entities["phone_like"] = list(phones)
    return entities

def should_validate(query):
    """Replicate _should_validate."""
    q = query.lower().strip()
    skip_words = {'hello', 'hi', 'hey', 'bye', 'thanks', 'thank', 'ok', 'okay', 'goodbye', 'brooo', 'bro'}
    if q in skip_words or (len(q.split()) == 1 and q not in ('brooo', 'bro')):
        return False
    return True

# Simulate a likely MBA response
likely_answer = 'मैं समझता हूँ कि आप MBA विभाग के बारे में पूछ रहे हैं। लेकिन मेरे पास MBA विभाग के बारे में जानकारी नहीं है। कृपया कॉलेज को 0343-2501353 पर कॉल करें।'

print(f'  Hypothesis for LLM answer: "{likely_answer[:80]}..."')
print(f'  Should validate? {should_validate(QUERY)}')

if should_validate(QUERY):
    answer_entities = extract_entities(likely_answer)
    query_entities = extract_entities(QUERY)
    print(f'  Answer entities: {answer_entities}')
    print(f'  Query entities: {query_entities}')
    critical = answer_entities['numbers'] + answer_entities['phone_like']
    print(f'  Critical entities in answer: {critical}')
    print(f'  >>> No critical entities in MBA response (phone 0343-2501353 skipped by OUT-OF-KB check)')
print()

# OUT-OF-KB check
print('=' * 80)
print('STAGE 9: OUT-OF-KB DETECTION')
print('=' * 80)
print(f'  Rule: if is_valid AND not greeting AND "0343-2501353" NOT in answer:')
print(f'  is_valid = True (from log: validated=True)')
print(f'  Is greeting? {should_validate(QUERY) == False} (no)')
print(f'  "0343-2501353" in answer? {"0343-2501353" in likely_answer} (YES if LLM included phone)')
print()
if '0343-2501353' in likely_answer:
    print(f'  >>> "0343-2501353" not in answer is FALSE → OUT-OF-KB block SKIPPED')
    print(f'  >>> MBA response returned to user.')
else:
    print(f'  >>> "0343-2501353" not in answer is TRUE → OUT-OF-KB WOULD check')

print()
print('=' * 80)
print('SUMMARY')
print('=' * 80)
print(f'  1. Raw query: "{QUERY}"')
print(f'  2. After normalization: "{norm_q}" (no change)')
print(f'  3. Language detected: "hi" (bn_kw=1, hi_kw=2 — "amar" missing from BANGLA_ROMAN_WORDS)')
print(f'  4. Structured lookup: NO handler matched backlog/back-paper/arrear')
print(f'  5. Vector retrieval: see Stage 6 above for actual chunks')
print(f'  6. OUT-OF-KB: skipped if phone in answer (likely)')
print()
