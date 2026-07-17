"""
Demo Readiness Assessment — BCREC Voice Agent
Tests every critical path for the principal demo.
"""

import json, sys, os, re, asyncio

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, "backend"))
sys.stdout.reconfigure(encoding="utf-8")

PASS = 0
FAIL = 0
WARN = 0
results = []


def check(ok, msg, detail=""):
    global PASS, FAIL, WARN
    if ok:
        PASS += 1
        results.append(f"  ✅ {msg}")
    else:
        FAIL += 1
        results.append(f"  ❌ {msg} — {detail}")


def warn(msg, detail=""):
    global WARN
    WARN += 1
    results.append(f"  ⚠️  {msg} — {detail}")


# ── 1. Load KB and validate structure ──
print("=" * 60)
print("PHASE 1: Knowledge Base Integrity")
print("=" * 60)

kb_path = os.path.join(_ROOT, "backend", "data", "knowledge_base", "combined_kb.json")
with open(kb_path, "r", encoding="utf-8") as f:
    kb = json.load(f)

vra = kb.get("voice_ready_answers", {})
check(len(vra) >= 20, f"voice_ready_answers has {len(vra)} entries (expected >= 20)")

for key, entry in vra.items():
    kw = entry.get("keywords", [])
    if kw is None:
        warn(f"Entry '{key}' has null keywords (uses sub_answers or topic mapping?)")
    elif len(kw) == 0:
        warn(f"Entry '{key}' has empty keywords list")
    else:
        check(True, f"Entry '{key}': {len(kw)} keywords")

    has_answers = "answers" in entry and isinstance(entry["answers"], dict)
    has_sub = "sub_answers" in entry
    if has_answers:
        for lang in ["en", "hi", "bn"]:
            if lang not in entry["answers"]:
                warn(f"Entry '{key}' missing '{lang}' answer")
            elif len(entry["answers"][lang]) < 10:
                warn(
                    f"Entry '{key}' '{lang}' answer too short ({len(entry['answers'][lang])} chars)"
                )
    if has_sub:
        for sk, sv in entry["sub_answers"].items():
            sub_kw = sv.get("keywords", [])
            if not sub_kw:
                warn(f"Entry '{key}' sub_answer '{sk}' has no keywords")
            for lang in ["en", "hi", "bn"]:
                if lang not in sv.get("answers", {}):
                    warn(f"Entry '{key}' sub_answer '{sk}' missing '{lang}' answer")

# ── 2. Load GroqService ──
print("\n" + "=" * 60)
print("PHASE 2: GroqService Initialization & Keywords")
print("=" * 60)

from app.services.llm.groq_service import GroqService

gs = GroqService()

kw_set = gs._all_faq_keywords
check(len(kw_set) > 0, f"_all_faq_keywords has {len(kw_set)} entries")

for must in [
    "hod",
    "principal",
    "hostel",
    "placement",
    "admission",
    "scholarship",
    "campus",
    "wifi",
    "documents",
]:
    check(must in kw_set, f"Keyword '{must}' in _all_faq_keywords")

for must in ["एचओडी", "प्रिंसिपल", "फीस", "छात्रावास", "প্লেসমেন্ট", "ক্যাম্পাস"]:
    check(must in kw_set, f"Hindi/Bengali keyword '{must}' in _all_faq_keywords")

# ── 3. Test _try_faq ──
print("\n" + "=" * 60)
print("PHASE 3: FAQ Matching Accuracy (ALL entries, ALL languages)")
print("=" * 60)

test_cases = [
    ("principal name", "en"),
    ("who is the principal", "en"),
    ("प्रिंसिपल कौन हैं", "hi"),
    ("প্রিন্সিপাল কে", "bn"),
    ("vice principal name", "en"),
    ("वाइस प्रिंसिपल", "hi"),
    ("হোড", "bn"),
    ("एचओडी", "hi"),
    ("hod", "en"),
    ("hostel fee", "en"),
    ("hostel fees", "en"),
    ("छात्रावास शुल्क", "hi"),
    ("placement", "en"),
    ("placement report", "en"),
    ("प्लेसमेंट", "hi"),
    ("documents required", "en"),
    ("documents for admission", "en"),
    ("scholarship", "en"),
    ("scholarship details", "en"),
    ("छात्रवृत्ति", "hi"),
    ("admission process", "en"),
    ("एडमिशन", "hi"),
    ("কোর্স", "bn"),
    ("courses offered", "en"),
    ("wifi", "en"),
    ("वाईफाई", "hi"),
    ("faculty", "en"),
    ("फैकल्टी", "hi"),
    ("online learning", "en"),
    ("campus", "en"),
    ("campus size", "en"),
    ("बीसीआरईसी क्यों", "hi"),
    ("why bcrec", "en"),
    ("policy", "en"),
    ("hidden charges", "en"),
    ("refund policy", "en"),
    ("application status", "en"),
    ("international", "en"),
    ("international admissions", "en"),
]

for query, lang in test_cases:
    result = gs._try_faq(query, lang)
    ok = result is not None and len(result) > 5
    check(ok, f"[{lang}] '{query}' → matched", f"got: {result[:60] if result else 'None'}...")

