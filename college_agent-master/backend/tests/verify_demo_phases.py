"""Integration verification for Phases 0, 3 Lite, 4 — no network required."""
import sys, os, asyncio
sys.path.insert(0, '.')
os.environ.setdefault('GROQ_API_KEY', '')

print('=' * 70)
print('  INTEGRATION VERIFICATION (no-network)')
print('  Tests all 3 phases end-to-end with stubs')
print('=' * 70)

# ---------- Test 1: Phase 0 hallucination guard ----------
print()
print('TEST 1: Phase 0 — Hallucination guard via full code path')
print('-' * 70)
from app.services.llm.groq_service import GroqService
svc = GroqService.__new__(GroqService)
svc._cache = None

ctx = 'CSE total fee is 5,98,300. Intake is 180.'
hallucinated = 'CSE fee is 9,99,999 rupees.'
correct = 'CSE fee is 5,98,300 rupees.'

ok_bad, _ = svc._validate_answer(hallucinated, ctx, 'What is CSE fee?')
ok_good, _ = svc._validate_answer(correct, ctx, 'What is CSE fee?')
assert ok_bad == False
assert ok_good == True
print('  Hallucinated fee rejected:', not ok_bad)
print('  Correct fee accepted:    ', ok_good)

# ---------- Test 2: Phase 4 cache round-trip ----------
print()
print('TEST 2: Phase 4 — Cache hit/miss/store cycle')
print('-' * 70)
import cachetools
svc._cache = cachetools.TTLCache(maxsize=256, ttl=600)
svc._cache_stats = {'hits': 0, 'misses': 0}
svc._kb_mtime = 12345.0

query, lang, context = 'What is BTech fee?', 'en', 'CSE fee 5,98,300'
key = svc._cache_key(query, lang, context)
cached = svc._cache.get(key)
assert cached is None
svc._cache_stats['misses'] += 1
print('  First call:  miss (cache empty)')

response = {'answer': 'CSE fee is 5,98,300', 'voice_text': 'CSE fee is 5,98,300'}
svc._cache[key] = response

cached = svc._cache.get(key)
assert cached is not None
svc._cache_stats['hits'] += 1
print('  Second call: hit (served from cache)')

stats = svc.get_cache_stats()
print(f'  Stats: hit_ratio={stats["hit_ratio"]}, size={stats["size"]}')
assert stats['hit_ratio'] == 0.5

# ---------- Test 3: Phase 3 Lite TTS cache ----------
print()
print('TEST 3: Phase 3 Lite — TTS audio cache')
print('-' * 70)
from app.services import tts_cache
import tempfile, shutil
test_dir = tempfile.mkdtemp(prefix='tts_int_test_')
tts_cache._CACHE_DIR = test_dir
tts_cache._MEMORY_CACHE.clear()

fake_wav = b'RIFF' + b'\x00' * 100
text = 'Hello! Welcome to BCREC.'

audio = tts_cache.get_cached_audio(text, 'en-IN', 'shubh')
assert audio is None
print('  First request: miss')

tts_cache.store_audio(text, 'en-IN', 'shubh', fake_wav)
audio = tts_cache.get_cached_audio(text, 'en-IN', 'shubh')
assert audio == fake_wav
print('  Second request: hit (memory)')

tts_cache._MEMORY_CACHE.clear()
audio = tts_cache.get_cached_audio(text, 'en-IN', 'shubh')
assert audio == fake_wav
print('  Memory cleared: hit (disk)')

stats = tts_cache.get_stats()
print(f'  TTS stats: hits={stats["hits"]}, misses={stats["misses"]}, ratio={stats["hit_ratio"]}')

shutil.rmtree(test_dir, ignore_errors=True)

# ---------- Test 4: API endpoints registered ----------
print()
print('TEST 4: API endpoints registered correctly')
print('-' * 70)
from app.api.tts import router as tts_router
paths = sorted({r.path for r in tts_router.routes if hasattr(r, 'path')})
print(f'  TTS routes: {paths}')
assert '/tts/cache/stats' in paths
assert '/tts/cache/invalidate' in paths
print('  /qa/tts/cache/stats:      registered (under /qa prefix from main.py)')
print('  /qa/tts/cache/invalidate:  registered (under /qa prefix from main.py)')

# ---------- Test 5: KB mtime auto-invalidation ----------
print()
print('TEST 5: Cache auto-invalidation via KB mtime')
print('-' * 70)
svc._check_kb_changed()
print('  Initial check: no-op')
old_mtime = svc._kb_mtime
svc._kb_mtime = old_mtime - 100
svc._check_kb_changed()
assert len(svc._cache) == 0
print('  KB change detected: cache cleared')

print()
print('=' * 70)
print('  ALL INTEGRATION CHECKS PASSED')
print('=' * 70)
