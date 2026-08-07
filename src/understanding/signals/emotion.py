"""Emotion detector — identifies explicit emotional signals in user text.

This detector runs in the understanding stage and produces a Signal.
The reasoning engine consumes the signal but does not perform detection.

Emotion subtypes:
    frustration  -- annoyed, fed up, angry at system/process
    anxiety      -- worried, nervous, tense about outcomes
    confusion    -- unsure, lost, doesn't understand
    urgency      -- time pressure, needs immediate response

This detector is intentionally conservative. It avoids false positives for:
- Factual admission questions (cutoff, eligibility, "can I get")
- Fee / hostel / placement information requests
- Syllabus / availability queries
- Profile data statements
"""
from __future__ import annotations

import re
from typing import Optional

from src.understanding.signals.base import Signal

_SOURCE = "understanding.emotion_detector"

# ── Frustration patterns ────────────────────────────────────────────

_FRUSTRATION_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\bfrustrated\b", re.I), 0.85),
    (re.compile(r"\bfed\s+up\b", re.I), 0.85),
    (re.compile(r"\bsick\s+of\b", re.I), 0.85),
    (re.compile(r"\bannoyed\b", re.I), 0.8),
    (re.compile(r"\bthis\s+is\s+useless\b", re.I), 0.85),
    (re.compile(r"\buseless\b", re.I), 0.75),
    (re.compile(r"\bterrible\b", re.I), 0.8),
    (re.compile(r"\bhorrible\b", re.I), 0.8),
    (re.compile(r"\bawful\b", re.I), 0.8),
    (re.compile(r"\bpathetic\b", re.I), 0.85),
    (re.compile(r"\bunacceptable\b", re.I), 0.85),
    (re.compile(r"\bcompletely\s+(?:useless|stupid|broken|terrible)\b", re.I), 0.9),
    (re.compile(r"\bwaste\s+(?:of|of\s+time)\b", re.I), 0.8),
    (re.compile(r"\btoo\s+complicated\b", re.I), 0.75),
    (re.compile(r"\bwhy\s+is\s+it\s+so\s+(?:hard|difficult)\b", re.I), 0.8),
]

# ── Anxiety patterns ────────────────────────────────────────────────

_ANXIETY_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\bvery\s+worried\b", re.I), 0.8),
    (re.compile(r"\breally\s+worried\b", re.I), 0.8),
    (re.compile(r"\bi'?m\s+worried\b", re.I), 0.75),
    (re.compile(r"\bworried\s+(?:about|that)\b", re.I), 0.7),
    (re.compile(r"\bnervous\b", re.I), 0.7),
    (re.compile(r"\bscared\b", re.I), 0.75),
    (re.compile(r"\btense\b", re.I), 0.65),
    (re.compile(r"\banxious\b", re.I), 0.75),
    (re.compile(r"\bafraid\b", re.I), 0.7),
    (re.compile(r"\bstress(?:ed|ful)\b", re.I), 0.65),
    (re.compile(r"\bpanicking\b", re.I), 0.85),
    (re.compile(r"\bpanic(?:king|s|ked|ed)?\b", re.I), 0.8),
    (re.compile(r"\bfreaking\s+out\b", re.I), 0.85),
    (re.compile(r"\bstressed?\s+out\b", re.I), 0.75),
    (re.compile(r"\buneasy\b", re.I), 0.65),
    (re.compile(r"\bconcerned\b", re.I), 0.7),
]

# ── Confusion patterns ──────────────────────────────────────────────
# NOTE: These express emotional confusion, not factual comparison.
# "confused between X and Y" is emotional; "what is the difference"
# is factual and handled by exclusion patterns below.

_CONFUSION_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\bconfused\s+(?:between|about|with|regarding)\b", re.I), 0.85),
    (re.compile(r"\bconfused\b", re.I), 0.7),
    (re.compile(r"\bdon'?t\s+understand\b", re.I), 0.7),
    (re.compile(r"\bnot\s+sure\s+(?:what|which|how|about)\b", re.I), 0.7),
    (re.compile(r"\bwhat\s+should\s+i\s+(?:do|choose|pick|take)\b", re.I), 0.75),
    (re.compile(r"\bhow\s+to\s+(?:decide|choose)\b", re.I), 0.75),
    (re.compile(r"\bcan'?t\s+decide\b", re.I), 0.8),
    (re.compile(r"\bcan'?t\s+understand\b", re.I), 0.7),
    (re.compile(r"\bno\s+idea\b", re.I), 0.65),
    (re.compile(r"\bdon'?t\s+know\s+what\s+to\s+do\b", re.I), 0.8),
    (re.compile(r"\bunclear\b", re.I), 0.65),
    (re.compile(r"\bnot\s+clear\b", re.I), 0.65),
    (re.compile(r"\bunsure\b", re.I), 0.65),
    (re.compile(r"\bdilemma\b", re.I), 0.75),
    # Hindi: confusion / pareshan
    (re.compile(r"\bconfusion\s+(?:mein|hai|ho|h?\b)", re.I), 0.8),
    (re.compile(r"\bpareshan\b", re.I), 0.75),
]

# ── Urgency patterns ────────────────────────────────────────────────

