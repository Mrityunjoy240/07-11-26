"""
Groq LLM Service - Clean RAG Architecture
==========================================
Flow: User Query -> Vector Search (top 4 chunks) -> LLM with context -> Answer

No more full KB injection. No conflicting rules. Just simple, clean RAG.

Phase 0 (Hallucination Guardrail):
- After LLM response, extract numbers/entities and verify they exist in context.
- If a critical entity (fee amount, principal name, etc.) is NOT found in the
  retrieved context, replace the answer with a polite fallback.
"""
import logging
import os
import re
import time
import json
import hashlib
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phase 0 — Hallucination guard configuration
# ---------------------------------------------------------------------------
# Toggle validation on/off via env var. Defaults to ON.
HALLUCINATION_GUARD_ENABLED = os.getenv("HALLUCINATION_GUARD_ENABLED", "true").lower() == "true"

# Topics where we MUST validate entities against context.
# For other topics (greetings, general chat) we skip validation.
VALIDATED_TOPICS = {
    "fees", "fee", "hostel", "admission", "principal", "vice_principal",
    "contact", "phone", "email", "address", "placement", "cutoff",
    "scholarship", "documents", "eligibility",
}

FALLBACK_ANSWER_EN = (
    "I'm sorry, I don't have that specific information. "
    "Please call the college at 0343-2501353 for accurate details."
)
FALLBACK_ANSWER_HI = (
    "क्षमा करें, मेरे पास यह विशिष्ट जानकारी नहीं है। "
    "कृपया सटीक जानकारी के लिए कॉलेज को 0343-2501353 पर कॉल करें।"
)
FALLBACK_ANSWER_BN = (
    "দুঃখিত, আমার কাছে এই নির্দিষ্ট তথ্য নেই। "
    "সঠিক তথ্যের জন্য অনুগ্রহ করে কলেজে 0343-2501353 নম্বরে কল করুন।"
)

# ---------------------------------------------------------------------------
# Phase 4 — Query cache configuration
# ---------------------------------------------------------------------------
# Cache TTL (seconds) and max entries. Tunable via env vars.
try:
    import cachetools  # type: ignore
    CACHE_AVAILABLE = True
except ImportError:
    cachetools = None  # type: ignore
    CACHE_AVAILABLE = False
    logger.warning("cachetools not installed — query cache will be disabled")

CACHE_TTL_SECONDS = int(os.getenv("QUERY_CACHE_TTL", "600"))  # 10 min default
CACHE_MAX_ENTRIES = int(os.getenv("QUERY_CACHE_MAX", "256"))

# Combined KB path — used to auto-invalidate cache when the file changes.
_KB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_base" / "combined_kb.json"

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

from app.config import settings
from app.services.vector_store import get_vector_store
from app.utils.language_detect import detect_language


# ---------------------------------------------------------------------------
# System Prompt — Voice-First Telephony Optimization
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an AI admission assistant for Dr. B.C. Roy Engineering College (BCREC), Durgapur.

CRITICAL ROLE CLARITY:
- THE PRINCIPAL (Head of College) is Dr. Sanjay S. Pawar.
- THE VICE PRINCIPAL is Prof. (Dr.) K. M. Hossain.
- If asked "Who is the principal?", always answer: Dr. Sanjay S. Pawar.

FEE ACCURACY & BRANCH CLARITY:
- BE SURGICALLY ACCURATE. Never give ranges or "approximate" figures if the exact number is in the context.
- BRANCH DISTINCTION:
  * CSE (CORE), IT, and ECE have the SAME fee: Rs. 5,98,300.
  * CSE (AI & ML), CSE (Data Science), CSE (Design), and Electrical (EE) have the SAME fee: Rs. 5,47,700.
  * Mechanical (ME) and Civil (CE) have the SAME fee: Rs. 4,37,700.
- If a user asks for "CSE fee", clarify: "CSE Core is five lakh ninety-eight thousand three hundred, while CSE Specializations like AI ML are five lakh forty-seven thousand seven hundred."

PRONUNCIATION & CURRENCY RULES (TTS OPTIMIZATION):
- NEVER use digits (0-9) for fees or amounts.
- ABSOLUTELY FORBIDDEN: "5.98", "6.1", "₹4.5", "Rs. 5,000".
- YOU MUST write the entire number out in words.
- HINDI: Use words like "पाँच लाख" (panch lakh), "छह लाख" (chheh lakh), "चार हजार" (chaar hazaar).
- BENGALI: Use words like "পাঁচ লাখ" (panch lakh), "ছয় লাখ" (chhoy lakh), "দশ হাজার" (dosh hazaar).
- Example Hindi: Instead of "₹4.49 लाख", write "लगभग साढ़े चार लाख रुपये".
- Example Bengali: Instead of "Rs. 5,98,300", write "প্রায় ছয় লাখ টাকা".
- Example English: Instead of "Rs. 5,98,300", write "approximately six lakh rupees".
- This is the ONLY way the TTS will pronounce it correctly.

