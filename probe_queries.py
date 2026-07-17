#!/usr/bin/env python3
"""
Probe retrieval at Banglish/English boundary to determine:
- Is the embedding model itself bad at Banglish?
- Or is the failure specifically caused by "back" not normalizing to "backlog"?
"""
import sys, os
sys.path.insert(0, r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend')
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
import warnings
warnings.filterwarnings('ignore')

from app.services.vector_store import VectorStoreService
vs = VectorStoreService()

queries = [
    # Pure English baselines
    (1,  "back",                              "en"),
    (2,  "back paper",                        "en"),
    (3,  "backlog",                           "en"),
    (4,  "supplementary exam",                "en"),
    (5,  "fail semester",                     "en"),
    # Banglish variants — mixing "back" with Bangla
    (6,  "back ache",                         "bn"),
    (7,  "ami backlog peyechi",               "bn"),
    (8,  "amar backlog hoyeche",              "bn"),
    (9,  "backlog hoyeche",                   "bn"),
    (10, "back paper hoyeche",                "bn"),
    # The original problem query
    (11, "ami khub somossa te achi amar bhi back chole aseche ki korbo",  "bn"),
    # Full Banglish — no English keywords at all
    (12, "ami porikkhay fyel korechi",        "bn"),
    (13, "amar ekta sem a fail hoyeche",      "bn"),
    (14, "ami supplementary dite chai",       "bn"),
    (15, "amar result e back lagbe ki korbo",  "bn"),
]

print(f'{"#":>2} | {"Query":<60} | {"Lang":>4} | {"Top Score":>9} | {"Top Section":<25} | {"Policies in Top-10?":<20}')
print('-' * 130)

for qid, query, lang in queries:
    results = vs.vector_store.similarity_search_with_relevance_scores(query, k=10)
    
    if not results:
        print(f'{qid:>2} | {query:<60} | {lang:>4} | {"no results":>9} | {"":25} | {"—":20}')
        continue
    
    top_score = results[0][1]
    top_meta = results[0][0].metadata or {}
    top_section = f'{top_meta.get("section","?")}:{top_meta.get("subsection","?")}'
    top_text = results[0][0].page_content or ''
    if '[' in top_text and ']' in top_text:
        top_text = top_text.split(']', 1)[-1].strip()
    
    # Check if policies/backlog content appears anywhere in top 10
    policies_found = False
    policies_rank = None
    for rank, (doc, score) in enumerate(results, 1):
        text = doc.page_content or ''
        section = (doc.metadata or {}).get('section', '')
        if section == 'policies' or any(kw in text.lower() for kw in ['backlog', 'fail', 'supplementary', 'reappear']):
            policies_found = True
            policies_rank = rank
            break
    
    # Check if MBA appears
    mba_found = False
    mba_rank = None
    for rank, (doc, score) in enumerate(results, 1):
        text = doc.page_content or ''
        section = (doc.metadata or {}).get('section', '')
        if 'mba' in text.lower() or 'mba' in section.lower():
            mba_found = True
            mba_rank = rank
            break
    
    policies_str = f'Rank {policies_rank}' if policies_found else 'ABSENT'
    mba_str = f'MBA@Rank {mba_rank}' if mba_found else '—'
    
    print(f'{qid:>2} | {query:<60} | {lang:>4} | {top_score:.4f} | {top_section:<25} | {policies_str:<20} | {mba_str}')

print()

# Now show DETAILED output for the critical queries
print('=' * 80)
print('DETAIL: Key queries with all candidates')
print('=' * 80)

key_queries = [
    (3,  "backlog",                           "en – pure English keyword"),
    (6,  "back ache",                         "bn – Banglish 'back'"),
    (9,  "backlog hoyeche",                   "bn – Banglish 'backlog'"),
    (12, "ami porikkhay fyel korechi",        "bn – pure Banglish 'fail'"),
    (15, "amar result e back lagbe ki korbo", "bn – Banglish 'back'"),
]

for qid, query, label in key_queries:
    print(f'\n--- Query {qid}: "{query}" ({label}) ---')
    results = vs.vector_store.similarity_search_with_relevance_scores(query, k=10)
    for i, (doc, score) in enumerate(results):
        meta = doc.metadata or {}
        text = doc.page_content or ''
        if '[' in text and ']' in text:
            text = text.split(']', 1)[-1].strip()
        section = meta.get('section', '?')
        anchor = meta.get('semantic_anchor', '?')
        is_policy = section == 'policies' or 'backlog' in text.lower() or 'fail' in text.lower()
        is_mba = 'mba' in text.lower() or 'mba' in section.lower() or meta.get('subsection') == 'mba'
        tag = ''
        if is_policy: tag = ' <<< POLICIES'
        elif is_mba: tag = ' <<< MBA'
        print(f'  #{i+1}: score={score:.4f} section={section} anchor={anchor[:40]}{tag}')
        print(f'       "{text[:100]}"')
