"""Decision-intent detector — identifies explicit decision-making signals.

This detector runs in the understanding stage and produces a Signal.
The reasoning engine consumes the signal but does not perform detection.

Decision-intent subtypes:
    compare       -- explicit comparison between options (X or Y, X vs Y)
    recommend     -- asking for recommendation (which should I, suggest)
    choose        -- asking for help choosing (help me decide, go for)
    alternative   -- looking for alternatives (what else, backup, other options)
    tradeoff      -- evaluating tradeoffs (pros and cons, worth it, gain/lose)

This detector is intentionally conservative. It avoids false positives for:
- Factual admission questions (cutoff, eligibility, "can I get")
- Fee / hostel / placement information requests
- Preference statements ("I want CSE", "I prefer IT")
"""
from __future__ import annotations

import re
from typing import Optional

from src.understanding.signals.base import Signal

_SOURCE = "understanding.decision_detector"

# ── Branch / option names (for target extraction) ──────────────────────

_BRANCH_NAMES = (
    "cse|ece|ee|me|ce|it|ai|aiml|biotechnology|biotech|"
    "data science|cyber security|cybersecurity|iot|robotics|"
    "mechanical|electrical|civil|electronics|computer science|"
    "information technology|chemical|production|instrumentation|"
    "metallurgy|mining|textile|automobile|aerospace"
)

_OPTION_PATTERN = re.compile(
    rf"\b({_BRANCH_NAMES})\b", re.IGNORECASE
)


def _extract_options(text: str) -> list[str]:
    """Extract branch/option names mentioned in text."""
    matches = _OPTION_PATTERN.findall(text)
    seen: set[str] = set()
    result: list[str] = []
    for m in matches:
        canonical = m.strip().upper()
        # Normalize common abbreviations
        norm_map = {
            "COMPUTER SCIENCE": "CSE",
            "INFORMATION TECHNOLOGY": "IT",
            "ELECTRONICS AND COMMUNICATION": "ECE",
            "ELECTRONICS": "ECE",
            "ELECTRICAL": "EE",
            "MECHANICAL": "ME",
            "CIVIL": "CE",
            "CYBERSECURITY": "CYBER SECURITY",
            "BIOTECHNOLOGY": "BIOTECH",
        }
        canonical = norm_map.get(canonical, canonical)
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


# ── Compare patterns ───────────────────────────────────────────────────

_COMPARE_PATTERNS: list[tuple[re.Pattern, float]] = [
    # "X or Y" with branch names on both sides
    (re.compile(
        rf"\b({_BRANCH_NAMES})\s+or\s+({_BRANCH_NAMES})\b",
        re.IGNORECASE,
    ), 0.9),
    # "X vs Y" / "X versus Y"
    (re.compile(
        rf"\b({_BRANCH_NAMES})\s+(?:vs\.?|versus)\s+({_BRANCH_NAMES})\b",
        re.IGNORECASE,
    ), 0.95),
    # "compare X and Y" / "compare X with Y"
    (re.compile(
        r"\bcompare\s+.{0,40}?\b(?:and|with|to)\s+",
        re.IGNORECASE,
    ), 0.85),
    # "difference between X and Y"
    (re.compile(
        r"\bdifference\s+between\s+.{0,40}?\band\b",
        re.IGNORECASE,
    ), 0.85),
    # "how does X compare with/to Y"
    (re.compile(
        r"\bhow\s+(?:does|is)\s+\w+\s+compare\s+(?:with|to)\b",
        re.IGNORECASE,
    ), 0.85),
    # "which is better, X or Y"
    (re.compile(
        r"\bwhich\s+is\s+better\s*,?\s*.{0,30}?\bor\b",
        re.IGNORECASE,
    ), 0.85),
    # "X or Y better"
    (re.compile(
        rf"\b({_BRANCH_NAMES})\s+or\s+({_BRANCH_NAMES})\s+better\b",
        re.IGNORECASE,
    ), 0.9),
    # "X or Y which is better"
    (re.compile(
        rf"\b({_BRANCH_NAMES})\s+or\s+({_BRANCH_NAMES})\s+.{0,10}?\bbetter\b",
        re.IGNORECASE,
    ), 0.9),
    # "which one is better for" (without specific options)
    (re.compile(
        r"\bwhich\s+(?:one|branch|stream)\s+is\s+better\s+for\b",
        re.IGNORECASE,
    ), 0.8),
    # "how is X compared to Y"
    (re.compile(
        r"\bhow\s+is\s+\w+\s+compared\s+to\b",
        re.IGNORECASE,
    ), 0.85),
]

