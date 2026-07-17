#!/usr/bin/env python3
"""
Trace raw Chroma retrieval pipeline for the Bengali backlog query.
Shows ALL candidates before any filtering/reranking/dedup.
"""
import sys, os, re, json
sys.path.insert(0, r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend')
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
import warnings
warnings.filterwarnings('ignore')

QUERY = 'ami khub somossa te achi amar bhi back chole aseche ki korbo'

from app.services.vector_store import VectorStoreService

vs = VectorStoreService()

# ============================================================
# PHASE 1: What documents exist in the vector store?
# ============================================================
print('=' * 80)
print('PHASE 1: Vector store inventory')
print('=' * 80)

collection = vs.vector_store._collection
count = collection.count()
print(f'Total documents in collection: {count}')
print()

# Get ALL documents metadata to understand what's in the store
all_data = collection.get(include=['metadatas', 'documents'])
all_metas = all_data['metadatas']
all_docs = all_data['documents']

# Group by section and semantic_anchor
sections = {}
for i, meta in enumerate(all_metas):
    section = meta.get('section', 'N/A') if meta else 'N/A'
    anchor = meta.get('semantic_anchor', 'N/A') if meta else 'N/A'
    lang = meta.get('language', 'N/A') if meta else 'N/A'
    key = f'{section} | {anchor} | {lang}'
    if key not in sections:
        sections[key] = {'count': 0, 'docs': [], 'content_preview': ''}
    sections[key]['count'] += 1
    if all_docs and i < len(all_docs):
        if not sections[key]['content_preview'] and all_docs[i]:
            text = all_docs[i]
            if '[' in text and ']' in text:
                text = text.split(']', 1)[-1].strip()
            sections[key]['content_preview'] = text[:200]

print(f'Unique section | anchor | language combinations: {len(sections)}')
print()
# Show sections that contain backlog/fail/backpaper keywords
print('--- Sections containing backlog/fail/backpaper/supply/arrear keywords ---')
for key, info in sorted(sections.items()):
    if any(kw in key.lower() for kw in ['backlog', 'fail', 'backpaper', 'supply', 'arrear', 'policy']):
        print(f'  {key}')
        print(f'    Count: {info["count"]}')
        print(f'    Preview: {info["content_preview"][:150]}')
        print()

# Show ALL sections for reference
print('--- ALL sections in vector store ---')
for key, info in sorted(sections.items()):
    print(f'  [{info["count"]:3d}x] {key}')
print()

# ============================================================
# PHASE 2: Raw Chroma search — top 20 candidates, NO filtering
# ============================================================
print('=' * 80)
print('PHASE 2: RAW Chroma Top-20 (similarity_search_with_relevance_scores)')
print('=' * 80)
print(f'Query: "{QUERY}"')
print()

# raw_search does NOT use search_with_scores (which has built-in filtering)
# Instead call similarity_search_with_relevance_scores directly
results = vs.vector_store.similarity_search_with_relevance_scores(QUERY, k=20)
print(f'Total raw results: {len(results)}')
print()

backlog_found = False
for i, (doc, score) in enumerate(results):
    meta = doc.metadata if hasattr(doc, 'metadata') else {}
    text = doc.page_content if hasattr(doc, 'page_content') else str(doc)
    if '[' in text and ']' in text:
        text = text.split(']', 1)[-1].strip()
    
    section = meta.get('section', 'N/A')
    subsection = meta.get('subsection', 'N/A')
    anchor = meta.get('semantic_anchor', 'N/A')
    lang = meta.get('language', 'N/A')
    
    # Check if this is backlog-related
    is_backlog = any(kw in text.lower() for kw in ['backlog', 'fail', 'supplementary', 'arrear', 'repeat course', 'semester', 'makut'])
    if is_backlog:
        backlog_found = True
    
    marker = ' <<< BACKLOG' if is_backlog else ''
    print(f'--- Rank {i+1} (score={score:.4f}){marker} ---')
    print(f'  Section:      {section}')
    print(f'  Subsection:   {subsection}')
    print(f'  Anchor:       {anchor}')
    print(f'  Language:     {lang}')
    print(f'  Content ({len(text)} chars):')
    print(f'  """{text[:300]}"""')
    print()

print(f'Backlog-related chunk found in raw Top-20? {backlog_found}')
print()

# ============================================================
# PHASE 3: Verify — does the backlog KB entry actually exist in the store?
# ============================================================
print('=' * 80)
print('PHASE 3: Manual check — does the backlog policy chunk exist?')
print('=' * 80)

# Read the original KB to check what backlog content should exist
kb_path = r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend\data\knowledge_base\combined_kb.json'
with open(kb_path, 'r', encoding='utf-8') as f:
    kb = json.load(f)

# Look at voice_ready_answers.policies
vra = kb.get('voice_ready_answers', {})
policies = vra.get('policies', {})
print('voice_ready_answers.policies content:')
print(json.dumps(policies, ensure_ascii=False, indent=2)[:800])
print()

# Check how the ingestion pipeline splits this into chunks
# Search the documents list for any content containing "backlog" or "fail"
print('--- Searching ALL vector store documents for backlog/fail content ---')
backlog_docs_found = []
for i, meta in enumerate(all_metas):
    doc_text = all_docs[i] if all_docs and i < len(all_docs) else ''
    if doc_text and any(kw in doc_text.lower() for kw in ['backlog', 'fail', 'supplementary', 'arrear', 'repeat course']):
        section = meta.get('section', 'N/A') if meta else 'N/A'
        anchor = meta.get('semantic_anchor', 'N/A') if meta else 'N/A'
        lang = meta.get('language', 'N/A') if meta else 'N/A'
        preview = doc_text[:200]
        if '[' in preview and ']' in preview:
            preview = preview.split(']', 1)[-1].strip()
        backlog_docs_found.append({
            'section': section,
            'anchor': anchor,
            'lang': lang,
            'preview': preview
        })

if backlog_docs_found:
    print(f'Found {len(backlog_docs_found)} backlog-related documents in vector store:')
    for bd in backlog_docs_found:
        print(f'  Section: {bd["section"]} | Anchor: {bd["anchor"]} | Lang: {bd["lang"]}')
        print(f'  Content: {bd["preview"][:150]}')
        print()
else:
    print('*** NO backlog-related documents found in vector store ***')
print()

# ============================================================
# PHASE 4: Control experiment — English rephrasing
# ============================================================
print('=' * 80)
print('PHASE 4: Control — same query in English')
print('=' * 80)

en_queries = [
    'I have a backlog from last semester what should I do',
    'backlog back paper failed semester help',
    'I failed a semester what are the supplementary exam rules',
]

for eq in en_queries:
    print(f'--- Query: "{eq}" ---')
    en_results = vs.vector_store.similarity_search_with_relevance_scores(eq, k=5)
    en_backlog_found = False
    for doc, score in en_results:
        text = doc.page_content or ''
        if '[' in text and ']' in text:
            text = text.split(']', 1)[-1].strip()
        is_bk = any(kw in text.lower() for kw in ['backlog', 'fail', 'supplementary', 'arrear'])
        if is_bk:
            en_backlog_found = True
            print(f'  Rank ??? (score={score:.4f}) <<< BACKLOG FOUND')
            print(f'  Section: {doc.metadata.get("section")} | Anchor: {doc.metadata.get("semantic_anchor")}')
            print(f'  Content: {text[:200]}')
            print()
    
    if not en_backlog_found:
        print(f'  Top result: score={en_results[0][1]:.4f}, section={en_results[0][0].metadata.get("section")}')
        print(f'  Content: {(en_results[0][0].page_content or "")[:200]}')
        print(f'  *** Even English query does NOT retrieve backlog content ***')
    print()

print('=' * 80)
print('SUMMARY')
print('=' * 80)
