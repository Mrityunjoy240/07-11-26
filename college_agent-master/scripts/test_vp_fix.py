"""Test VP query fix with semantic anchors."""

import sys, os, asyncio

sys.path.insert(0, "backend")

from app.services.llm.groq_service import get_groq_service
from app.utils.language_detect import detect_language


async def test():
    svc = get_groq_service()
    tests = [
        ("\u0989\u09aa-\u09aa\u09cd\u09b0\u09a7\u09be\u09a8 \u0995\u09c7?", "bn", "Bengali VP"),
        ("Vice Principal kaun hai?", "hi", "Hindi VP"),
        ("Who is the Vice Principal?", "en", "English VP"),
        ("CSE er fee koto?", "bn", "Bengali fee"),
        ("IT HOD kaun hai?", "hi", "Hindi IT HOD"),
    ]
    with open("vp_test_output.txt", "w", encoding="utf-8") as out:
        for query, expected_lang, label in tests:
            detected = detect_language(query)
            lang_ok = detected == expected_lang
            context = svc._retrieve_context(query)
            out.write(f"[{label}]\n")
            out.write(
                f"  Lang: {detected} (expected {expected_lang}) {'OK' if lang_ok else 'FAIL'}\n"
            )
            preview = context[:400] if context else "(empty)"
            out.write(f"  Context: {preview}\n\n")
    print("Done - check vp_test_output.txt")


asyncio.run(test())