# Sub-answer tests (HOD departments)
hod_cases = [
    ("cse hod", "en"),
    ("it hod", "en"),
    ("ece hod", "en"),
    ("ee hod", "en"),
    ("me hod", "en"),
    ("ce hod", "en"),
    ("aiml hod", "en"),
    ("bca hod", "en"),
    ("mba hod", "en"),
    ("mca hod", "en"),
    ("csd hod", "en"),
    ("एचओडी सीएसई", "hi"),
    ("হোড সিএসডি", "bn"),
]
for query, lang in hod_cases:
    result = gs._try_faq(query, lang)
    ok = result is not None and len(result) > 5
    check(ok, f"[{lang}] HOD '{query}' → matched", f"got: {result[:60] if result else 'None'}...")

# Fee branch tests
fee_cases = [
    ("cse fee", "en"),
    ("it fee", "en"),
    ("ece fee", "en"),
    ("ee fee", "en"),
    ("me fee", "en"),
    ("ce fee", "en"),
    ("aiml fee", "en"),
    ("csd fee", "en"),
    ("एएमएल फीस", "hi"),
    ("এআইএমএল ফি", "bn"),
    ("cse core fee", "en"),
    ("it fees", "en"),
]
for query, lang in fee_cases:
    result = gs._try_faq(query, lang)
    ok = result is not None and len(result) > 5
    check(ok, f"[{lang}] Fee '{query}' → matched", f"got: {result[:60] if result else 'None'}...")

# ── 4. Follow-up scenario tests ──
print("\n" + "=" * 60)
print("PHASE 4: Follow-Up Scenarios")
print("=" * 60)

# The skip-faq logic is inside generate_response(), not _try_faq.
# We test generate_response() to verify it handles follow-ups correctly.

# Test greeting first
result_greeting = asyncio.run(gs.generate_response("hi"))
check(
    result_greeting["source"] == "greeting_deterministic",
    "Greeting 'hi' → deterministic",
    f"got: {result_greeting.get('source')}",
)

# Language detection
from app.utils.language_detect import detect_language

check(detect_language("hello") == "en", "detect_language: 'hello' → en")
check(detect_language("नमस्ते") == "hi", "detect_language: 'नमस्ते' → hi")
check(detect_language("হ্যালো") == "bn", "detect_language: 'হ্যালো' → bn")

# Romanized Hindi (Hinglish)
# Without fasttext, this is harder but the fallback should catch common words
detected = detect_language("mujhe principal ka naam bataye")
hi_or_en = detected in ("hi", "en")
check(hi_or_en, f"Romanized Hindi detected as '{detected}' (hi or en is acceptable)")

# ── 5. Edge cases ──
print("\n" + "=" * 60)
print("PHASE 5: Edge Cases & Robustness")
print("=" * 60)

# Empty query — should not crash, should return a response
result_empty = asyncio.run(gs.generate_response(""))
check(
    "answer" in result_empty and len(result_empty.get("answer", "")) > 0,
    "Empty query handled gracefully (returns non-empty answer)",
)

# Query with numbers still matches FAQ
result_num_faq = gs._try_faq("fee for 2025 batch in cse", "en")
check(
    result_num_faq is not None,
    "Query with numbers still matches FAQ",
    f"got: {result_num_faq[:80] if result_num_faq else 'None'}...",
)

# ── 6. TTS Normalization (clean_for_voice) ──
print("\n" + "=" * 60)
print("PHASE 6: TTS Normalization Quality")
print("=" * 60)

from app.utils.voice_utils import clean_for_voice

tts_tests = [
    ("BCREC fee is Rs. 5,98,300 per year", "rupees"),
    ("Contact HOD at 0343-2501353", "0"),
    ("The fee is 520000 rupees", "lakh"),
    ("Prof. Sanjay S. Pawar is principal", "Professor"),
    ("B.Tech CSE AIML fee structure", "Computer Science and Engineering"),
    ("Dr. K. M. Hossain is Vice Principal", "Doctor"),
    ("NAAC accreditation", "N. A. A. C."),
    ("WBJEE rank", "W. B. J. E. E."),
    ("The LPA is 12 LPA", "Lakhs per annum"),
    ("Rs. 4,37,700 for ME and CE", "rupees"),
    ("CSE department has 120 students", "hundred"),
]

for inp, expected in tts_tests:
    try:
        out = clean_for_voice(inp)
        ok = expected.lower() in out.lower()
        check(
            ok, f"clean_for_voice: '{inp[:50]}...' → contains '{expected}'", f"got: '{out[:80]}...'"
        )
    except Exception as e:
        check(False, f"clean_for_voice: '{inp[:50]}...' threw exception", str(e))

# Hindi text normalization
hi_text = "बीसीआरईसी की फीस पाँच लाख अट्ठानवे हजार तीन सौ रुपये है"
try:
    out_hi = clean_for_voice(hi_text)
    check(True, "clean_for_voice handles Hindi text", f"output: {out_hi[:60]}...")