CRITICAL RULES FOR VOICE INTERACTION (SPEED IS PARAMOUNT):
- BE EXTREMELY CONCISE. Your response must be 1 to 2 short sentences MAX.
- NEVER PROVIDE TABLES, BULLET POINTS, OR NUMBERED LISTS.
- NEVER use filler phrases like "Based on the context". Just state the facts immediately.
- End sentences with a period (.) for immediate TTS start.

LANGUAGE & TRANSLATION RULES (FACTUAL CONSISTENCY IS MANDATORY):
- The facts you provide MUST remain exactly the same regardless of the language you are speaking in.
- If the user writes in Bengali script -> translate the facts to Bengali. Use common English loanwords phonetically. Keep it very short.
- If the user writes in Hindi script -> translate the facts to Hindi. Keep it very short.
- If the user writes in English or Romanized (Banglish/Hinglish) -> reply in the SAME style they used.
- NEVER switch languages mid-response.

CONTENT RULES:
- Answer ONLY from the CONTEXT provided below. Do not make up facts.
- NEVER invent or assume company names. List ONLY the companies explicitly mentioned in the context. If Infosys, Amazon, Flipkart etc. are NOT in the context, do NOT mention them.
- If the context contains pre-formatted voice_ready_answers for the user's language, USE THOSE EXACT WORDS for fees, hostel, and placement answers. Do not rephrase or recalculate numbers.
- If asked about "Departments" or "Admission", list ONLY the main degree categories (B.Tech, MCA, MBA, M.Tech) or the top 3 B.Tech branches.
- If the context does not contain the answer, say so politely and give the college phone: 0343-2501353."""


class GroqService:
    """
    Clean Hybrid RAG service: JSON (Precision) + Vector Store (Context).
    """

    def __init__(self):
        self.model = "llama-3.1-8b-instant"
        self.max_tokens = 256
        self.client = settings.groq_client
        self.async_client = getattr(settings, 'async_groq_client', None)
        self.vector_store = get_vector_store()

        # Load high-precision core knowledge once into memory
        try:
            # backend/app/services/llm/groq_service.py -> .parent x4 -> backend/
            kb_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_base" / "combined_kb.json"
            with open(kb_path, "r", encoding="utf-8") as f:
                self.core_kb = json.load(f)
            logger.info(f"Core Knowledge (JSON) loaded successfully from {kb_path}")
        except Exception as e:
            logger.error(f"Failed to load combined_kb.json: {e}")
            self.core_kb = {}

        # Phase 4 — Query cache (in-memory, TTL-based)
        # Caches the FINAL response by (query, lang, context_hash, kb_mtime).
        # Auto-invalidates if the KB file changes on disk.
        self._cache = None
        self._cache_stats = {"hits": 0, "misses": 0}
        self._kb_mtime = None
        try:
            if _KB_PATH.exists():
                self._kb_mtime = _KB_PATH.stat().st_mtime
        except Exception:
            pass
        if CACHE_AVAILABLE and cachetools is not None:
            self._cache = cachetools.TTLCache(maxsize=CACHE_MAX_ENTRIES, ttl=CACHE_TTL_SECONDS)
            logger.info(
                f"Query cache ENABLED (ttl={CACHE_TTL_SECONDS}s, max={CACHE_MAX_ENTRIES})"
            )
        else:
            logger.info("Query cache DISABLED (cachetools not installed)")

        if self.client:
            logger.info("GroqService ready.")
        else:
            logger.warning("GroqService: Groq client not found. Check GROQ_API_KEY in .env")

    # -----------------------------------------------------------------------
    # Phase 4 — Cache helpers
    # -----------------------------------------------------------------------
    def _cache_key(self, query: str, lang: str, context: str) -> str:
        """Build a stable cache key from query + lang + context + KB mtime."""
        ctx_hash = hashlib.md5(context.encode("utf-8")).hexdigest()[:12] if context else "0"
        return f"{lang}|{query.strip().lower()}|{ctx_hash}|{self._kb_mtime or 0}"

    def _check_kb_changed(self) -> None:
        """Invalidate cache if combined_kb.json mtime changed on disk."""
        try:
            if not _KB_PATH.exists():
                return
            mtime = _KB_PATH.stat().st_mtime
            if self._kb_mtime is None or mtime != self._kb_mtime:
                if self._cache is not None:
                    logger.info("KB file changed on disk — invalidating query cache")
                    self._cache.clear()
                self._kb_mtime = mtime
        except Exception as e:
            logger.debug(f"KB mtime check failed: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Expose hit/miss counts for /metrics later."""
        total = self._cache_stats["hits"] + self._cache_stats["misses"]
        ratio = round(self._cache_stats["hits"] / total, 3) if total else 0.0
        return {
            **self._cache_stats,
            "total": total,
            "hit_ratio": ratio,
            "size": len(self._cache) if self._cache is not None else 0,
            "max_size": CACHE_MAX_ENTRIES,
            "ttl_seconds": CACHE_TTL_SECONDS,
            "enabled": self._cache is not None,
        }

    def invalidate_cache(self) -> int:
        """Manually clear the cache. Returns # of entries cleared."""
        if self._cache is None:
            return 0
        cleared = len(self._cache)
        self._cache.clear()
        logger.info(f"Query cache manually invalidated ({cleared} entries)")
        return cleared

    def _get_precision_context(self, query: str) -> str:
        """Extract relevant parts of the JSON based on keywords (Fast & Accurate)."""
        q = query.lower()
        context_parts = []
        
        # Topic Mapping (Keywords -> JSON Keys)
        mapping = {
            "fees": ["fees_summary", "courses", "scholarships"],
            "fee": ["fees_summary", "courses", "scholarships"],
            "hostel": ["hostel"],
            "admission": ["admission", "admission_documents", "branch_change"],
            "placement": ["placements"],
            "company": ["placements"],
            "cutoff": ["courses"],
            "rank": ["courses", "admission"],
            "contact": ["college", "departments"],
            "principal": ["principal", "vice_principal"],
            "vice": ["vice_principal"],
            "infrastructure": ["infrastructure", "student_life"],
            "courses": ["courses"],
            "branch": ["courses", "branch_change"],
            "scholarship": ["scholarships", "admission"],
            "ragging": ["anti_ragging"],
            "document": ["admission_documents"],
            "hod": ["departments"],
            "head": ["departments", "placements"],
            "department": ["departments"],
            "professor": ["departments", "academics"],
            "faculty": ["departments", "academics"],
            "teacher": ["departments", "academics"],
            "email": ["college", "departments", "principal", "vice_principal"],
            "phone": ["college", "departments", "principal", "vice_principal", "admission", "hostel"],
            "mobile": ["college", "departments", "principal", "vice_principal", "admission", "hostel"],
        }
        
        found_keys = set()
        for topic, keys in mapping.items():
            if topic in q:
                found_keys.update(keys)
        
        # If no specific topic found, give general college info
        if not found_keys:
            found_keys.update(["college", "quick_answers"])
            
        for key in found_keys:
            if key in self.core_kb:
                context_parts.append(f"## {key.upper()}\n{json.dumps(self.core_kb[key], indent=1)}")
                
        return "\n\n".join(context_parts)

    def _retrieve_context(self, query: str) -> str:
        """Combine Precision JSON with Vector Search."""
        # 1. Get high-precision facts from JSON
        precision_ctx = self._get_precision_context(query)
        
        # 2. Get fuzzy context from Vector Store (fallback/extra)
        try:
            results = self.vector_store.search(query, k=2) # Reduced k since we have JSON
            vector_ctx = "\n\n---\n\n".join(doc.page_content for doc in results)
        except Exception:
            vector_ctx = ""
            
        return f"{precision_ctx}\n\n--- ADDITIONAL CONTEXT ---\n\n{vector_ctx}"

    def _build_messages(
        self,
        query: str,
        context: str,
        history: List[Dict],
        lang: str
    ) -> List[Dict]:
        """Build the messages list for Groq API."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add last 6 conversation turns (3 user + 3 assistant) for memory
        if history:
            for turn in history[-6:]:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})

        # Final user message with retrieved context
        lang_hint = {
            "bn": "Reply in Bengali script (বাংলা).",
            "hi": "Reply in Hindi script (हिन्दी).",
            "en": "Reply in English.",
        }.get(lang, "Reply in the same language as the user.")

        user_message = f"""CONTEXT FROM KNOWLEDGE BASE:
{context}

