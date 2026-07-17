"""Comprehensive FAQ test — all entries, all languages, follow-ups, misspellings."""

import sys, os, json

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["PYTHONUTF8"] = "1"
from dotenv import load_dotenv

load_dotenv("backend/.env", override=True)

from app.services.llm.groq_service import GroqService

svc = GroqService()
results = []

# ─── Test 1: Each FAQ entry in all 3 languages ─────────────────────────
FAQ_TESTS = {
    "principal": {
        "en": "who is the principal of this college",
        "hi": "कॉलेज के प्रिंसिपल कौन हैं",
        "bn": "এই কলেজের অধ্যক্ষ কে",
    },
    "vice_principal": {
        "en": "who is the vice principal",
        "hi": "वाइस प्रिंसिपल कौन हैं",
        "bn": "ভাইস প্রিন্সিপাল কে",
    },
    "hod_cse": {
        "en": "hod of computer science department",
        "hi": "सीएसई विभाग का एचओडी कौन है",
        "bn": "সিএসই বিভাগের এইচওডি কে",
    },
    "hod_aiml": {
        "en": "hod of artificial intelligence department",
        "hi": "एआई एमएल डिपार्टमेंट का एचओडी कौन है",
        "bn": "সিএসসি আইএমএল বিভাগের এইচওডি কে",
    },
    "hod_csd": {
        "en": "hod of computer science design department",
        "hi": "सीएसडी डिपार्टमेंट का एचओडी कौन है",
        "bn": "সিএসডি বিভাগের এইচওডি কে",
    },
    "fees_cse": {
        "en": "what is the fee for cse",
        "hi": "सीएसई की फीस कितनी है",
        "bn": "সিএসই বিভাগের ফি কত",
    },
    "fees_aiml": {
        "en": "fee for artificial intelligence and machine learning",
        "hi": "एआई एमएल की फीस कितनी है",
        "bn": "এআই এমএল এর ফি কত",
    },
    "fees_me": {
        "en": "mechanical engineering fee",
        "hi": "मैकेनिकल इंजीनियरिंग की फीस",
        "bn": "মেকানিক্যাল ইঞ্জিনিয়ারিং ফি",
    },
    "documents": {
        "en": "what documents needed for admission",
        "hi": "एडमिशन के लिए क्या डॉक्यूमेंट चाहिए",
        "bn": "ভর্তির জন্য কি কি ডকুমেন্ট লাগবে",
    },
    "admission": {
        "en": "how to apply for admission",
        "hi": "एडमिशन के लिए आवेदन कैसे करें",
        "bn": "ভর্তির জন্য কীভাবে আবেদন করবেন",
    },
    "placement": {
        "en": "what is the placement record",
        "hi": "प्लेसमेंट रिकॉर्ड क्या है",
        "bn": "প্লেসমেন্ট রেকর্ড কি",
    },
    "hostel": {
        "en": "tell me about hostel facilities",
        "hi": "हॉस्टल की सुविधाओं के बारे में बताएं",
        "bn": "হোস্টেল সুবিধা সম্পর্কে বলুন",
    },
    "scholarship": {
        "en": "is there any scholarship",
        "hi": "क्या कोई छात्रवृत्ति है",
        "bn": "কোনো স্কলারশিপ আছে কি",
    },
    "courses": {
        "en": "what courses are offered",
        "hi": "कौन से कोर्स ऑफर किए जाते हैं",
        "bn": "কি কি কোর্স অফার করা হয়",
    },
    "wifi": {
        "en": "is there wifi on campus",
        "hi": "क्या कैंपस में वाईफाई है",
        "bn": "ক্যাম্পাসে ওয়াইফাই আছে কি",
    },
    "faculty": {
        "en": "tell me about faculty",
        "hi": "फैकल्टी के बारे में बताएं",
        "bn": "ফ্যাকাল্টি সম্পর্কে বলুন",
    },
    "online_learning": {
        "en": "is online learning available",
        "hi": "क्या ऑनलाइन लर्निंग उपलब्ध है",
        "bn": "অনলাইন লার্নিং পাওয়া যায় কি",
    },
    "campus": {
        "en": "tell me about the campus",
        "hi": "कैंपस के बारे में बताएं",
        "bn": "ক্যাম্পাস সম্পর্কে বলুন",
    },
    "international": {
        "en": "do you accept international students",
        "hi": "क्या अंतर्राष्ट्रीय छात्रों को प्रवेश मिलता है",
        "bn": "আন্তর্জাতিক ছাত্ররা কি ভর্তি হতে পারে",
    },
    "why_bcrec": {
        "en": "why should I choose BCREC",
        "hi": "मुझे बीसीआरईसी क्यों चुनना चाहिए",
        "bn": "কেন আমি বিসিআরইসি বেছে নেব",
    },
    "hidden_charges": {
        "en": "are there any hidden charges",
        "hi": "क्या कोई छिपे हुए शुल्क हैं",
        "bn": "কোনো লুকানো চার্জ আছে কি",
    },
    "refund_policy": {
        "en": "what is the refund policy",
        "hi": "रिफंड पॉलिसी क्या है",
        "bn": "রিফান্ড পলিসি কি",
    },
    "application_status": {
        "en": "how to check application status",
        "hi": "आवेदन की स्थिति कैसे जांचें",
        "bn": "আবেদনের অবস্থা কীভাবে পরীক্ষা করবেন",
    },
    "policies": {
        "en": "what are the college policies",
        "hi": "कॉलेज की नीतियां क्या हैं",
        "bn": "কলেজের নীতিগুলি কি কি",
    },
}