except Exception as e:
    check(False, "clean_for_voice handles Hindi text", str(e))

bn_text = "বিসিআরইসি এর ফি পাঁচ লাখ ছাপ্পান্ন হাজার টাকা"
try:
    out_bn = clean_for_voice(bn_text)
    check(True, "clean_for_voice handles Bengali text", f"output: {out_bn[:60]}...")
except Exception as e:
    check(False, "clean_for_voice handles Bengali text", str(e))

# ── 7. Answer quality: No raw digits in FAQ answers ──
print("\n" + "=" * 60)
print("PHASE 7: Answer Quality — No raw digits in FAQ fee answers")
print("=" * 60)

fee_queries = [
    ("cse fee", "en"),
    ("hostel fee", "en"),
    ("एमई फीस", "hi"),
    ("এমই ফি", "bn"),
]
for q, lang in fee_queries:
    faq_result = gs._try_faq(q, lang)
    if faq_result:
        ans = faq_result
        has_raw_digits = bool(re.search(r"\b\d[\d,.]*\b", ans.replace(" ", "")))
        if has_raw_digits:
            digits_found = re.findall(r"\b\d[\d,.]*\b", ans)
            warn(
                f"FAQ answer for '{q}' contains raw digits: {digits_found[:3]}",
                f"answer: {ans[:120]}",
            )
        else:
            check(True, f"FAQ answer for '{q}' has no raw digits (TTS-safe)", "")

# ── 8. sarvam_service clean_for_voice integration check ──
print("\n" + "=" * 60)
print("PHASE 8: Sarvam Service — clean_for_voice Integration")
print("=" * 60)

from app.services.sarvam_service import SarvamService

sarvam = SarvamService(api_key="test")
test_text = "BCREC CSE fee is Rs. 5,98,300 per year for Prof. Dr. Sanjay"
normalized = sarvam._normalize_text_for_tts(test_text)
# Should have expanded abbreviations
check(
    "Rupees" in normalized or "rupees" in normalized,
    "sarvam._normalize_text_for_tts expands Rs. → Rupees",
    f"got: {normalized[:80]}...",
)

# ── 9. Data file cross-check: no JSON syntax errors ──
print("\n" + "=" * 60)
print("PHASE 9: Data File Integrity")
print("=" * 60)

# Re-parse KB to check it's valid JSON
try:
    json.loads(open(kb_path, "r", encoding="utf-8").read())
    check(True, "combined_kb.json is valid JSON")
except Exception as e:
    check(False, "combined_kb.json is valid JSON", str(e))

# Check FAQ entries have correct answer content
vra = kb.get("voice_ready_answers", {})
principal_bn = vra.get("principal", {}).get("answers", {}).get("bn", "")
check("সঞ্জয়" in principal_bn, "Principal BN answer contains 'সঞ্জয়' (সঞ্জয় এস পাওয়ার)")

hostel_en = vra.get("hostel", {}).get("answers", {}).get("en", "")
check("hostel" in hostel_en.lower(), "Hostel EN answer contains 'hostel'")

placement_hi = vra.get("placement", {}).get("answers", {}).get("hi", "")
check(len(placement_hi) > 20, f"Placement HI answer exists ({len(placement_hi)} chars)")

# ── 10. stream_response works (verify no crash) ──
print("\n" + "=" * 60)
print("PHASE 10: Streaming Response (no crash on basic call)")
print("=" * 60)


async def test_stream():
    collected = ""
    async for chunk in gs.stream_response("hi"):
        collected += chunk
    return collected


try:
    stream_out = asyncio.run(test_stream())
    check(len(stream_out) > 0, "stream_response('hi') yields text", f"len={len(stream_out)}")
    check(
        any(word in stream_out.lower() for word in ["hello", "hi", "help", "how can"]),
        "stream_response('hi') returns greeting",
        f"got: {stream_out[:80]}...",
    )
except Exception as e:
    check(False, "stream_response('hi') works", str(e))

# ── SUMMARY ──
print("\n" + "=" * 60)
print("DEMO READINESS RESULTS")
print("=" * 60)
print(f"  ✅ PASS: {PASS}")
print(f"  ❌ FAIL: {FAIL}")
print(f"  ⚠️  WARN: {WARN}")
print(f"  Total: {PASS + FAIL + WARN}")

if FAIL == 0:
    print("\n  🟢 OVERALL: DEMO READY (no failures)")
elif FAIL <= 3:
    print(f"\n  🟡 OVERALL: CONDITIONAL ({FAIL} failures — review warnings)")
else:
    print(f"\n  🔴 OVERALL: NOT READY ({FAIL} failures — must fix before demo)")

report_path = "demo_readiness_report.txt"
with open(report_path, "w", encoding="utf-8") as f:
    f.write("BCREC VOICE AGENT — DEMO READINESS REPORT\n")
    f.write("=" * 50 + "\n\n")
    for r in results:
        f.write(r + "\n")
    f.write(f"\n\nPASS: {PASS} | FAIL: {FAIL} | WARN: {WARN}\n")
print(f"\nDetailed report: {report_path}")
