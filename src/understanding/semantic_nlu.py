"""
Hybrid semantic NLU for the understanding layer.

Architecture (per the understanding-layer contract):

    USER MESSAGE
        │
        ├─ 1. Fast semantic reading (local, deterministic, ~sub-ms)
        │      canonical intents + entities + language + confidence
        │
        │   confident? ── yes ──► return (source="deterministic")
        │
        ├─ 2. Semantic NLU via LLM (only when the fast reading is unsure)
        │      strict JSON schema, validated against the shared taxonomy
        │
        │   parseable? ── yes ──► return (source="semantic_nlu")
        │
        └─ 3. Safe fallback → low-confidence deterministic reading
               (never crash, never fabricate, never "clarify" on a panic)

The NLU is an *interpreter* only: it turns natural language (including typos,
informal/Banglish/Hinglish and short context-dependent follow-ups) into a
canonical structured object. It does NOT decide eligibility, cutoffs, policy,
answers, or knowledge retrieval — those stay in the deterministic brain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.llm.interfaces import LLMAdapter
from src.understanding.llm_intent import VALID_INTENTS, parse_llm_json

# The semantic NLU's canonical intent vocabulary. ``category`` is a genuine
# profile-fact reading the deterministic taxonomy cannot express directly;
# the engine maps it onto the committed conversation topic before the brain.
_NLU_INTENTS = (*VALID_INTENTS, "category")

# ── Small deterministic vocabulary (typo-tolerant) ──────────────────────────
# No per-phrase regex patches: fuzzy word matching on a handful of canonical
# triggers covers typo/informal variants ("genral", "chatagory", "healp").

CATEGORIES: dict[str, tuple[str, ...]] = {
    "general": ("general", "gen", "ur", "unreserved", "general category", "gn"),
    "obc": ("obc", "other backward", "other backward class"),
    "sc": ("sc", "scheduled caste"),
    "st": ("st", "scheduled tribe"),
    "ews": ("ews", "economically weaker", "economically weaker section"),
}

BRANCHES: dict[str, tuple[str, ...]] = {
    "CSE": ("cse", "computer science", "computer", "cs", "comp science", "computar"),
    "ECE": ("ece", "electronics", "electronics and communication", "e and c", "ec"),
    "EE": ("ee", "electrical", "electrical engineering", "elec"),
    "ME": ("mechanical", "mechanical engineering", "mech", "machanical"),
    "CE": ("ce", "civil", "civil engineering"),
    "IT": ("it", "information technology", "info tech"),
    "Biotechnology": ("biotech", "biotechnology", "bio tech"),
    "AI": ("ai", "ai ml", "artificial intelligence", "aiml"),
    "Data Science": ("data science", "data analytics"),
    "Cyber Security": ("cyber security", "cybersecurity", "cyber"),
}

_QUESTION_MARKERS = re.compile(
    r"\b(?:what|which|how|why|when|where|who|is|are|does|do|can|"
    r"kya|kaun|kon|ki|koto|keno|kivabe|kab|kobe|কী|কি|কোন|কেন|কবে|क्या|कौन|कब|कैसे)\b",
    re.IGNORECASE,
)

_DOMAIN_HINT = re.compile(
    r"\b(?:college|university|institute|campus|admission|admit|apply|"
    r"hostel|stay|accommodation|room\b|fee\b|fees|tuition|placement|"
    r"scholarship|course|branch|engineering|exam|rank|percentage|quota|"
    r"cutoff|counsel\b|syllabus|subject|backlog|arrear|hostel|loan|"
    r"ভর্তি|হোস্টেল|ক্লাস|স্কলারশিপ|छात्रावास|कॉलेज|भर्ती)\b",
    re.IGNORECASE,
)

_GREETINGS = (
    "hi", "hello", "hey", "hola", "namaste", "namaskar", "namaskaram",
    "vanakkam", "hy", "hii", "helo", "hiiiii", "হ্যালো", "নমস্কার", "নমশকার",
    "नमस्ते", "नमस्कार", "हेलो",
)
_GREETING_PHRASES = (
    ("good", "morning"), ("good", "afternoon"), ("good", "evening"),
    ("good", "morning", "ji"), ("good", "evening", "ji"),
)

_HELP_TRIGGERS = (("help",), ("help", "me"), ("help", "me", "out"), ("need", "help"),
                  ("madad",), ("madad", "karo"), ("help", "chahiye"))
_SELFINTRO_TRIGGERS = (
    ("who", "are", "you"), ("what", "are", "you"), ("about", "you"),
    ("introduce", "yourself"), ("tell", "me", "about", "yourself"),
    ("who", "r", "you"), ("tu", "ke"), ("ken", "tui"),
    ("tum", "kaun", "ho"), ("aap", "kaun", "ho"), ("kaun", "ho"),
)
_SOCIAL_TRIGGERS = (
    ("im", "back"), ("i", "am", "back"), ("i", "m", "back"),
    ("am", "back"), ("i", "came", "back"), ("are", "you", "there"),
    ("are", "u", "there"), ("welcome", "back"),
)
_CLOSING_TRIGGERS = (
    ("thank"), ("thanks"), ("thank", "you"), ("thnx"), ("thx"),
    ("dhonnobad"), ("dhonyobad"), ("dhanyavad"), ("ধন্যবাদ"),
)

_INTENT_TRIGGERS: dict[str, tuple[tuple[str, ...], ...]] = {
    "backlog": (
        ("backlog",), ("back", "in"), ("back", "ase"), ("back", "ache"),
        ("back", "hai"), ("got", "back"), ("arrear",), ("arrears",),
        ("failed",), ("fail", "in"), ("failed", "subject"), ("clear",),
        ("cleared",), ("supplementary",), ("reappear",), ("supply",),
        ("carry", "over"), ("ব্যাকলগ",),
    ),
    "fee": (
        ("fee",), ("fees",), ("tuition",), ("fee", "structure"),
        ("how", "much"), ("cost",), ("koto", "taka"), ("koto", "fee"),
        ("fees", "kitna"), ("kitna", "fee"), ("কত", "টাকা"), ("ফি",),
        ("शुल्क",), ("फीस",),
    ),
    "scholarship": (
        ("scholarship",), ("stipend",), ("financial", "aid"),
        ("fee", "waiver"), ("concession",), ("freeship",),
        ("post", "matric"), ("scolarship",), ("স্কলারশিপ",), ("छात्रवृत्ति",),
    ),
    "program": (
        ("subjects",), ("subject",), ("syllabus",), ("curriculum",),
        ("course", "content"), ("topics",), ("study",), ("learn",),
        ("what", "do", "you", "teach"), ("taught",), ("modules",),
        ("সিলেবাস",), ("পাঠ্যক্রম",), ("पाठ्यक्रम",),
    ),
    "hostel": (
        ("hostel",), ("dorm",), ("accommodation",), ("boarding",),
        ("mess",), ("room",), ("warden",), ("हॉस्टल",), ("হস্টেল",), ("होस्टल",),
        ("hostel", "fee"), ("hostel", "facility"),
    ),
    "admission": (
        ("admission",), ("apply",), ("eligib",), ("can", "i", "get"),
        ("get", "admission"), ("admit",), ("admission", "process"),
        ("admission", "form"), ("form", "fill"), ("ভর্তি",), ("प्रवेश",),
    ),
    "placement": (
        ("placement",), ("placements",), ("package",), ("salary",),
        ("job",), ("recruit",), ("ctc",), ("lpa",), ("प्लेसमेंट",),
        ("প্লেসমেন্ট",), ("recruiter",), ("company", "visit"),
    ),
    "cutoff": (
        ("cutoff",), ("cut", "off"), ("closing", "rank"), ("previous", "year"),
        ("last", "year", "rank"), ("কাটঅফ",), ("कटऑफ",),
    ),
    "help_request": _HELP_TRIGGERS,
    "self_introduction": _SELFINTRO_TRIGGERS,
    "social_return": _SOCIAL_TRIGGERS,
    "greeting": (),
    "career_confusion": (
        ("confused",), ("confusion",), ("not", "sure"), ("dilemma",),
        ("what", "should", "i", "do"), ("what", "to", "choose"),
        ("confused", "about"), ("don", "know", "what"),
        ("কনফিউশন",), ("দ্বিধা",), ("कन्फ्यूज",),
    ),
    "safety": (
        ("safe",), ("safety",), ("security",), ("secure", "campus"),
        ("girls", "safe"), ("সুরক্ষা",), ("নিরাপত্তা",), ("सुरक्षा",),
    ),
    "grievance": (
        ("grievance",), ("complaint",), ("rechecking",), ("re", "evaluation"),
        ("marks", "lower"), ("not", "renewed"), ("hasn", "renewed"),
        ("অভিযোগ",), ("शिकायत",),
    ),
    "seats": (
        ("seat",), ("seats",), ("intake",), ("capacity",), ("strength",),
        ("how", "many", "students"), ("সিট",), ("सीट",),
    ),
    "document": (
        ("document",), ("documents",), ("certificate",), ("marksheet",),
        ("transcript",), ("proof",), ("ডকুমেন্ট",), ("प्रमाणपत्र",),
    ),
    "loan": (
        ("loan",), ("education", "loan"), ("student", "loan"),
        ("bank", "loan"), ("ঋণ",), ("कर्ज",), ("लोन",),
    ),
    "transfer": (
        ("transfer",), ("migration",), ("change", "college"),
        ("switch", "college"), ("শিফট",), ("स्थानांतरण",),
    ),
    "lateral_entry": (
        ("lateral",), ("diploma",), ("jexpo",), ("direct", "second", "year"),
        ("polytechnic",), ("डिप्लोमा",),
    ),
    "management_quota": (
        ("management", "quota"), ("donation",), ("paid", "seat"),
        ("management", "seat"),
    ),
    "nri_admission": (
        ("nri",), ("foreign",), ("abroad",), ("international", "student"),
        ("नरई",),
    ),
    "sports_quota": (
        ("sports", "quota"), ("sports", "admission"), ("athlete",),
        ("sports", "seat"), ("sports", "certificate"),
    ),
    "distance_education": (
        ("distance",), ("distance", "education"), ("online", "course"),
        ("online", "degree"), ("correspondence",), ("distance", "learning"),
    ),
    "counseling_info": (
        ("counseling",), ("counselling",), ("allotment",),
        ("choice", "filling"), ("mock", "round"), ("কাউন্সেলিং",),
        ("काउंसलिंग",),
    ),
    "institution": (
        ("college", "located"), ("college", "address"), ("college", "location"),
        ("college", "contact"), ("college", "phone"), ("college", "email"),
        ("where", "is", "the", "college"), ("college", "name"),
        ("college", "affiliation"),
    ),
    "repeat": (
        ("repeat",), ("again",), ("say", "again"), ("what", "said"),
        ("dubara",), ("fir", "se"),
    ),
}

# Non-domain triggers never commit a conversation topic on their own.
_CONVERSATIONAL_LABELS = frozenset(
    {"greeting", "help_request", "self_introduction", "social_return", "closing"}
)

_OVERLAP = (
    "when is", "which is", "how much", "what about", "what are", "what is",
    "how to", "is there", "does the",
)

# ── Fuzzy helpers (edit-distance based, no per-phrase regexes) ──────────────


def _normalize(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum() or ch.isspace())


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) > len(b):
        a, b = b, a
    prev = list(range(len(a) + 1))
    for j, cb in enumerate(b, 1):
        cur = [j]
        for i, ca in enumerate(a, 1):
            cur.append(min(
                cur[i - 1] + 1,
                prev[i] + 1,
                prev[i - 1] + (ca != cb),
            ))
        prev = cur
    return prev[-1]


def _word_ratio(a: str, b: str) -> float:
    if a == b:
        return 1.0
    return 1.0 - _edit_distance(a, b) / max(len(a), len(b))


def _token_ok(token: str, trigger: str) -> bool:
    """A token matches a trigger word, tolerating typos of reasonable size.

    Guards against false positives: fuzzy matches must share the first two
    characters and be within one character of the trigger's length, so e.g.
    ``hote``/``hostel``, ``btech``/``biotech`` and ``general``/``lateral``
    never collide while ``genral``/``general`` and ``chatagory``/``category``
    still match.
    """
    if token == trigger:
        return True
    if len(trigger) <= 2:
        return False
    if len(token) < 2 or token[:2] != trigger[:2]:
        return False
    if abs(len(token) - len(trigger)) > 1:
        return False
    if len(trigger) == 3:
        return _word_ratio(token, trigger) >= 0.75
    return _word_ratio(token, trigger) >= 0.65


def _match_phrase(tokens: list[str], phrase: tuple[str, ...]) -> bool:
    """True when every trigger word appears in order (fuzzy) in the text."""
    if not phrase:
        return False
    i = 0
    for trig in phrase:
        found = False
        while i < len(tokens):
            if _token_ok(tokens[i], trig):
                i += 1
                found = True
                break
            i += 1
        if not found:
            return False
    return True


def _fuzzy_find_token(tokens: list[str], trigger: str) -> int:
    """Index of the first token fuzzy-matching ``trigger``, else -1."""
    for i, tok in enumerate(tokens):
        if _token_ok(tok, trigger):
            return i
    return -1


def _first_token_is(tokens: list[str], candidates: tuple[str, ...]) -> bool:
    for cand in candidates:
        if _token_ok(tokens[0], cand):
            return True
    return False


# ── Entity extraction (separate from intent) ────────────────────────────────

_RE_RANK = re.compile(
    r"(?:rank|air|ran)\s*(?:is|:)?\s*(\d{1,6})(?:\s*[kK])?"
    r"|(\d{1,6})\s*(?:rank|air|ran)\b",
    re.IGNORECASE,
)
_RE_RANK_K = re.compile(r"\b(\d{1,3})\s*[kK]\b")
_RE_PERCENT = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*%"
    r"|(\d{1,3}(?:\.\d+)?)\s*(?:pcm|percentage|percent|marks|aggregate)",
    re.IGNORECASE,
)

_SUBJECT_COUNT = {
    "one": 1, "a": 1, "an": 1, "single": 1, "ek": 1, "akta": 1, "1": 1,
    "two": 2, "duti": 2, "2": 2,
    "three": 3, "tin": 3, "3": 3,
    "four": 4, "char": 4, "4": 4,
    "five": 5, "panch": 5, "5": 5,
}


def _extract_rank(text: str) -> tuple[int | None, float]:
    m = _RE_RANK.search(text)
    if m:
        raw = m.group(1) or m.group(2)
        return int(raw), 0.95
    m = _RE_RANK_K.search(text)
    if m:
        return int(m.group(1)) * 1000, 0.8
    return None, 0.0


def _extract_percentage(text: str) -> tuple[float | None, float]:
    m = _RE_PERCENT.search(text)
    if m:
        value = float(m.group(1) or m.group(2))
        if 0 <= value <= 100:
            return value, 0.95
    return None, 0.0


def _extract_category(text: str) -> tuple[str, float]:
    tokens = _normalize(text).split()
    best, best_score = "", 0.0
    for canonical, aliases in CATEGORIES.items():
        for alias in aliases:
            if " " in alias:
                if _match_phrase(tokens, tuple(alias.split())):
                    score = 0.98
                else:
                    continue
            else:
                idx = _fuzzy_find_token(tokens, alias)
                if idx < 0:
                    continue
                score = 0.95 if tokens[idx] == alias else 0.9
            if score > best_score:
                best, best_score = canonical, score
    return best, best_score


def _extract_branch(text: str) -> tuple[str, float]:
    tokens = _normalize(text).split()
    best, best_score = "", 0.0
    for canonical, aliases in BRANCHES.items():
        for alias in aliases:
            if " " in alias:
                if _match_phrase(tokens, tuple(alias.split())):
                    score = 0.95
                else:
                    continue
            else:
                idx = _fuzzy_find_token(tokens, alias)
                if idx < 0:
                    continue
                score = 0.95 if tokens[idx] == alias else 0.85
            if score > best_score:
                best, best_score = canonical, score
    return best, best_score


def _extract_subject_count(text: str) -> tuple[int | None, float]:
    m = re.search(
        r"(?:\b(?:in|have|got|back|on|for|of|a|an|one|akta|ek)\b\s*)?"
        r"(\d+|one|two|three|four|five|ek|akta|duti|tin)\s*"
        r"(?:sub|subject|subjects|paper|sem|semester)\b",
        _normalize(text),
    )
    if not m:
        return None, 0.0
    word = m.group(1)
    count = _SUBJECT_COUNT.get(word.lower())
    if count is None:
        return None, 0.0
    return count, 0.92


def _detect_language(text: str) -> str:
    if any("\u0980" <= c <= "\u09ff" for c in text):
        return "bn"
    if any("\u0900" <= c <= "\u097f" for c in text):
        return "hi"
    bn = sum(1 for w in ("amar", "ami", "koto", "ache", "hobe", "keno", "kivabe")
             if re.search(rf"\b{w}\b", text, re.IGNORECASE))
    hi = sum(1 for w in ("hai", "kya", "kaise", "kitna", "kaun", "mera", "kab")
             if re.search(rf"\b{w}\b", text, re.IGNORECASE))
    if bn >= 2 and bn > hi:
        return "bn"
    if hi >= 2 and hi > bn:
        return "hi"
    return "en"


# ── Canonical structured output ─────────────────────────────────────────────

@dataclass
class SemanticUnderstanding:
    intent: str = "unknown"
    subtopic: str = ""
    entities: dict[str, Any] = field(default_factory=dict)
    language: str = "en"
    confidence: float = 0.0
    topic: str = ""
    source: str = "deterministic"      # "deterministic" | "semantic_nlu"
    raw: str = ""
    unknown_override: bool = False     # LLM said unknown/out-of-scope


def _closing_intent(tokens: list[str]) -> tuple[str, float]:
    for phrase in _CLOSING_TRIGGERS:
        if _match_phrase(tokens, tuple(phrase if isinstance(phrase, tuple) else (phrase,))):
            return "general", 0.9
    return "", 0.0


def _subtopic_for(intent: str, text: str, branch: str) -> str:
    tl = _normalize(text)
    if intent == "fee":
        if re.search(r"installment|payment|emi", tl):
            return "installment"
        if re.search(r"waiver|concession|discount", tl):
            return "waiver"
        if re.search(r"hostel", tl):
            return "hostel_fee"
        return "total_cost"
    if intent == "program":
        if branch:
            return "curriculum"
        if re.search(r"syllabus|curriculum|module", tl):
            return "syllabus"
        return "subjects"
    if intent == "hostel":
        if re.search(r"mess|food", tl):
            return "mess"
        if re.search(r"facilit|room|amenity", tl):
            return "facilities"
        if re.search(r"fee|cost", tl):
            return "fee"
        return "facilities"
    if intent == "admission":
        if re.search(r"eligib|qualif|criteria|process", tl):
            return "process"
        return ""
    if intent == "scholarship":
        if re.search(r"eligib|qualif|criteria|get", tl):
            return "criteria"
        return ""
    if intent == "backlog":
        if re.search(r"clear|procedure|how", tl):
            return "clearance"
        return ""
    return ""


def _fast_reading(text: str, topic: str = "") -> SemanticUnderstanding:
    """Deterministic semantic reading. O(triggers × tokens) edit-distance scans."""
    tokens = _normalize(text).split()
    entities: dict[str, Any] = {}

    category, cat_conf = _extract_category(text)
    if category:
        entities["category"] = category
    branch, branch_conf = _extract_branch(text)
    if branch:
        entities["branch"] = branch
    rank, rank_conf = _extract_rank(text)
    if rank:
        entities["rank"] = rank
    percentage, pct_conf = _extract_percentage(text)
    if percentage:
        entities["percentage"] = percentage
    subject_count, subj_conf = _extract_subject_count(text)
    if subject_count is not None:
        entities["subject_count"] = subject_count

    if topic:
        entities["topic"] = topic

    language = _detect_language(text)
    question = bool(_QUESTION_MARKERS.search(text))

    # 1. Standalone conversational glue (only when nothing domain-specific is said).
    candidates: list[tuple[str, float, int]] = []  # (intent, confidence, specificity)
    domain_candidates: list[tuple[str, float, int]] = []

    if tokens:
        if _first_token_is(tokens, _GREETINGS):
            candidates.append(("greeting", 0.97, 1))
        elif any(_match_phrase(tokens, phrase) for phrase in _GREETING_PHRASES):
            candidates.append(("greeting", 0.97, 1))
    for intent, phrases in _INTENT_TRIGGERS.items():
        if intent == "greeting":
            continue
        for phrase in phrases:
            if _match_phrase(tokens, phrase):
                specificity = len(phrase)
                conf = 0.90 + 0.05 * min(specificity, 2)
                entry = (intent, conf, specificity)
                if intent in _CONVERSATIONAL_LABELS:
                    candidates.append(entry)
                else:
                    domain_candidates.append(entry)

    closing_intent, closing_conf = _closing_intent(tokens)
    if closing_intent:
        candidates.append(("closing", closing_conf, 1))

    # Category/profile facts are genuine semantic readings on their own.
    profile_fact: tuple[str, float] | None = None
    if category:
        profile_fact = ("category", cat_conf)
    elif rank and rank_conf >= 0.8:
        profile_fact = ("admission", rank_conf)
    elif percentage and pct_conf >= 0.8:
        profile_fact = ("admission", pct_conf)

    # 2. Pick the winner.
    if domain_candidates:
        domain_candidates.sort(key=lambda x: (-x[1], -x[2], x[0]))
        top = domain_candidates[0]
        runner = domain_candidates[1] if len(domain_candidates) > 1 else None
        # A backlog statement with a subject count ("ek sub me back hai")
        # whose words only surface via the count/back combination.
        if (
            top[0] not in ("backlog",)
            and "back" in _normalize(text).split()
            and subject_count is not None
        ):
            top = ("backlog", max(top[1], 0.9), top[2])
        # Two distinct strong domain readings with no context → ambiguous.
        if runner is not None and runner[0] != top[0] and abs(top[1] - runner[1]) < 0.05:
            return SemanticUnderstanding(
                intent="unknown", subtopic="", entities=entities,
                language=language, confidence=0.35, topic=topic,
                source="deterministic", raw=text,
            )
        intent, conf, _ = top
        # A domain keyword beats a category/profile-fact-only reading
        # ("what is the fee for gen category" → fee + category entity).
        return SemanticUnderstanding(
            intent=intent,
            subtopic=_subtopic_for(intent, text, branch),
            entities=entities, language=language, confidence=conf,
            topic=topic, source="deterministic", raw=text,
        )

    if profile_fact:
        intent, conf = profile_fact
        if intent == "category":
            # Category statement is a continuation fact: carry the topic so the
            # engine can route it, and say so in the structured object.
            return SemanticUnderstanding(
                intent="category", subtopic="", entities=entities,
                language=language, confidence=max(conf, 0.9), topic=topic,
                source="deterministic", raw=text,
            )
        return SemanticUnderstanding(
            intent=intent, subtopic="", entities=entities,
            language=language, confidence=conf, topic=topic,
            source="deterministic", raw=text,
        )

    if candidates:
        candidates.sort(key=lambda x: (-x[1], -x[2], x[0]))
        intent, conf, _ = candidates[0]
        return SemanticUnderstanding(
            intent=intent, subtopic="", entities=entities,
            language=language, confidence=conf, topic=topic,
            source="deterministic", raw=text,
        )

    # 3. Follow-up inside a committed topic with no new subject.
    if topic and topic not in _CONVERSATIONAL_LABELS:
        if question or not tokens:
            return SemanticUnderstanding(
                intent=topic, subtopic="", entities=entities,
                language=language, confidence=0.55, topic=topic,
                source="deterministic", raw=text,
            )
        if len(tokens) <= 4:
            return SemanticUnderstanding(
                intent=topic, subtopic="", entities=entities,
                language=language, confidence=0.5, topic=topic,
                source="deterministic", raw=text,
            )

    # 4. Unknown / off-topic.
    if not _DOMAIN_HINT.search(text):
        return SemanticUnderstanding(
            intent="unknown", subtopic="", entities=entities,
            language=language, confidence=0.2, topic=topic,
            source="deterministic", raw=text,
        )
    return SemanticUnderstanding(
        intent="general", subtopic="", entities=entities,
        language=language, confidence=0.3, topic=topic,
        source="deterministic", raw=text,
    )


# ── LLM fallback (strict, swappable via LLMAdapter) ─────────────────────────

_LLM_PROMPT = (
    "You are the understanding layer of a college admission chatbot.\n"
    "Read the CURRENT student message and answer with ONLY one JSON object, no extra text:\n"
    "{{\"intent\": \"unknown\", \"subtopic\": \"\", "
    "\"entities\": {{\"category\": \"\", \"branch\": \"\", \"rank\": 0, "
    "\"percentage\": 0, \"subject_count\": 0, \"topic\": \"\"}}, "
    "\"language\": \"en\", \"confidence\": 0.0}}\n"
    "\n"
    "intent must be exactly one of: {intents}\n"
    "\n"
    "Committed conversation topic (from earlier turns): {topic}\n"
    "Student message: {text}\n"
    "\n"
    "Rules:\n"
    "- A short follow-up that continues the committed topic (e.g. \"general "
    "category\", \"yes\", \"what about hostel\") must keep that topic in "
    "entities.topic and set intent to the topic (\"category\" when the follow-up "
    "is a category/profile fact).\n"
    "- Only report values the student actually stated. Never invent ranks, "
    "percentages or categories.\n"
    "- If the message is unrelated to this college chatbot, set intent "
    "\"unknown\" and keep confidence low.\n"
    "- confidence 0.0-1.0: high (>=0.8) only when the message clearly states a "
    "single intent.\n"
)

_NLU_LLM_LABELS = ", ".join(sorted(_NLU_INTENTS))


def _parse_llm_understanding(raw: str) -> SemanticUnderstanding | None:
    data = parse_llm_json(raw)
    if data is None:
        return None
    intent = data.get("intent")
    if not isinstance(intent, str) or intent not in _NLU_INTENTS:
        return None
    entities = data.get("entities")
    if not isinstance(entities, dict):
        entities = {}
    subtopic = data.get("subtopic")
    language = data.get("language")
    confidence = data.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else 0.0
    except (TypeError, ValueError):
        confidence = 0.0
    if not (0.0 <= confidence <= 1.0):
        confidence = 0.0
    return SemanticUnderstanding(
        intent=intent,
        subtopic=str(subtopic or ""),
        entities=dict(entities),
        language=str(language or "en")[:2],
        confidence=confidence,
        source="semantic_nlu",
        raw=raw,
    )


class SemanticNLU:
    """Hybrid NLU: deterministic fast path, LLM fallback, safe degradation.

    When the fast reading is confident (>= ``confidence_threshold``) the LLM is
    never called. Otherwise a strict-JSON LLM reading is attempted through the
    ``LLMAdapter`` interface (Groq in the live demo, MockLLM in tests). Any
    failure, timeout, or unparseable output falls back to the deterministic
    reading so the engine never crashes.
    """

    def __init__(
        self,
        llm: LLMAdapter | None = None,
        confidence_threshold: float = 0.55,
    ) -> None:
        self._llm = llm
        self.confidence_threshold = confidence_threshold
        self.llm_calls = 0
        self.llm_failures = 0
        self.deterministic_calls = 0
        self.fast_path_hits = 0

    def interpret(self, text: str, topic: str = "") -> SemanticUnderstanding:
        fast = _fast_reading(text, topic=topic)
        self.deterministic_calls += 1
        if fast.confidence >= self.confidence_threshold:
            self.fast_path_hits += 1
            return fast
        if self._llm is None:
            return fast
        self.llm_calls += 1
        nlu = self._llm_call(text, topic=topic)
        if nlu is None or nlu.intent in ("unknown", "general", "closing"):
            if nlu is not None:
                fast.unknown_override = True
            return fast
        return nlu

    def _llm_call(self, text: str, topic: str = "") -> SemanticUnderstanding | None:
        prompt = _LLM_PROMPT.format(
            intents=_NLU_LLM_LABELS,
            topic=topic or "none",
            text=text,
        )
        try:
            response = self._llm.generate(prompt, temperature=0.0, max_tokens=256)
        except Exception:
            self.llm_failures += 1
            return None
        return _parse_llm_understanding(response.text)

    # ── Deterministic reading (exposed for tests / instrumentation) ────────

    @staticmethod
    def fast_reading(text: str, topic: str = "") -> SemanticUnderstanding:
        return _fast_reading(text, topic=topic)

    @staticmethod
    def parse_llm(raw: str) -> SemanticUnderstanding | None:
        return _parse_llm_understanding(raw)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "deterministic_calls": self.deterministic_calls,
            "fast_path_hits": self.fast_path_hits,
            "llm_calls": self.llm_calls,
            "llm_failures": self.llm_failures,
        }