USER QUESTION: {query}

{lang_hint} Answer based only on the context above."""

        messages.append({"role": "user", "content": user_message})
        return messages

    def _is_lang_switch(self, query: str) -> tuple[bool, str | None]:
        """
        Detect if user is just asking to switch language.
        Returns (is_switch, forced_lang_code).
        e.g. "in bengali" → (True, "bn")
             "in hindi" → (True, "hi")
             "in english" → (True, "en")
             "বাংলায় বলো" → (True, "bn")
        """
        q = query.strip().lower()
        patterns = {
            "bn": ["in bengali", "bangla te", "banglay", "বাংলায়", "বাংলা তে", "bengali te", "bengali তে", "bangla y"],
            "hi": ["in hindi", "hindi me", "hindi mein", "हिंदी में", "हिंदी मे"],
            "en": ["in english", "english e", "ইংরেজিতে", "english me"],
        }
        for lang, triggers in patterns.items():
            for t in triggers:
                if t in q or q == t:
                    return True, lang
        return False, None

    def _get_last_user_question(self, history: List[Dict]) -> str | None:
        """Get the most recent user question from conversation history."""
        for turn in reversed(history):
            if turn.get("role") == "user":
                return turn.get("content", "").strip()
        return None

    # -----------------------------------------------------------------------
    # Phase 0 — Hallucination guard
    # -----------------------------------------------------------------------
    def _should_validate(self, query: str) -> bool:
        """Only validate on high-stakes topics (fees, names, contact, etc.)."""
        if not HALLUCINATION_GUARD_ENABLED:
            return False
        q = query.lower()
        return any(topic in q for topic in VALIDATED_TOPICS)

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract verifiable entities from the LLM answer.
        Returns: {"numbers": [...], "names": [...], "phone_like": [...]}
        """
        entities: Dict[str, List[str]] = {
            "numbers": [],
            "names": [],
            "phone_like": [],
        }

        # 1) Numbers (≥3 digit) — likely fee amounts, intakes, cutoffs, percentages
        #    E.g. "598300", "5,98,300", "90%", "180"
        for m in re.finditer(r"\b\d[\d,\.]{2,}\b", text):
            raw = m.group(0)
            # Skip if this number is part of a percentage (e.g., 80.62%)
            end_pos = m.end()
            if end_pos < len(text) and text[end_pos] == '%':
                continue
            num = raw.replace(",", "").replace(".", "")
            if num.isdigit() and len(num) >= 3:
                entities["numbers"].append(num)

        # 2) Percentages like "90%", "85%+"
        for m in re.finditer(r"\b\d{1,3}\s*%(?:\+)?", text):
            entities["numbers"].append(m.group(0).strip().replace("+", ""))

        # 3) Phone-like numbers (10+ digits possibly with hyphens/spaces)
        for m in re.finditer(r"\b\d{4}[\s\-]?\d{3,7}\b", text):
            entities["phone_like"].append(re.sub(r"[\s\-]", "", m.group(0)))

        # 4) Proper nouns / titles: "Dr.", "Prof.", words starting with capital
        #    We only check KNOWN key names below — generic names create noise.
        #    So we leave this empty; number/phone checks are stronger signals.
        return entities

    def _context_contains(self, context: str, entity: str) -> bool:
        """Loose check: does the entity appear anywhere in the retrieved context?"""
        if not entity:
            return True  # vacuously true; nothing to validate
        # Normalize both sides (commas, spaces) for robust matching
        ctx_norm = context.replace(",", "").replace(" ", "").lower()
        ent_norm = entity.replace(",", "").replace(" ", "").lower()
        return ent_norm in ctx_norm

    def _validate_answer(self, answer: str, context: str, query: str) -> tuple[bool, str]:
        """
        Validate that critical entities in `answer` appear in the context.
        Returns (is_valid, reason_if_invalid).
        """
        if not self._should_validate(query):
            return True, ""

        entities = self._extract_entities(answer)

        # Only check numbers and phone-like strings — these are the high-signal
        # hallucination markers. Names are too noisy to check blindly.
        critical = entities["numbers"] + entities["phone_like"]
        if not critical:
            # No verifiable entities extracted → nothing to validate.
            # (Answers like "Yes, hostel is available" pass through.)
            return True, ""

        missing = [e for e in critical if not self._context_contains(context, e)]
        if missing:
            return False, f"entities not found in context: {missing[:5]}"
        return True, ""

    def _safe_fallback(self, lang: str) -> str:
        """Return a polite, language-appropriate fallback message."""
        if lang == "hi":
            return FALLBACK_ANSWER_HI
        if lang == "bn":
            return FALLBACK_ANSWER_BN
        return FALLBACK_ANSWER_EN

    # -----------------------------------------------------------------------
    # Deterministic FAQ — bypasses LLM for common questions
    # -----------------------------------------------------------------------
    def _try_faq(self, query: str, lang: str) -> Optional[str]:
        """Match common questions and return pre-formatted answers directly.
        Returns None if no FAQ match (falls through to LLM)."""
        q = query.lower()
        vra = self.core_kb.get("voice_ready_answers", {})
        if not vra:
            return None

        # --- PRINCIPAL questions ---
        principal_keywords = ["principal", "प्रिंसिपल", "প্রিন্সিপাল", "প্রধান", "head of college"]
        if any(k in q for k in principal_keywords):
            principal_answers = {
                "en": "The principal of BCREC is Dr. Sanjay S. Pawar.",
                "hi": "बीसीआरईसी के प्रिंसिपल डॉ. संजय एस. पवार हैं।",
                "bn": "বিসিআরইসি এর প্রিন্সিপাল হলেন ড. সঞ্জয় এস পাওয়ার।"
            }
            return principal_answers.get(lang, principal_answers["en"])

        # --- HOD questions ---
        hod_keywords = ["hod", "head of department", "head of the department", "विभाग अध्यक्ष", "বিভাগীয় প্রধান", "विभाग प्रमुख"]
        if any(k in q for k in hod_keywords):
            # Detect department
            if "cse" in q or "computer science" in q:
                return {
                    "en": "The Head of the CSE department is Dr. Raj Kumar Samanta.",
                    "hi": "सीएसई विभाग के अध्यक्ष डॉ. राज कुमार सामंत हैं।",
                    "bn": "সিএসই বিভাগের প্রধান হলেন ড. রাজ কুমার সামন্ত।"
                }.get(lang, "The Head of the CSE department is Dr. Raj Kumar Samanta.")
            elif "it" in q or "information tech" in q:
                return {
                    "en": "The Head of the Information Technology department is Dr. Dinesh Kumar Pradhan.",
                    "hi": "इंफॉर्मेशन टेक्नोलॉजी विभाग के अध्यक्ष डॉ. दिनेश कुमार प्रधान हैं।",
                    "bn": "ইনফরমেশন টেকনোলজি বিভাগের প্রধান হলেন ড. দীনেশ কুমার প্রধান।"
                }.get(lang, "The Head of the Information Technology department is Dr. Dinesh Kumar Pradhan.")
            elif "ece" in q or "electronics" in q:
                return {
                    "en": "The Head of the ECE department is Dr. Mrinmoy Chakraborty.",
                    "hi": "ईसीई विभाग के अध्यक्ष डॉ. मृण्मय चक्रवर्ती हैं।",
                    "bn": "ইসিই বিভাগের প্রধান হলেন ড. মৃন্ময় চক্রবর্তী।"
                }.get(lang, "The Head of the ECE department is Dr. Mrinmoy Chakraborty.")
            elif "ee" in q or "electrical" in q:
                return {
                    "en": "The Head of the Electrical Engineering department is Dr. Shibendu Mahata.",
                    "hi": "इलेक्ट्रिकल इंजीनियरिंग विभाग के अध्यक्ष डॉ. शिबेंदु महता हैं।",
                    "bn": "ইলেকট্রিক্যাল ইঞ্জিনিয়ারিং বিভাগের প্রধান হলেন ড. শিবেন্দু মাহাতো।"
                }.get(lang, "The Head of the Electrical Engineering department is Dr. Shibendu Mahata.")
            elif "mechanical" in q or "me" in q:
                return {
                    "en": "The Head of the Mechanical Engineering department is Dr. Chandan Chattoraj.",
                    "hi": "मैकेनिक इंजीनियरिंग विभाग के अध्यक्ष डॉ. चंदन चट्टोराज हैं।",
                    "bn": "মেকানিক্যাল ইঞ্জিনিয়ারিং বিভাগের প্রধান হলেন ড. চন্দন চট্টরাজ।"
                }.get(lang, "The Head of the Mechanical Engineering department is Dr. Chandan Chattoraj.")
            elif "civil" in q or "ce" in q:
                return {
                    "en": "The Head of the Civil Engineering department is Dr. Sanjay Sengupta.",
                    "hi": "सिविल इंजीनियरिंग विभाग के अध्यक्ष डॉ. संजय सेनगुप्ता हैं।",
                    "bn": "সিভিল ইঞ্জিনিয়ারিং বিভাগের প্রধান হলেন ড. সঞ্জয় সেনগুপ্ত।"
                }.get(lang, "The Head of the Civil Engineering department is Dr. Sanjay Sengupta.")
            elif "aiml" in q or "artificial" in q:
                return {
                    "en": "The Head of the Artificial Intelligence and Machine Learning department is Dr. Gour Sundar Mitra Thakur.",
                    "hi": "एआई एमएल विभाग के अध्यक्ष डॉ. गौर सुंदर मित्रा ठाकुर हैं।",
                    "bn": "এআই এমএল বিভাগের প্রধান হলেন ড. গৌর সুন্দর মিত্র ঠাকুর।"
                }.get(lang, "The Head of the Artificial Intelligence and Machine Learning department is Dr. Gour Sundar Mitra Thakur.")
            elif "data science" in q or "ds" in q:
                return {
                    "en": "The Head of the Data Science department is Dr. Chandan Bandyopadhyay.",
                    "hi": "डाटा साइंस विभाग के अध्यक्ष डॉ. चंदन बंद्योपाध्याय हैं।",
                    "bn": "ডাটা সায়েন্স বিভাগের প্রধান হলেন ড. চন্দন বন্দ্যোপাধ্যায়।"
                }.get(lang, "The Head of the Data Science department is Dr. Chandan Bandyopadhyay.")
            elif "cyber" in q or "cy" in q:
                return {
                    "en": "The Head of the Cyber Security department is Dr. Gour Sundar Mitra Thakur.",
                    "hi": "साइबर सिक्योरिटी विभाग के अध्यक्ष डॉ. गौर सुंदर मित्रा ठाकुर हैं।",
                    "bn": "সাইবার সিকিউরিটি বিভাগের প্রধান হলেন ড. গৌর সুন্দর মিত্র ঠাকুর।"
                }.get(lang, "The Head of the Cyber Security department is Dr. Gour Sundar Mitra Thakur.")
            elif "design" in q or "csd" in q:
                return {
                    "en": "The Head of the Computer Science and Design department is Dr. Poulomi Mukherjee Tewari.",
                    "hi": "कंप्यूटर साइंस एंड डिज़ाइन विभाग के अध्यक्ष डॉ. पौलोमी मुखर्जी तिवारी हैं।",
                    "bn": "কম্পিউটার সায়েন্স অ্যান্ড ডিজাইন বিভাগের প্রধান হলেন ড. পৌলমী মুখার্জী তিওয়ারী।"
                }.get(lang, "The Head of the Computer Science and Design department is Dr. Poulomi Mukherjee Tewari.")
            elif "mba" in q or "management" in q:
                return {
                    "en": "The Head of the MBA department is Somroop Siddhanta.",
                    "hi": "एमबीए विभाग के अध्यक्ष सोमरूप सिद्धांत हैं।",
                    "bn": "এমবিএ বিভাগের প্রধান হলেন সোমরূপ সিদ্ধান্ত।"
                }.get(lang, "The Head of the MBA department is Somroop Siddhanta.")
            elif "mca" in q or "application" in q:
                return {
                    "en": "The Head of the MCA department is Dr. Pabitra Kumar Dey.",
                    "hi": "एमसीए विभाग के अध्यक्ष डॉ. पवित्र कुमार डे हैं।",
                    "bn": "এমসিএ বিভাগের প্রধান হলেন ড. পবিত্র কুমার দে।"
                }.get(lang, "The Head of the MCA department is Dr. Pabitra Kumar Dey.")
            else:
                return {
                    "en": "Could you please specify which department's HOD you are looking for? We have CSE, IT, ECE, EE, MCA, MBA, and other departments.",
                    "hi": "कृपया स्पष्ट करें कि आप किस विभाग के एचओडी की तलाश कर रहे हैं? हमारे पास सीएसई, आईटी, ईसीई, ईई, एमसीए, एमबीए और अन्य विभाग हैं।",
                    "bn": "দয়া করে নির্দিষ্ট করুন আপনি কোন বিভাগের এইচওডির খোঁজ করছেন? আমাদের সিএসই, আইটি, ইসিই, ইই, এমসিএ, এমবিএ এবং অন্যান্য বিভাগ রয়েছে।"
                }.get(lang, "Could you please specify which department's HOD you are looking for?")

        # --- HOSTEL questions ---
        hostel_keywords = ["hostel", "हॉस्टल", "হস্টেল", "হোস্টেল", "হসটেল", "mess", "food", "खाना", "খাবার", "ডাইনিং"]
        if any(k in q for k in hostel_keywords):
            hostel = vra.get("hostel", {})
            ans = hostel.get(lang) or hostel.get("en")
            if ans: return ans

        # --- PLACEMENT questions ---
        placement_keywords = ["placement", "प्लेसमेंट", "প্লেসমেন্ট", "company", "कंपनी", "কোম্পানি", "recruit", "package", "salary", "पैकेज", "প্যাকেজ", "চাকরি"]
        if any(k in q for k in placement_keywords):
            placement = vra.get("placement", {})
            ans = placement.get(lang) or placement.get("en")
            if ans: return ans

        # --- DOCUMENTS questions ---
        documents_keywords = ["document", "documents", "डॉक्यूमेंट", "दस्तावेज", "ডকুমেন্ট", "কাগজপত্র", "certificate", "marksheet", "মাকশিট", "মার্কশিট", "সার্টিফিকেট", "admit card"]
        if any(k in q for k in documents_keywords):
            documents = vra.get("documents", {})
            ans = documents.get(lang) or documents.get("en")
            if ans: return ans

        # --- SCHOLARSHIP questions ---
        scholarship_keywords = ["scholarship", "scholarships", "स्कॉलरशिप", "छात्रवृत्ति", "স্কলারশিপ", "বৃত্তি", "tfw", "svmcm", "kanyashree", "oasis", "aikyashree"]
        if any(k in q for k in scholarship_keywords):
            scholarship = vra.get("scholarship", {})
            ans = scholarship.get(lang) or scholarship.get("en")
            if ans: return ans

        # --- FEE questions ---
        fee_keywords = ["fee", "fees", "फीस", "ফি", "cost", "price", "खर्च", "খরচ"]
        if any(k in q for k in fee_keywords):
            fees = vra.get("fees", {})
            # Detect which branch
            cse_keys = ["cse", "computer", "सीएसई", "সিএস"]
            it_keys = [" it ", "information tech"]
            ece_keys = ["ece", "electronics", "ईसीई", "ইসিই"]
            ee_keys = [" ee ", "electrical", "ईई", "ইই"]
            aiml_keys = ["aiml", "ai ml", "ai-ml", "artificial", "machine learning"]
            ds_keys = ["data science", " ds "]
            me_keys = ["mechanical", " me ", "मैकेनिकल", "মেকানিকাল"]
            ce_keys = ["civil", " ce ", "सिविल", "সিভিল"]
            mba_keys = ["mba"]
            mca_keys = ["mca"]
            cy_keys = ["cyber", " cy "]
            csd_keys = ["design", "csd"]

            if any(k in q for k in me_keys + ce_keys):
                ans = fees.get("me_ce", {}).get(lang) or fees.get("me_ce", {}).get("en")
                if ans: return ans
            elif any(k in q for k in ee_keys + aiml_keys + ds_keys + cy_keys + csd_keys):
                ans = fees.get("ee_aiml_ds_cy_csd", {}).get(lang) or fees.get("ee_aiml_ds_cy_csd", {}).get("en")
                if ans: return ans
            elif any(k in q for k in mba_keys):
                ans = fees.get("mba", {}).get(lang) or fees.get("mba", {}).get("en")
                if ans: return ans
            elif any(k in q for k in mca_keys):
                ans = fees.get("mca", {}).get(lang) or fees.get("mca", {}).get("en")
                if ans: return ans
            elif any(k in q for k in cse_keys + it_keys + ece_keys):
                ans = fees.get("cse_it_ece", {}).get(lang) or fees.get("cse_it_ece", {}).get("en")
                if ans: return ans
            else:
                # General fee question — give CSE fee as primary + mention range
                ans = fees.get("cse_it_ece", {}).get(lang) or fees.get("cse_it_ece", {}).get("en")
                if ans: return ans

        return None  # No FAQ match — fall through to LLM

    async def generate_response(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Main entry point. Returns dict with 'answer', 'voice_text', 'source'."""
        if not self.client:
            return {"answer": "Service unavailable. Please call 0343-2501353.", "voice_text": "", "source": "error"}

        start = time.time()
        try:
            history = conversation_history or []

            # 1. Check if user is just switching language (e.g. "in bengali")
            is_switch, forced_lang = self._is_lang_switch(query)
            if is_switch and forced_lang and history:
                # Re-run the PREVIOUS user question in the new language
                prev_question = self._get_last_user_question(history[:-1] if history else [])
                if prev_question:
                    query = prev_question
                    logger.info(f"Language switch detected → re-running '{query[:50]}' in lang={forced_lang}")
                lang = forced_lang
            else:
                # 2. Detect language normally
                lang = detect_language(query)

            # 2.5 Deterministic FAQ — bypass LLM for common questions
            faq_answer = self._try_faq(query, lang)
            if faq_answer:
                latency_ms = round((time.time() - start) * 1000)
                logger.info(f"\u26a1 FAQ HIT (lang={lang}, {latency_ms}ms): '{query[:60]}'")
                return {
                    "answer": faq_answer,
                    "voice_text": faq_answer,
                    "source": "faq_deterministic",
                    "model": "none",
                    "latency_ms": latency_ms,
                    "hallucination_validated": True,
                    "tokens": {"prompt": 0, "completion": 0},
                    "cache_hit": False,
                }

            # 3. Retrieve relevant context via vector search
            context = self._retrieve_context(query)

            # 4. Phase 4 — Cache lookup (skip if there's chat history — context depends on it)
            #    Cache only stateless, fact-lookup queries. Conversational turns stay live.
            if self._cache is not None and not history:
                self._check_kb_changed()
                cache_key = self._cache_key(query, lang, context)
                cached = self._cache.get(cache_key)
                if cached is not None:
                    self._cache_stats["hits"] += 1
                    latency_ms = round((time.time() - start) * 1000)
                    logger.info(
                        f"⚡ CACHE HIT (lang={lang}, {latency_ms}ms): '{query[:60]}'"
                    )
                    cached_out = dict(cached)
                    cached_out["latency_ms"] = latency_ms
                    cached_out["cache_hit"] = True
                    return cached_out
                self._cache_stats["misses"] += 1

            # 5. Build messages with history + context
            messages = self._build_messages(
                query=query,
                context=context,
                history=history,
                lang=lang
            )

            # 6. Call Groq
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=self.max_tokens,
            )

            answer = completion.choices[0].message.content.strip()

            # 7. Phase 0 — Hallucination guard: verify entities against context
            is_valid, reason = self._validate_answer(answer, context, query)
            if not is_valid:
                logger.warning(
                    f"PHASE 0 GUARD TRIPPED (lang={lang}, query='{query[:60]}'): {reason}. "
                    f"LLM said: '{answer[:80]}'"
                )
                answer = self._safe_fallback(lang)

            # 8. Currency normalization for Bengali
            if lang == "bn":
                answer = answer.replace("রুপি", "টাকা").replace("টাকা.", "টাকা।")

            # 9. Phase 0 — Token usage tracking (best-effort; free tier so cost=0)
            prompt_tokens = 0
            completion_tokens = 0
            try:
                usage = getattr(completion, "usage", None)
                if usage:
                    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            except Exception:
                pass
            latency_ms = round((time.time() - start) * 1000)
            logger.info(
                f"Groq response ({lang}, {latency_ms}ms, validated={is_valid}, "
                f"tokens=in:{prompt_tokens}/out:{completion_tokens}): {answer[:80]}..."
            )

            response_payload: Dict[str, Any] = {
                "answer": answer,
                "voice_text": answer,  # same text — voice_utils will clean it
                "source": "groq_rag",
                "model": self.model,
                "latency_ms": latency_ms,
                "hallucination_validated": is_valid,
                "tokens": {
                    "prompt": prompt_tokens,
                    "completion": completion_tokens,
                },
                "cache_hit": False,
            }

            # 10. Phase 4 — Store in cache (only if validated AND no chat history)
            if self._cache is not None and is_valid and not history:
                try:
                    cache_key = self._cache_key(query, lang, context)
                    self._cache[cache_key] = response_payload
                except Exception as e:
                    logger.debug(f"Cache store failed: {e}")

            return response_payload

        except Exception as e:
            logger.error(f"Groq error: {e}")
            return {
                "answer": "Sorry, something went wrong. Please call the college at 0343-2501353.",
                "voice_text": "Sorry, something went wrong.",
                "source": "error",
                "cache_hit": False,
            }

    async def stream_response(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ):
        """Streaming version for low-latency web/voice UI."""
        if not self.async_client:
            yield "Service unavailable. Please call 0343-2501353."
            return

        try:
            history = conversation_history or []
            lang = detect_language(query)
            context = self._retrieve_context(query)
            messages = self._build_messages(query, context, history, lang)

            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=self.max_tokens,
                stream=True
            )

            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content

        except Exception as e:
            logger.error(f"Groq stream error: {e}")
            yield "Sorry, something went wrong."

    def is_available(self) -> bool:
        return self.client is not None


# Singleton
_groq_service = None

def get_groq_service() -> GroqService:
    global _groq_service
    if _groq_service is None:
        _groq_service = GroqService()
    return _groq_service
