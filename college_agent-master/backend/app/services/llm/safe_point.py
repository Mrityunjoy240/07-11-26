import asyncio
from collections import deque
import logging
import os
import random
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)


try:
    from app.config import settings

    _DEMO_SAFEPOINT_VAL = (
        bool(settings.demo_safepoint) or os.environ.get("DEMO_SAFEPOINT", "").lower() == "true"
    )
except Exception:
    _DEMO_SAFEPOINT_VAL = os.environ.get("DEMO_SAFEPOINT", "").lower() == "true"

DEMO_SAFEPOINT = _DEMO_SAFEPOINT_VAL


def _is_safe_point() -> bool:
    return DEMO_SAFEPOINT


GREETINGS = [
    "Hello, thank you for calling Dr. B.C. Roy Engineering College. How may I assist you today?",
    "Good morning, you have reached Dr. B.C. Roy Engineering College. How can I help you?",
    "Good afternoon, thank you for calling BCREC. How may I help you today?",
    "Good evening, this is Dr. B.C. Roy Engineering College. How can I assist you?",
    "Namaste, you have reached Dr. B.C. Roy Engineering College. How may I help you?",
    "नमस्ते, डॉ. बी.सी. रॉय इंजीनियरिंग कॉलेज में आपका स्वागत है। मैं आपकी कैसे मदद कर सकता हूँ?",
    "নমস্কার, ডাঃ বি.সি. রয় ইঞ্জিনিয়ারিং কলেজে আপনাকে স্বাগত। আমি আপনাকে কীভাবে সাহায্য করতে পারি?",
    "Hello, this is the BCREC admission office. How can I help you today?",
    "Good morning, Dr. B.C. Roy Engineering College. This is the college reception. How may I help you?",
    "Welcome to Dr. B.C. Roy Engineering College. How can I assist you with admissions or general information?",
]

HANDOFF_PATTERNS = re.compile(
    r"\b(human|operator|speak\s*(to|with)|talk\s*(to|with)|connect\s*me|transfer|"
    r"real\s*person|counselor|"
    r"counsellor|receptionist|manager|call\s*me\s*back|callback)\b",
    re.IGNORECASE,
)

HANDOFF_RESPONSES = {
    "principal": "I will connect you to the principal's office. The contact number is 0343-2501353.",
    "accounts": "For accounts and fee-related queries, please contact the accounts office at 0343-2501353.",
    "admission": "For admission-specific queries, the admission office can be reached at 0343-2501353.",
    "human": "Certainly. You can reach the college office at 0343-2501353. Our staff will be happy to help you.",
    "default": "I will share the correct admission office contact. Please call 0343-2501353.",
}

UNKNOWN_RESPONSE = (
    "I am not completely sure about that information, "
    "but I can connect you with the admission office. "
    "Please call 0343-2501353."
)

BENGALI_LOW_CONFIDENCE = "আমি পুরোটা বুঝতে পারিনি। আরেকবার একটু ধীরে বলবেন?"

TIMEOUT_FALLBACK = "I am sorry for the delay. Let me help using the information I already have."


def get_greeting() -> str:
    return random.choice(GREETINGS)


def _detect_handoff(query: str) -> Optional[str]:
    query_lower = query.lower()
    if not HANDOFF_PATTERNS.search(query_lower):
        return None
    for keyword, response in HANDOFF_RESPONSES.items():
        if keyword in query_lower:
            return response
    return HANDOFF_RESPONSES["default"]


def _add_personality(text: str) -> str:
    """Add natural conversational framing to responses.
    Keeps responses clean — no random prefixes or suffixes.
    The structured handlers and LLM prompt already produce complete sentences."""
    return text.strip()