results.append("=" * 60)
results.append("TEST 1: All FAQ entries in English, Hindi, Bengali")
results.append("=" * 60)

for key, langs in FAQ_TESTS.items():
    for lang_code, query in langs.items():
        ans = svc._try_faq(query, lang_code)
        status = "✓" if ans else "✗ MISS"
        results.append(f"  {status} {key}/{lang_code}: {query[:50]}")
        if not ans:
            results.append(f"    → NO ANSWER (LLM fallback would be used)")
    results.append("")

# ─── Test 2: Follow-up scenario (skip-faq logic) ─────────────────────
results.append("=" * 60)
results.append("TEST 2: Follow-up conversation memory (skip-faq logic)")
results.append("=" * 60)

# Simulate: Agent asked "please clarify", user answers "AIML"
history_followup = [
    {"role": "user", "content": "hod of computer science department"},
    {"role": "assistant", "content": "The Head of the CSE department is Dr. Raj Kumar Samanta."},
    {"role": "user", "content": "what about aiml department"},
    {
        "role": "assistant",
        "content": "Could you please specify which department's HOD you are looking for?",
    },
]
followup_query = "artificial intelligence and machine learning"
q = followup_query.lower()
results.append(f'Follow-up: "{followup_query}" after assistant asked "?"')

# This should skip FAQ (no standalone FAQ keywords if we look correctly...)
# Actually "artificial" and "machine learning" ARE FAQ keywords (fee + hod)
# So FAQ should NOT be skipped
has_kw = any(kw in q for kw in svc._all_faq_keywords)
results.append(f"  Has FAQ keywords: {has_kw}")

# Simulate the skip-faq decision
last = history_followup[-1]
skip = last.get("role") == "assistant" and (last.get("content", "") or "").strip().endswith("?")
if skip and not has_kw:
    skip_faq = True
else:
    skip_faq = False
results.append(f"  skip_faq: {skip_faq} (previous was question={skip}, has_keywords={has_kw})")

if skip_faq:
    results.append(f"  → Would skip FAQ, LLM handles with context ✓")
else:
    ans = svc._try_faq(followup_query, "en")
    results.append(f"  → FAQ would fire: {ans[:60] if ans else 'NO MATCH'}")

# Simulate: User asks HOD after greeting (previous greeting ended with ?)
results.append("")
results.append("Scenario: User asks CSD HOD after greeting 'How can I help you today?'")
history_greeting = [
    {"role": "assistant", "content": "Hello! BCREC AI assistant here."},
    {"role": "assistant", "content": "How can I help you today?"},
]
hod_query = "सीएसडी डिपार्टमेंट का एचओडी कौन है"
q2 = hod_query.lower()
has_kw2 = any(kw in q2 for kw in svc._all_faq_keywords)
results.append(f'  Query: "{hod_query}"')
results.append(f"  Has FAQ keywords: {has_kw2}")
if has_kw2:
    ans2 = svc._try_faq(hod_query, "hi")
    results.append(f"  → FAQ result: {ans2[:80] if ans2 else 'NO MATCH'}")
else:
    results.append(f"  → Would incorrectly skip FAQ (BUG)")

# ─── Test 3: Misspellings / edge cases ────────────────────────────────
results.append("")
results.append("=" * 60)
results.append("TEST 3: Misspellings and edge cases")
results.append("=" * 60)

edge_cases = [
    ("en", "principal name", "principal"),
    ("hi", "प्रिंसिपल", "principal"),
    ("bn", "প্রিন্সিপাল", "principal"),
    ("en", "cse hod", "hod_cse"),
    ("hi", "एचओडी सीएसई", "hod_cse"),
    ("en", "aiml fees", "fees_aiml"),
    ("hi", "एएमएल फीस", "fees_aiml"),
    ("bn", "এআইএমএল ফি", "fees_aiml"),
    ("en", "documents for bcrec admission", "documents"),
    ("hi", "बीसीआरईसी में एडमिशन के लिए कागजात", "documents"),
]

for lang, query, expected_key in edge_cases:
    ans = svc._try_faq(query, lang)
    status = "✓" if ans else "✗ MISS"
    results.append(f'  {status} ({lang}) "{query[:40]}" → {ans[:60] if ans else "NO MATCH"}')

# ─── Summary ──────────────────────────────────────────────────────────
results.append("")
results.append("=" * 60)
results.append("SUMMARY")
results.append("=" * 60)

# Count
with open("backend/data/knowledge_base/combined_kb.json", "r", encoding="utf-8") as f:
    data = json.load(f)
vra = data.get("voice_ready_answers", {})
total_entries = len(vra)
total_subs = sum(1 for e in vra.values() if "sub_answers" in e for _ in e.get("sub_answers", {}))
results.append(
    f"Total FAQ entries: {total_entries} (with sub-entries: {total_entries + total_subs})"
)
results.append(f"Total FAQ keywords precomputed: {len(svc._all_faq_keywords)}")
results.append(f"Tests written to test_faq_report.txt")

# Write report
with open("test_faq_report.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))

print("Report written to test_faq_report.txt")
