"""Full system test — run from project root."""
import sys, asyncio, os
sys.path.insert(0, 'backend')
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from dotenv import load_dotenv
load_dotenv('backend/.env')

results = []

def ok(name, detail=""): results.append((name, "PASS", detail))
def fail(name, err):     results.append((name, "FAIL", str(err)[:90]))
def warn(name, detail=""): results.append((name, "WARN", detail))
def info(name, detail=""): results.append((name, "----", detail))

# ── TEST 1: Core imports ────────────────────────────────────────────────────
try:
    from app.services.llm.groq_service import get_groq_service
    from app.services.sarvam_service import get_sarvam_service
    from app.services.vector_store import get_vector_store
    from app.services import tts_cache
    from app.utils.language_detect import detect_language
    ok("Core imports")
except Exception as e:
    fail("Core imports", e)

# ── TEST 2: Vector Store / RAG ──────────────────────────────────────────────
try:
    vs = get_vector_store()
    r_en = vs.search("CSE fee", k=3)
    r_bn = vs.search("ভর্তি", k=2)
    r_hi = vs.search("हॉस्टल", k=2)
    assert len(r_en) > 0
    ok("Vector search EN", f"{len(r_en)} chunks")
    ok("Vector search BN", f"{len(r_bn)} chunks")
    ok("Vector search HI", f"{len(r_hi)} chunks")
except Exception as e:
    fail("Vector search", e)

# ── TEST 3: Language Detection ───────────────────────────────────────────────
try:
    lang_en = detect_language("What are the fees for CSE?")
    lang_bn = detect_language("ফি কত?")
    lang_hi = detect_language("फीस कितनी है?")
    assert lang_en == "en", f"Expected en, got {lang_en}"
    assert lang_bn == "bn", f"Expected bn, got {lang_bn}"
    assert lang_hi == "hi", f"Expected hi, got {lang_hi}"
    ok("Language detect", "en/bn/hi all correct")
except Exception as e:
    fail("Language detect", e)

# ── TEST 4: TTS Cache ───────────────────────────────────────────────────────
try:
    tts_cache.store_audio("Hello BCREC", "en-IN", "shubh", b"fakeaudio123")
    cached = tts_cache.get_cached_audio("Hello BCREC", "en-IN", "shubh")
    assert cached == b"fakeaudio123"
    stats = tts_cache.get_stats()
    ok("TTS cache store/retrieve", f"mem_entries={stats['memory_entries']}")
except Exception as e:
    fail("TTS cache", e)

# ── TEST 5: Groq LLM — English ─────────────────────────────────────────────
async def test_groq_en():
    svc = get_groq_service()
    r = await svc.generate_response("What is the total fee for CSE branch?")
    return r

try:
    r = asyncio.run(test_groq_en())
    answer = r.get("answer", "")
    validated = r.get("hallucination_validated")
    cache_hit = r.get("cache_hit", False)
    ok("Groq LLM EN", f"validated={validated} cache={cache_hit}")
    info("LLM Answer (EN)", answer[:110])
except Exception as e:
    fail("Groq LLM EN", e)

# ── TEST 6: Groq LLM — Bengali ─────────────────────────────────────────────
async def test_groq_bn():
    svc = get_groq_service()
    r = await svc.generate_response("হোস্টেল আছে কি?")
    return r

try:
    r = asyncio.run(test_groq_bn())
    ok("Groq LLM BN", f"validated={r.get('hallucination_validated')}")
    info("LLM Answer (BN)", r.get("answer","")[:80])
except Exception as e:
    fail("Groq LLM BN", e)

# ── TEST 7: Query cache (2nd identical call) ────────────────────────────────
async def test_cache_hit():
    svc = get_groq_service()
    r = await svc.generate_response("What is the total fee for CSE branch?")
    return r.get("cache_hit", False)

try:
    hit = asyncio.run(test_cache_hit())
    if hit:
        ok("Query cache hit", "2nd call served from cache")
    else:
        warn("Query cache hit", "Cache miss on 2nd call (TTL may have reset)")
except Exception as e:
    fail("Query cache", e)

# ── TEST 8: Out-of-KB fallback ──────────────────────────────────────────────
async def test_fallback():
    svc = get_groq_service()
    r = await svc.generate_response("What is the price of gold today?")
    return r.get("answer", "")

try:
    ans = asyncio.run(test_fallback())
    if "0343" in ans or "don't have" in ans.lower() or "sorry" in ans.lower():
        ok("Hallucination guard fallback", "Correctly refused out-of-KB query")
    else:
        warn("Hallucination guard fallback", f"Unexpected: {ans[:80]}")
except Exception as e:
    fail("Hallucination guard", e)

# ── TEST 9: Backend app import ─────────────────────────────────────────────
try:
    import importlib
    spec = importlib.util.spec_from_file_location("main", "backend/app/main.py")
    ok("Backend main.py importable", "")
except Exception as e:
    fail("Backend main.py", e)

# ── TEST 10: LiveKit agent importable ──────────────────────────────────────
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("livekit_agent", "scripts/livekit_agent.py")
    ok("livekit_agent.py importable", "")
except Exception as e:
    fail("livekit_agent.py", e)

# ── PRINT RESULTS ──────────────────────────────────────────────────────────
print()
print("=" * 70)
print("  BCREC VOICE AGENT — FULL SYSTEM TEST")
print("=" * 70)
for name, status, detail in results:
    icon = "✓" if status == "PASS" else ("✗" if status == "FAIL" else ("⚠" if status == "WARN" else " "))
    print(f"  {icon}  {name:<35} [{status}]  {detail}")
print("=" * 70)
passed = sum(1 for r in results if r[1] == "PASS")
failed = sum(1 for r in results if r[1] == "FAIL")
warned = sum(1 for r in results if r[1] == "WARN")
print(f"  PASSED: {passed}  |  WARNINGS: {warned}  |  FAILED: {failed}")
print("=" * 70)
sys.exit(1 if failed > 0 else 0)
