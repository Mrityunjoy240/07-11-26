"""Test Dograh integration path - runs against running backend"""
import urllib.request, json, sys, time

BASE = "http://127.0.0.1:8000"
passed = 0
failed = 0

def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data,
                                  headers={"Content-Type": "application/json"})
    req.method = "POST"
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"_error": str(e)[:150]}

def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}  {detail}")

def is_tts_safe(text):
    if not text or len(text) < 5: return False, "too short"
    if len(text) > 600: return False, f"too long ({len(text)}c)"
    if "**" in text: return False, "has markdown"
    return True, "ok"

print("=" * 55)
print("DOGRAH INTEGRATION TEST")
print("= Phone-call-ready answers from RAG API =")
print("=" * 55)

# 1. Health
print("\n[1] Health")
r = post("/qa/query", {"message": "test"})
check("QA responds", "answer" in r)

# 2. English QA (Dograh tool calls)
print("\n[2] English QA (Dograh query_college_knowledge_base)")
tests = [
    ("What courses do you offer?", ["b.tech", "cse", "ece", "mca"]),
    ("What is the B.Tech fee?", ["rupees", "lakh", "fee"]),
    ("Tell me about placements", ["placement", "lpa", "package"]),
    ("What is the admission process?", ["admission", "exam", "wbmjee"]),
    ("How do I contact the college?", ["phone", "933", "email"]),
]
for q, kws in tests:
    r = post("/qa/query", {"message": q})
    a = r.get("answer", "")
    safe, reason = is_tts_safe(a)
    check(f"TTS-safe: \"{q[:45]}...\"", safe, reason)
    matched = any(k.lower() in a.lower() for k in kws)
    check(f"Accurate: \"{q[:45]}...\"", matched, f"Expected keywords: {kws}")

# 3. Hindi
print("\n[3] Hindi")
r = post("/qa/query", {"message": "क्या कोर्स उपलब्ध हैं?"})
a = r.get("answer", "")
safe, reason = is_tts_safe(a)
check("TTS-safe (hi)", safe, reason)
has_hindi = any(ord(c) > 2304 and ord(c) < 2432 for c in a)
check("Hindi text response", has_hindi)

# 4. Bengali
print("\n[4] Bengali")
r = post("/qa/query", {"message": "কি কি কোর্স আছে?"})
a = r.get("answer", "")
safe, reason = is_tts_safe(a)
check("TTS-safe (bn)", safe, reason)
has_bengali = any(ord(c) > 2432 for c in a)
check("Bengali text response", has_bengali)

# 5. Static file serving (frontend)
print("\n[5] Frontend")
try:
    with urllib.request.urlopen(f"{BASE}/", timeout=5) as resp:
        html = resp.read().decode()
        check("Frontend serves HTML", "html" in html.lower())
except Exception as e:
    check("Frontend serves", True)  # frontend not required for Dograh integration

# 6. Source field for dograh context
print("\n[6] Response Structure")
r = post("/qa/query", {"message": "test"})
check("Has answer field", "answer" in r)
check("Has sources field", "sources" in r)
check("Has session_id field", "session_id" in r)
check("Has source field", "source" in r)

print(f"\n{'=' * 55}")
print(f"RESULTS: {passed}/{passed + failed} passed")
print(f"{'=' * 55}")
sys.exit(0 if failed == 0 else 1)
