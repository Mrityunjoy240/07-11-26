"""
Test the College Voice Agent QA endpoint with typical parent/student questions
in English, Hindi, and Bengali.
"""
import sys
import os
import requests
import json

# Fix Unicode output on Windows
sys.stdout.reconfigure(encoding='utf-8')

URL = "http://localhost:8000/qa/query"
TIMEOUT = 60  # generous timeout

QUESTIONS = [
    # === ENGLISH ===
    ("EN", "What is the BTech CSE fee?"),
    ("EN", "Who is the principal of BCREC?"),
    ("EN", "Is hostel compulsory? What is the hostel fee?"),
    ("EN", "What is the placement record? Which companies visit?"),
    ("EN", "What documents are needed for admission?"),
    ("EN", "Is there any scholarship available?"),
    ("EN", "What is the cutoff rank for CSE?"),

    # === HINDI ===
    ("HI", "BTech CSE की फीस कितनी है?"),
    ("HI", "प्रिंसिपल कौन हैं?"),
    ("HI", "हॉस्टल की फीस क्या है? खाना कैसा है?"),
    ("HI", "प्लेसमेंट कैसा है? कौन सी कंपनियां आती हैं?"),
    ("HI", "एडमिशन के लिए कौन से डॉक्यूमेंट चाहिए?"),

    # === BENGALI ===
    ("BN", "BTech CSE এর ফি কত?"),
    ("BN", "প্রিন্সিপাল কে?"),
    ("BN", "হস্টেলের ফি কত? খাবার কেমন?"),
    ("BN", "প্লেসমেন্ট কেমন? কোন কোম্পানি আসে?"),
    ("BN", "ভর্তির জন্য কী কী ডকুমেন্ট লাগবে?"),
]

print("=" * 70)
print("  COLLEGE VOICE AGENT - QA TEST")
print("=" * 70)

passed = 0
failed = 0

for lang, question in QUESTIONS:
    print(f"\n[{lang}] Q: {question}")
    try:
        resp = requests.post(URL, json={"message": question}, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            answer = data.get("answer", "NO ANSWER")
            print(f"     A: {answer}")
            passed += 1
        else:
            print(f"     ERROR: HTTP {resp.status_code} - {resp.text[:200]}")
            failed += 1
    except requests.exceptions.Timeout:
        print(f"     ERROR: Request timed out after {TIMEOUT}s")
        failed += 1
    except Exception as e:
        print(f"     ERROR: {e}")
        failed += 1

print("\n" + "=" * 70)
print(f"  RESULTS: {passed} PASSED / {failed} FAILED out of {len(QUESTIONS)}")
print("=" * 70)
