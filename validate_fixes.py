#!/usr/bin/env python3
"""
Full validation suite for the 12 specified queries.
Tests: language detection, normalization, query expansion, structured handler, vector retrieval.
"""
import sys, os, re, json
sys.path.insert(0, r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend')
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
import warnings
warnings.filterwarnings('ignore')

from app.utils.language_detect import detect_language
from app.services.vector_store import VectorStoreService

# Load the actual normalization patterns from groq_service
_BANGLISH_SYNONYMS = [
    (r'\bback\s+chole\s+aseche\b', 'backlog'),
    (r'\bback\s+as(?:che|e)\b', 'backlog'),
    (r'\bback\s+hoyeche\b', 'backlog'),
    (r'\bback\s+lag(?:be|se)\b', 'backlog'),
    (r'\bback\s+ache\b', 'backlog'),
    (r'\bsem(?:ester)?\s+back\b', 'backlog failed semester'),
    (r'\bresult.*back\b', 'backlog'),
    (r'\bback\s+paper\b', 'backlog supplementary exam'),
    (r'\bfyel\b', 'fail'),
]

_ACADEMIC_FAILURE_EXPANSION = "fail semester backlog supplementary exam reappear"
_ACADEMIC_FAILURE_TRIGGER = re.compile(
    r'\b(backlog|fail|supplementary|arrear|back\s+paper|reappear)\b',
    re.IGNORECASE,
)

# Structured handler patterns (same as added to _structured_lookup)
_ACADEMIC_FAILURE_PATTERN = re.compile(
    r'\b(backlog|back.?paper|arrear|supply|supplementary|reappear|fail)'
    r'|back\s+(ache|hoyeche|lag|lagbe|lagse|chole|as)',
    re.IGNORECASE,
)

def normalize(q):
    for pat, repl in _BANGLISH_SYNONYMS:
        q = re.sub(pat, repl, q, flags=re.IGNORECASE)
    return q

def expand(normalized):
    if _ACADEMIC_FAILURE_TRIGGER.search(normalized):
        return f"{normalized} {_ACADEMIC_FAILURE_EXPANSION}"
    return normalized

def structured_match(q):
    ql = q.strip().lower()
    return bool(_ACADEMIC_FAILURE_PATTERN.search(ql))

queries = [
    "backlog",
    "back paper",
    "fail semester",
    "supplementary exam",
    "ami backlog peyechi",
    "amar backlog hoyeche",
    "back hoyeche",
    "back ache",
    "amar ekta sem a fail hoyeche",
    "ami supplementary dite chai",
    "amar result e back lagbe ki korbo",
    "ami khub somossa te achi amar bhi back chole aseche ki korbo",
]

vs = VectorStoreService()

print(f'{"Query #":>8} | {"Lang":>4} | {"Structured?":>11} | {"Policies Rank":>14} | {"MBA Rank?":>10} | {"Top Section":<25} | Top Score')
print('-' * 120)

for i, q in enumerate(queries, 1):
    # 1. Language detection
    lang = detect_language(q)
    
    # 2. Normalization
    normed = normalize(q)
    
    # 3. Expansion
    expanded = expand(normed)
    
    # 4. Structured handler check
    uses_structured = structured_match(q)
    
    # 5. Vector retrieval with EXPANDED query
    results = vs.vector_store.similarity_search_with_relevance_scores(expanded, k=10)
    
    top_score = results[0][1] if results else 0.0
    top_meta = results[0][0].metadata if results else {}
    top_section = f'{top_meta.get("section","?")}:{top_meta.get("subsection","?")}'
    
    # Check policies rank
    policies_rank = None
    mba_rank = None
    for rank, (doc, score) in enumerate(results, 1):
        text = doc.page_content or ''
        meta = doc.metadata or {}
        section = meta.get('section', '')
        if section == 'policies' or ('backlog' in text.lower() and 'fail' in text.lower()):
            policies_rank = rank
        if section == 'hod' and meta.get('subsection') == 'mba':
            if mba_rank is None:
                mba_rank = rank
    
    policies_str = f'#{policies_rank}' if policies_rank else 'ABSENT'
    mba_str = f'#{mba_rank}' if mba_rank else '—'
    
    print(f'{i:>8} | {lang:>4} | {str(uses_structured):>11} | {policies_str:>14} | {mba_str:>10} | {top_section:<25} | {top_score:.4f}')
    
    # Print the expanded query for Banglish queries
    if expanded != q:
        print(f'          Expanded: "{expanded}"')

print()
print('LEGEND:')
print('  Structured? = whether the structured handler would catch this query')
print('  Policies Rank = rank of backlog/fail KB chunk in retrieval results (#N or ABSENT)')
print('  MBA Rank? = rank of MBA HOD chunk (— if absent)')
print('  Top Section = top-ranked retrieval result')

# Show detailed retrieval for the ORIGINAL problem query
print()
print('=' * 80)
print('DETAILED: Original problem query')
print('=' * 80)
q = 'ami khub somossa te achi amar bhi back chole aseche ki korbo'
normed = normalize(q)
expanded = expand(normed)
lang = detect_language(q)
print(f'Raw:       "{q}"')
print(f'Normalized: "{normed}"')
print(f'Expanded:   "{expanded}"')
print(f'Language:   {lang}')
print(f'Structured: {structured_match(q)}')
print()
results = vs.vector_store.similarity_search_with_relevance_scores(expanded, k=10)
for rank, (doc, score) in enumerate(results, 1):
    meta = doc.metadata or {}
    text = doc.page_content or ''
    if '[' in text and ']' in text:
        text = text.split(']', 1)[-1].strip()
    section = meta.get('section', '?')
    anchor = meta.get('semantic_anchor', '?')
    is_policies = section == 'policies'
    is_mba = section == 'hod' and meta.get('subsection') == 'mba'
    tag = ''
    if is_policies: tag = ' <<< POLICIES ✓'
    elif is_mba: tag = ' <<< MBA'
    print(f'  #{rank}: score={score:.4f} section={section}:{meta.get("subsection","?")}{tag}')
    print(f'       "{text[:120]}"')
print()

# Also show CONTROL: English queries for comparison
print('=' * 80)
print('CONTROL: Same queries in English')
print('=' * 80)
en_queries = [
    'backlog',
    'fail semester',
]
for q in en_queries:
    normed = normalize(q)
    expanded = expand(normed)
    results = vs.vector_store.similarity_search_with_relevance_scores(expanded, k=5)
    print(f'Query: "{q}"')
    for rank, (doc, score) in enumerate(results, 1):
        meta = doc.metadata or {}
        text = doc.page_content or ''
        if '[' in text and ']' in text:
            text = text.split(']', 1)[-1].strip()
        section = meta.get('section', '?')
        is_policies = section == 'policies'
        tag = ' <<< POLICIES' if is_policies else ''
        print(f'  #{rank}: score={score:.4f} section={section}{tag}')
        print(f'       "{text[:100]}"')
    print()