# ── Recommend patterns ────────────────────────────────────────────────

_RECOMMEND_PATTERNS: list[tuple[re.Pattern, float]] = [
    # "which one should I choose"
    (re.compile(r"\bwhich\s+(?:one|branch|stream)?\s*should\s+i\s+choose\b", re.I), 0.9),
    # "what would you recommend"
    (re.compile(r"\bwhat\s+would\s+you\s+recommend\b", re.I), 0.9),
    # "can you suggest"
    (re.compile(r"\bcan\s+you\s+suggest\b", re.I), 0.85),
    # "what do you suggest"
    (re.compile(r"\bwhat\s+do\s+you\s+suggest\b", re.I), 0.85),
    # "which branch is better for me"
    (re.compile(r"\bwhich\s+branch\s+is\s+better\s+for\s+me\b", re.I), 0.9),
    # "best option for me"
    (re.compile(r"\bbest\s+option\s+for\s+me\b", re.I), 0.85),
    # "best branch for me"
    (re.compile(r"\bbest\s+branch\s+for\s+me\b", re.I), 0.85),
    # "what should I pick"
    (re.compile(r"\bwhat\s+should\s+i\s+pick\b", re.I), 0.85),
    # "you recommend"
    (re.compile(r"\byou\s+recommend\b", re.I), 0.8),
    # "please suggest"
    (re.compile(r"\bplease\s+suggest\b", re.I), 0.8),
    # Hindi: "kya suggest karein" / "kaun sa lena chahiye"
    (re.compile(r"\b(?:kya|kaun\s+sa)\s+suggest\b", re.I), 0.8),
    (re.compile(r"\bkaun\s+sa\s+(?:branch|stream|college)\s+(?:lein|lun|chahiye|choose)\b", re.I), 0.85),
    # "which one do you think"
    (re.compile(r"\bwhich\s+one\s+do\s+you\s+think\b", re.I), 0.8),
]

# ── Choose patterns ───────────────────────────────────────────────────

_CHOOSE_PATTERNS: list[tuple[re.Pattern, float]] = [
    # "which should I take"
    (re.compile(r"\bwhich\s+should\s+i\s+take\b", re.I), 0.9),
    # "should I choose X or Y"
    (re.compile(r"\bshould\s+i\s+choose\b", re.I), 0.85),
    # "what should I go for"
    (re.compile(r"\bwhat\s+should\s+i\s+go\s+for\b", re.I), 0.9),
    # "help me decide"
    (re.compile(r"\bhelp\s+me\s+decide\b", re.I), 0.9),
    # "help me choose"
    (re.compile(r"\bhelp\s+me\s+choose\b", re.I), 0.9),
    # "I can't decide"
    (re.compile(r"\bi\s+(?:can'?t|cannot)\s+decide\b", re.I), 0.8),
    # "confused between X and Y"
    (re.compile(r"\bconfused\s+between\b", re.I), 0.85),
    # "torn between X and Y"
    (re.compile(r"\btorn\s+between\b", re.I), 0.85),
    # "stuck between X and Y"
    (re.compile(r"\bstuck\s+between\b", re.I), 0.85),
    # "which one to go with"
    (re.compile(r"\bwhich\s+one\s+to\s+go\s+with\b", re.I), 0.85),
    # "which ... should I pick"
    (re.compile(r"\bwhich\s+(?:one|branch|stream|college|subject)?\s*should\s+i\s+pick\b", re.I), 0.85),
    # "what to choose"
    (re.compile(r"\bwhat\s+to\s+choose\b", re.I), 0.8),
    # Hindi: "X kare ya Y" — choice between options
    (re.compile(r"\b\w+\s+kare\s+ya\s+\w+", re.I), 0.85),
    # Hindi: "kaun sa branch choose kare" / "kaunsa choose kare"
    (re.compile(r"\bkaun\s*a?\s*sa\b.*?\bchoose\s*kare?\b", re.I), 0.85),
    # Hindi: "decide nahi kar pa rahi" / "decide nahi kar pa rahe"
    (re.compile(r"\bdecide\s+nahi\s+kar\s+pa\b", re.I), 0.85),
    # Hindi: "samajh nahi aa raha" in decision context
    (re.compile(r"\bsamajh\s+nahi\s+aa\s+raha\b", re.I), 0.7),
]

# ── Alternative patterns ──────────────────────────────────────────────