def _is_unknown_response(text: str) -> bool:
    patterns = [
        r"\bi\s+(?:don'?t|do\s+not)\s+(?:know|have)",
        r"\bi\s+(?:couldn'?t|could\s+not)\s+find",
        r"\bno\s+information\b",
        r"\bnot\s+available\b",
        r"\bunable\s+to\b",
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


class DemoLogger:
    MAX_LOG_ENTRIES = 1000

    def __init__(self):
        self.logs: deque = deque(maxlen=self.MAX_LOG_ENTRIES)

    def log(self, session_id: str, entry: dict):
        entry["ts"] = time.time()
        self.logs.append(entry)
        logger.info(f"[DEMO_SAFEPOINT] [{session_id}] {entry}")

    def flush(self, session_id: str):
        relevant = [e for e in self.logs if e.get("session_id") == session_id]
        if relevant:
            logger.debug(f"[DEMO_SAFEPOINT] Flushed {len(relevant)} log entries for {session_id}")


_demo_logger = DemoLogger()


async def safe_generate_response(service, query: str, session_id: str, lang: str) -> dict:
    if not DEMO_SAFEPOINT:
        return None

    t_start = time.time()
    handoff_response = _detect_handoff(query)
    if handoff_response:
        _demo_logger.log(
            session_id,
            {
                "event": "handoff",
                "query": query[:60],
                "latency_ms": round((time.time() - t_start) * 1000),
            },
        )
        result = {
            "answer": handoff_response,
            "voice_text": handoff_response,
            "source": "safe_point_handoff",
            "model": "none",
            "latency_ms": round((time.time() - t_start) * 1000),
            "hallucination_validated": True,
            "tokens": {"prompt": 0, "completion": 0},
            "cache_hit": False,
        }
        return result

    if lang == "bn":
        # The language has already been resolved upstream by the LLM-backed
        # detector (``lang`` is authoritative and generalizes to any romanized
        # text). We only deflect clear *structural* garbage here — never a
        # vocabulary test, because a word list cannot generalize to unseen
        # romanized words ("sub", "bol", "tech", ...). Anything that is real
        # natural language must reach the understanding/LLM pipeline.
        if _is_structural_junk(query):
            _demo_logger.log(
                session_id,
                {
                    "event": "bengali_low_confidence",
                    "query": query[:60],
                },
            )
            result = {
                "answer": BENGALI_LOW_CONFIDENCE,
                "voice_text": BENGALI_LOW_CONFIDENCE,
                "source": "safe_point_bengali",
                "model": "none",
                "latency_ms": round((time.time() - t_start) * 1000),
                "hallucination_validated": True,
                "tokens": {"prompt": 0, "completion": 0},
                "cache_hit": False,
            }
            return result

    return None


def _is_structural_junk(query: str) -> bool:
    """Language-agnostic noise filter.

    Returns ``True`` only for input that is not plausible natural language:
    empty, punctuation/digit-only, or obvious keyboard-mashing. It deliberately
    knows nothing about vocabulary or script, so it generalizes to every
    language and to romanized text with never-before-seen words.

    The decision of *which* language a real query is in is the job of the
    LLM-backed language detector, not this gate.
    """
    s = query.strip()
    if not s:
        return True
    letters = [c for c in s if c.isalpha()]
    # No alphabetic content at all (pure digits / punctuation / symbols).
    if not letters:
        return True
    # A single repeated letter ("aaaaaa") is not a real word.
    if len(letters) >= 6 and len(set(letters)) <= 1:
        return True
    # Extremely low character diversity over a longer string → keyboard mash.
    if len(letters) >= 12 and len(set(letters)) / len(letters) < 0.25:
        return True
    return False


def post_process_response(service, query: str, result: dict, lang: str) -> dict:
    if not DEMO_SAFEPOINT:
        return result
    if not result or not result.get("answer"):
        return result

    answer = result["answer"]
    voice = result.get("voice_text", answer)

    is_fallback = (
        answer == UNKNOWN_RESPONSE or answer == BENGALI_LOW_CONFIDENCE or answer == TIMEOUT_FALLBACK
    )

    if _is_unknown_response(answer):
        answer = UNKNOWN_RESPONSE
        voice = UNKNOWN_RESPONSE
        result["answer"] = answer
        result["voice_text"] = voice
        result["source"] = result.get("source", "") + "+safe_point_unknown"
        is_fallback = True

    if is_fallback:
        return result

    answer = _add_personality(answer)
    voice = _add_personality(voice)

    result["answer"] = answer
    result["voice_text"] = voice
    return result
