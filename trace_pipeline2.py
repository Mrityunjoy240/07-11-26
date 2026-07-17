#!/usr/bin/env python3
"""Show per-chunk scores from ChromaDB similarity search."""
import sys, os, re, json
sys.path.insert(0, r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend')
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
import warnings
warnings.filterwarnings('ignore')

QUERY = 'ami khub somossa te achi amar bhi back chole aseche ki korbo'

from app.services.vector_store import VectorStoreService

vs = VectorStoreService()

# Direct Chroma access to get scores
results = vs.vector_store.similarity_search_with_relevance_scores(QUERY, k=10)
print(f'Total raw results: {len(results)}')
print(f'Threshold in vector_store.search_with_scores: 0.15')
print()

for i, (doc, score) in enumerate(results):
    meta = doc.metadata if hasattr(doc, 'metadata') else {}
    text = doc.page_content if hasattr(doc, 'page_content') else str(doc)
    if '[' in text and ']' in text:
        text = text.split(']', 1)[-1].strip()
    passed = score >= 0.15
    print(f'--- Result {i+1} (score={score:.4f}, {"PASS" if passed else "BLOCK"}) ---')
    print(f'  Section: {meta.get("section", "N/A")}')
    print(f'  Subsection: {meta.get("subsection", "N/A")}')
    print(f'  Semantic anchor: {meta.get("semantic_anchor", "N/A")}')
    print(f'  Language: {meta.get("language", "N/A")}')
    print(f'  Content ({len(text)} chars):')
    print(f'  """{text[:300]}"""')
    print()

# Filtered count
filtered = [(d,s) for d,s in results if s >= 0.15]
print(f'Filtered (score >= 0.15): {len(filtered)} docs')
print(f'Max score: {max((s for _,s in results), default=0.0):.4f}')
print()

# Now simulate _retrieve_context's re-rank + dedup
print('=' * 80)
print('SIMULATING _retrieve_context re-rank + dedup:')
print('=' * 80)

query_lower = QUERY.lower()
query_words = set(query_lower.split())
detected_lang = 'hi'

def semantic_score(doc):
    meta = doc.metadata or {}
    score = 0
    anchor = meta.get('semantic_anchor', '').lower()
    anchor_words = anchor.split()
    score += sum(1 for w in anchor_words if w in query_words)
    section = meta.get('section', '')
    if section and section.lower() in query_lower:
        score += 2
    if meta.get('language') == detected_lang:
        score += 1
    if meta.get('language') == 'en' and detected_lang != 'en':
        score -= 0.5
    return score

filtered_docs = [d for d,s in filtered]
for i, doc in enumerate(filtered_docs):
    meta = doc.metadata or {}
    ss = semantic_score(doc)
    text = doc.page_content or ''
    if '[' in text and ']' in text:
        text = text.split(']', 1)[-1].strip()
    print(f'  Doc {i+1}: semantic_score={ss}, section={meta.get("section")}, subsection={meta.get("subsection")}')

ranked = sorted(filtered_docs, key=semantic_score, reverse=True)
print()
print('  After re-rank (sorted by semantic_score):')
for i, doc in enumerate(ranked):
    meta = doc.metadata or {}
    text = doc.page_content or ''
    if '[' in text and ']' in text:
        text = text.split(']', 1)[-1].strip()
    print(f'  Rank {i+1}: section={meta.get("section")}:{meta.get("subsection")} ({len(text)} chars)')

print()
print('  After section:subsection dedup (taking first of each unique):')
seen = set()
final = []
for doc in ranked:
    meta = doc.metadata or {}
    section = meta.get('section', '')
    sub = meta.get('subsection', '')
    dedup_key = f'{section}:{sub}'
    if dedup_key in seen:
        print(f'    DISCARDED (duplicate): {dedup_key}')
        continue
    seen.add(dedup_key)
    text = doc.page_content or ''
    if '[' in text and ']' in text:
        text = text.split(']', 1)[-1].strip()
    final.append(text)
    print(f'    KEPT: {dedup_key} ({len(text)} chars)')
    if len(final) >= 8:
        break

context = '\n\n---\n\n'.join(final)
print()
print(f'  Final context length: {len(context)} chars')
print(f'  Context content:')
print(f'  """{context}"""')