_ALTERNATIVE_PATTERNS: list[tuple[re.Pattern, float]] = [
    # "what other branches"
    (re.compile(r"\bwhat\s+other\s+(?:branches?|options?|choices?)\b", re.I), 0.9),
    # "if I can't get X"
    (re.compile(r"\bif\s+i\s+can'?t\s+get\b", re.I), 0.85),
    # "what else can I choose"
    (re.compile(r"\bwhat\s+else\s+can\s+i\s+(?:choose|pick|take|opt)\b", re.I), 0.9),
    # "what else should I"
    (re.compile(r"\bwhat\s+else\s+should\s+i\b", re.I), 0.85),
    # "any other options"
    (re.compile(r"\bany\s+other\s+(?:options?|choices?|alternatives?)\b", re.I), 0.85),
    # "backup option"
    (re.compile(r"\bbackup\s+(?:option|choice|branch)\b", re.I), 0.85),
    # "backup branch"
    (re.compile(r"\bbackup\s+branch\b", re.I), 0.85),
    # "alternative to X"
    (re.compile(r"\balternative\s+to\b", re.I), 0.85),
    # "similar to X"
    (re.compile(r"\bsimilar\s+to\s+.{0,20}?\b(?:branch|option|choice)\b", re.I), 0.8),
    # "fallback"
    (re.compile(r"\bfallback\b", re.I), 0.8),
    # "plan B"
    (re.compile(r"\bplan\s*[bB]\b", re.I), 0.8),
    # "if not X, then"
    (re.compile(r"\bif\s+not\s+\w+.{0,10}?\bthen\b", re.I), 0.75),
    # "what are my options"
    (re.compile(r"\bwhat\s+are\s+my\s+options\b", re.I), 0.8),
]

# ── Tradeoff patterns ─────────────────────────────────────────────────

_TRADEOFF_PATTERNS: list[tuple[re.Pattern, float]] = [
    # "pros and cons"
    (re.compile(r"\bpros?\s+(?:and|&|\/)\s+cons?\b", re.I), 0.95),
    # "is X worth it"
    (re.compile(r"\bis\s+.{1,30}?\sworth\s+it\b", re.I), 0.85),
    # "worth it compared to"
    (re.compile(r"\bworth\s+it\s+compared\s+to\b", re.I), 0.9),
    # "what do I gain or lose"
    (re.compile(r"\bwhat\s+do\s+i\s+(?:gain|lose|miss)\b", re.I), 0.85),
    # "gain or lose by choosing"
    (re.compile(r"\b(?:gain|lose)\s+by\s+(?:choosing|taking|picking)\b", re.I), 0.9),
    # "tradeoff"
    (re.compile(r"\btrade\s*off\b", re.I), 0.9),
    # "trade-offs"
    (re.compile(r"\btrade[\s-]offs?\b", re.I), 0.9),
    # "which has better X but"
    (re.compile(r"\bwhich\s+has\s+better\b.{0,20}?\bbut\b", re.I), 0.85),
    # "advantages and disadvantages"
    (re.compile(r"\badvantages?\s+(?:and|&|\/)\s+disadvantages?\b", re.I), 0.9),
    # "drawback"
    (re.compile(r"\bdrawbacks?\b", re.I), 0.75),
    # "downside"
    (re.compile(r"\bdownside\b", re.I), 0.75),
    # "benefits? of X over Y"
    (re.compile(r"\bbenefits?\s+of\s+.{1,30}?\bover\b", re.I), 0.85),
]

# ── Exclusion patterns (should NOT trigger decision intent) ───────────

_EXCLUSION_PATTERNS: list[re.Pattern] = [
    # Eligibility / "can I get" questions
    re.compile(r"\bcan\s+i\s+get\b", re.I),
    re.compile(r"\bwill\s+i\s+get\b", re.I),
    re.compile(r"\bam\s+i\s+eligible\b", re.I),
    # Cutoff questions (standalone — not in tradeoff context)
    re.compile(r"\bcutoff\s+(?:for|of|marks|rank|score)\b", re.I),
    re.compile(r"\bclosing\s+rank\b", re.I),
    # Fee questions
    re.compile(r"\bfees?\b", re.I),
    re.compile(r"\bfee\s+structure\b", re.I),
    re.compile(r"\bhow\s+much\b", re.I),
    re.compile(r"\bkitna\s+fee\b", re.I),
    # Hostel questions
    re.compile(r"\bhostel\b", re.I),
    re.compile(r"\baccommodation\b", re.I),
    # Placement information (not tradeoff context)
    re.compile(r"\bplacement\s+(?:record|percentage|stat|data|detail|info)\b", re.I),
    re.compile(r"\bhighest\s+package\b", re.I),
    # Preference statements (not decisions)
    re.compile(r"\bi\s+want\s+\w+$", re.I),
    re.compile(r"\bi\s+prefer\s+\w+$", re.I),
    re.compile(r"\bi\s+like\s+\w+$", re.I),
    # Availability questions
    re.compile(r"\bis\s+.{1,20}?\s+available\b", re.I),
    re.compile(r"\bdo\s+you\s+(?:have|offer)\b", re.I),
    # Syllabus / curriculum questions
    re.compile(r"\bsyllabus\b", re.I),
    re.compile(r"\bcurriculum\b", re.I),
]