_URGENCY_PATTERNS: list[tuple[re.Pattern, float]] = [
    (re.compile(r"\burgent\b", re.I), 0.8),
    (re.compile(r"\bimmediately\b", re.I), 0.8),
    (re.compile(r"\basap\b", re.I), 0.85),
    (re.compile(r"\bhurry\s+up\b", re.I), 0.85),
    (re.compile(r"\btime\s+is\s+running\b", re.I), 0.85),
    (re.compile(r"\brunning\s+out\s+of\s+time\b", re.I), 0.85),
    (re.compile(r"\blast\s+date\b", re.I), 0.8),
    (re.compile(r"\b(?:deadline\s+(?:is\s+)?(?:approaching|near|tomorrow|today|closing|expiring|fast)|miss\s+(?:the\s+)?deadline|deadline\s+to\s+submit|urgent\s+deadline)\b", re.I), 0.8),
    (re.compile(r"\blast\s+day\b", re.I), 0.75),
    (re.compile(r"\bcutoff\s*date\b", re.I), 0.75),
    (re.compile(r"\bhurry\b", re.I), 0.7),
    (re.compile(r"\bquick\b", re.I), 0.6),
    (re.compile(r"\bsoon\b", re.I), 0.55),
    (re.compile(r"\btime\s+limit\b", re.I), 0.7),
    (re.compile(r"\bexpire\b", re.I), 0.7),
]

# ── Exclusion patterns ──────────────────────────────────────────────
# Factual questions that should NOT trigger emotion signals,
# even if weak emotional words are present nearby.

_EXCLUSION_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bcan\s+i\s+get\b", re.I),
    re.compile(r"\bwill\s+i\s+get\b", re.I),
    re.compile(r"\bam\s+i\s+eligible\b", re.I),
    re.compile(r"\bcutoff\s+(?:for|of|marks|rank|score)\b", re.I),
    re.compile(r"\bclosing\s+rank\b", re.I),
    re.compile(r"\bfees?\b", re.I),
    re.compile(r"\bfee\s+structure\b", re.I),
    re.compile(r"\bhow\s+much\b", re.I),
    re.compile(r"\bhostel\b", re.I),
    re.compile(r"\baccommodation\b", re.I),
    re.compile(r"\bplacement\s+(?:record|percentage|stat|data|detail|info)\b", re.I),
    re.compile(r"\bhighest\s+package\b", re.I),
    re.compile(r"\bis\s+.{1,20}?\s+available\b", re.I),
    re.compile(r"\bdo\s+you\s+(?:have|offer)\b", re.I),
    re.compile(r"\bsyllabus\b", re.I),
    re.compile(r"\bcurriculum\b", re.I),
]

# ── Negation handling ──────────────────────────────────────────────

_NEGATION_RE = re.compile(
    r"(?:\bnot\b|\bno\b|\bdon'?t\b|\bdoesn'?t\b|\bdidn'?t\b|"
    r"\bwasn'?t\b|\bweren'?t\b|\bhasn'?t\b|\bhaven'?t\b|"
    r"\bcan'?t\b|\bcouldn'?t\b|\bwon'?t\b|\bwouldn'?t\b|\bnever\b)",
    re.I,
)

# ── Core detector mapping ──────────────────────────────────────────

_SUBTYPE_PATTERNS: dict[str, list[tuple[re.Pattern, float]]] = {
    "frustration": _FRUSTRATION_PATTERNS,
    "anxiety": _ANXIETY_PATTERNS,
    "confusion": _CONFUSION_PATTERNS,
    "urgency": _URGENCY_PATTERNS,
}

# Subtypes where negation before the match should suppress detection.
# Confusion patterns already encode negation naturally ("don't understand",
# "can't decide"), so negation checking is skipped for confusion.
_NEGATION_CHECKED_SUBTYPES = {"frustration", "anxiety", "urgency"}


def _is_negated(text: str, match_start: int, match_end: int) -> bool:
    """Check if the matched span is preceded by a negation within 40 chars."""
    window_start = max(0, match_start - 40)
    window = text[window_start:match_start]
    return bool(_NEGATION_RE.search(window))


def detect_emotion(text: str) -> Optional[Signal]:
    """Detect an emotion signal from user text.

    Returns a Signal with the highest-confidence emotion subtype,
    or None if no genuine emotion is detected.

    This detector distinguishes genuine emotional expressions from
    factual questions, informational queries, and profile statements.
    """
    if not text or not text.strip():
        return None

    tl = text.strip()

    # Exclusion check: factual / informational queries
    has_exclusion = any(p.search(tl) for p in _EXCLUSION_PATTERNS)

    subtype_scores: dict[str, float] = {}

    for subtype, patterns in _SUBTYPE_PATTERNS.items():
        best_for_subtype = 0.0
        check_negation = subtype in _NEGATION_CHECKED_SUBTYPES
        for pat, weight in patterns:
            m = pat.search(tl)
            if m:
                # For frustration/anxiety/urgency, skip negated matches.
                # Confusion patterns encode negation naturally.
                if check_negation and _is_negated(tl, m.start(), m.end()):
                    continue
                # Exclusion patterns discount weak evidence.
                # Strong evidence (>= 0.7) still passes — explicit emotion words
                # (worried, scared, anxious, etc.) should not be suppressed
                # by factual topic keywords (hostel, cutoff, etc.).
                if has_exclusion and weight < 0.7:
                    score = weight * 0.3
                else:
                    score = weight
                if score > best_for_subtype:
                    best_for_subtype = score
        if best_for_subtype > 0:
            subtype_scores[subtype] = best_for_subtype

    if subtype_scores:
        best_subtype = max(subtype_scores, key=subtype_scores.get)
        best_score = subtype_scores[best_subtype]
    else:
        best_subtype = None
        best_score = 0.0

    # Require minimum confidence threshold
    if best_subtype is None or best_score < 0.5:
        return None

    return Signal(
        value=best_subtype,
        confidence=round(best_score, 2),
        source=_SOURCE,
    )
