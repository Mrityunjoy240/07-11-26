"""Test all 15 quick questions against the RAG pipeline."""

import sys
import os
import asyncio
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.services.llm.groq_service import GroqService, get_groq_service

EN_QS = [
    "What's the CSE fee?",
    "Who is the Vice Principal?",
    "What's the placement rate?",
    "Can I apply for admission?",
    "Is there a hostel?",
]

HI_QS = [
    "CSE ki fees kitni hai?",
    "Vice Principal kaun hai?",
    "Placement rate kya hai?",
    "Kya main admission le sakta hoon?",
    "Kya hostel hai?",
]

BN_QS = [
    "CSE er fee koto?",
    "Upo-pradhan ke?",
    "Placement rate koto?",
    "Ami admission nite pari?",
    "Hostel ache?",
]

PASS_INDICATORS = ["[PASS]", "[FAIL]"]


async def test_questions(lang, questions):
    groq = get_groq_service()
    for i, q in enumerate(questions, 1):
        start = time.time()
        try:
            resp = await groq.generate_response(q, session_id="test_{}_{}".format(lang, i))
        except Exception as e:
            print("Q{}: {} [ERROR] {}ms".format(i, q, 0))
            print("  -> ERROR: {}".format(e))
            continue
        elapsed = round((time.time() - start) * 1000)
        answer = resp.get("answer", "")
        source = resp.get("source", "")
        error_signals = [
            "sorry",
            "something went wrong",
            "don't have",
            "not found",
            "no information",
            "call the college",
        ]
        is_error = any(s in answer.lower() for s in error_signals)
        status = "[FAIL]" if is_error else "[PASS]"
        line1 = "Q{}: {} [{}] {}ms".format(i, status, lang.upper(), elapsed)
        line2 = "  -> {}...".format(answer[:200])
        print(line1)
        try:
            print(line2)
        except UnicodeEncodeError:
            print("  -> [Unicode response - logged to test_results.txt]")
        with open("test_results.txt", "a", encoding="utf-8") as f:
            f.write(line1 + "\n" + line2 + "\n\n")


async def main():
    open("test_results.txt", "w", encoding="utf-8").close()
    print("=" * 72)
    print("BCREC RAG - 15 Quick Questions Test")
    print("=" * 72)
    with open("test_results.txt", "a", encoding="utf-8") as f:
        f.write("BCREC RAG - 15 Quick Questions Test\n" + "=" * 60 + "\n\n")

    for lang, label, qs in [
        ("en", "ENGLISH", EN_QS),
        ("hi", "HINDI", HI_QS),
        ("bn", "BENGALI", BN_QS),
    ]:
        print()
        print("-" * 72)
        print("  " + label)
        print("-" * 72)
        await test_questions(lang, qs)

    print()
    print("=" * 72)
    print("  DONE - check results above")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