# ── Negation handling ──────────────────────────────────────────────────

_NEGATION_RE = re.compile(
    r"(?:\bnot\b|\bno\b|\bdon'?t\b|\bdoesn'?t\b|\bdidn'?t\b|"
    r"\bwasn'?t\b|\bweren'?t\b|\bhasn'?t\b|\bhaven'?t\b|"
    r"\bcan'?t\b|\bcouldn'?t\b|\bwon'?t\b|\bwouldn'?t\b|\bnever\b)",
    re.I,
)


def _is_negated(text: str, match_start: int, match_end: int) -> bool:
    """Check if the matched span is preceded by a negation within 40 chars."""
    window_start = max(0, match_start - 40)
    window = text[window_start:match_start]
    return bool(_NEGATION_RE.search(window))


# ── Core detector mapping ──────────────────────────────────────────────

_SUBTYPE_PATTERNS: dict[str, list[tuple[re.Pattern, float]]] = {
    "compare": _COMPARE_PATTERNS,
    "recommend": _RECOMMEND_PATTERNS,
    "choose": _CHOOSE_PATTERNS,
    "alternative": _ALTERNATIVE_PATTERNS,
    "tradeoff": _TRADEOFF_PATTERNS,
}

# When both compare and tradeoff patterns match, tradeoff is more specific.
_TRADEOFF_PRIORITY_BONUS = 0.05


def detect_decision_intent(text: str) -> Optional[Signal]:
    """Detect a decision-intent signal from user text.

    Returns a Signal with the highest-confidence subtype and optional
    target (extracted branch/option name), or None if no genuine
    decision intent is detected.

    This detector is intentionally conservative — it prioritizes
    precision over recall to avoid false positives on factual questions,
    preference statements, and informational queries.
    """
    if not text or not text.strip():
        return None

    tl = text.strip()

    # Exclusion check: factual / informational / preference queries
    has_exclusion = any(p.search(tl) for p in _EXCLUSION_PATTERNS)

    subtype_scores: dict[str, float] = {}
    subtype_matched: dict[str, bool] = {}

    for subtype, patterns in _SUBTYPE_PATTERNS.items():
        best_for_subtype = 0.0
        for pat, weight in patterns:
            m = pat.search(tl)
            if m and not _is_negated(tl, m.start(), m.end()):
                # Exclusion patterns discount weak evidence.
                # Strong evidence (>= 0.7) still passes — decision verb/question
                # patterns (choose, pick, recommend, which should I) should not
                # be suppressed by factual topic keywords (placement, fees, hostel).
                if has_exclusion and weight < 0.7:
                    score = weight * 0.3
                else:
                    score = weight
                if score > best_for_subtype:
                    best_for_subtype = score
        if best_for_subtype > 0:
            subtype_scores[subtype] = best_for_subtype
            subtype_matched[subtype] = True

    # Tradeoff gets a priority bonus over compare when both match.
    if subtype_matched.get("tradeoff") and subtype_matched.get("compare"):
        subtype_scores["tradeoff"] += _TRADEOFF_PRIORITY_BONUS

    if subtype_scores:
        best_subtype = max(subtype_scores, key=subtype_scores.get)
        best_score = subtype_scores[best_subtype]
    else:
        best_subtype = None
        best_score = 0.0

    # Require minimum confidence threshold
    if best_subtype is None or best_score < 0.5:
        return None

    # Extract target (branch/option names) for compare and choose subtypes
    target = None
    if best_subtype in ("compare", "choose", "alternative"):
        options = _extract_options(tl)
        if len(options) >= 2:
            target = " vs ".join(options[:2])
        elif len(options) == 1:
            target = options[0]

    return Signal(
        value=best_subtype,
        confidence=round(best_score, 2),
        source=_SOURCE,
        target=target,
    )
