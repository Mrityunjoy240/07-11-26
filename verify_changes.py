#!/usr/bin/env python3
"""Verify all changes compile and test language detection fix."""
import sys, os, re
sys.path.insert(0, r'C:\Users\ANAMIKA\DEV\Temp\college_agent-master\college_agent-master\backend')
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
import warnings
warnings.filterwarnings('ignore')

# 1. Syntax check both files
import ast
for path in [
    r'app\services\llm\groq_service.py',
    r'app\utils\language_detect.py',
]:
    with open(os.path.join(sys.path[0], path), 'r', encoding='utf-8') as f:
        try:
            ast.parse(f.read())
            print(f'{path}: SYNTAX OK')
        except SyntaxError as e:
            print(f'{path}: SYNTAX ERROR: {e}')

print()

# 2. Test language detection
from app.utils.language_detect import detect_language, BANGLA_ROMAN_WORDS, HINDI_ROMAN_WORDS

QUERY = 'ami khub somossa te achi amar bhi back chole aseche ki korbo'
text_lower = QUERY.lower()
text_words = set(re.sub(r'[^\w\s]', ' ', text_lower).split())
bn_matches = text_words & BANGLA_ROMAN_WORDS
hi_matches = text_words & HINDI_ROMAN_WORDS
print(f'Bangla matches: {sorted(bn_matches)} (count={len(bn_matches)})')
print(f'Hindi matches:  {sorted(hi_matches)} (count={len(hi_matches)})')
detected = detect_language(QUERY)
print(f'detect_language() = "{detected}"')
print(f'"amar" in BANGLA_ROMAN_WORDS: {"amar" in BANGLA_ROMAN_WORDS}')
print()

# 3. Check class attributes exist
from app.services.llm.groq_service import GroqService
print(f'_BANGLISH_SYNONYMS: {hasattr(GroqService, "_BANGLISH_SYNONYMS")}')
print(f'_ACADEMIC_FAILURE_EXPANSION: {hasattr(GroqService, "_ACADEMIC_FAILURE_EXPANSION")}')
print(f'_ACADEMIC_FAILURE_TRIGGER: {hasattr(GroqService, "_ACADEMIC_FAILURE_TRIGGER")}')

# 4. Test normalization on sample queries
print()
print('Testing normalization:')
test_queries = [
    'ami khub somossa te achi amar bhi back chole aseche ki korbo',
    'back ache',
    'back hoyeche',
    'amar ekta sem a fail hoyeche',
    'back paper',
    'fyel',
]
# Can't call _normalize_query without instantiation, so test the regex patterns directly
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
for q in test_queries:
    normalized = q
    for pat, repl in _BANGLISH_SYNONYMS:
        normalized = re.sub(pat, repl, normalized, flags=re.IGNORECASE)
    print(f'  Input:  "{q}"')
    print(f'  Output: "{normalized}"')
    print()
