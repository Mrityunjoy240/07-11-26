"""Grievance detector -- identifies user complaints with structured subtypes.

This detector runs in the understanding stage and produces a Signal.
The reasoning engine consumes the signal but does not perform detection.

Grievance subtypes (from benchmark analysis):
    waiting     -- delayed response, nobody replied, no update
    ignored     -- no response, unanswered, overlooked
    website     -- portal error, system not working, technical issue
    staff       -- administration problem, unhelpful staff, want escalation
    process     -- procedural complaint, messy process, general dissatisfaction
"""
from __future__ import annotations

import re
from typing import Optional

from src.understanding.signals.base import Signal

_SOURCE = "understanding.grievance_detector"

# Subtype patterns: (compiled_re, weight)
# Higher weight = stronger evidence for that subtype.

_WAITING_PATTERNS = [
    (re.compile(r"(?:waiting|waited|waiting\s+for)\s+(?:for\s+)?(?:\d+\s+)?(?:day|week|month|hour|minute)", re.I), 0.9),
    (re.compile(r"(?:no\s+(?:reply|response|update|answer|feedback))\s+(?:for|since|from|yet)", re.I), 0.85),
    (re.compile(r"(?:not\s+(?:yet\s+)?(?:responded|replied|answered|updated))", re.I), 0.8),
    (re.compile(r"(?:still\s+waiting|still\s+no\s+(?:reply|response|update))", re.I), 0.9),
    (re.compile(r"(?:hasn['\u2019]?\s*t?\s*(?:been|got)\s+(?:any\s+)?(?:reply|response|update|answer))", re.I), 0.85),
    (re.compile(r"(?:been\s+(?:waiting|asking)\s+.{0,30}?\d+\s+(?:minute|hour|day|week|month))", re.I), 0.9),
    (re.compile(r"(?:same\s+(?:question|answer|response|reply)\s+(?:for|over|again))", re.I), 0.85),
    (re.compile(r"(?:asked?\s+(?:the\s+same|this|that|it)\s+\d+\s+(?:time|hour|day|minute))", re.I), 0.85),
]

_IGNORED_PATTERNS = [
    (re.compile(r"(?:nobody|no\s+one|no\s+body)\s+(?:has\s+)?(?:responded|replied|answered|got\s+back)", re.I), 0.9),
    (re.compile(r"(?:got\s+no\s+(?:reply|response|answer))", re.I), 0.8),
    (re.compile(r"(?:no\s+(?:one|body)\s+(?:is\s+)?(?:responding|answering|replying))", re.I), 0.85),
    (re.compile(r"(?:been\s+(?:waiting|asking)\s+(?:for\s+)?(?:\d+\s+)?(?:day|week|month|hour|minute))", re.I), 0.75),
    (re.compile(r"(?:ignored|overlooked|neglected)\s+(?:my|the|our)\s+(?:application|request|query|complaint|ticket|email|call)", re.I), 0.9),
]

_WEBSITE_PATTERNS = [
    (re.compile(r"(?:website|portal|site|system|server)\s+(?:is\s+)?(?:not\s+)?(?:working|loading|opening|responding|down|broken|error)", re.I), 0.9),
    (re.compile(r"(?:cannot|can'?t|could\s+n'?t)\s+(?:access|open|load|login|log\s+in|submit|upload)", re.I), 0.8),
    (re.compile(r"(?:error|bug|crash|glitch)\s+(?:on|in|while|during)\s+(?:the\s+)?(?:website|portal|site|system|form|page)", re.I), 0.85),
]

_STAFF_PATTERNS = [
    (re.compile(r"(?:want|need|like)\s+to\s+speak\s+(?:to|with)\s+(?:someone|manager|principal|authority|in\s+charge|admin)", re.I), 0.85),
    (re.compile(r"(?:staff|administration|admin|office|authorities?)\s+(?:are|is|were|have\s+been)?\s*(?:not\s+)?(?:responding|helpful|cooperative|available|replying)", re.I), 0.85),
]

_PROCESS_PATTERNS = [
    (re.compile(r"(?:the\s+)?(?:whole\s+)?process\s+is\s+(?:a\s+)?(?:mess|disaster|nightmare|terrible|awful|horrible|pathetic)", re.I), 0.9),
    (re.compile(r"(?:completely\s+)?(?:unacceptable|ridiculous|absurd)", re.I), 0.8),
    (re.compile(r"(?:want\s+to\s+speak\s+to\s+(?:someone|manager|principal|authority|in\s+charge))", re.I), 0.85),
    (re.compile(r"(?:this\s+)?(?:system|process|service)\s+is\s+(?:useless|stupid|broken|terrible|awful|horrible|pathetic|garbage|trash|crap)", re.I), 0.9),
    (re.compile(r"(?:same\s+(?:stupid|dumb|useless)\s+(?:answer|response|reply|thing))", re.I), 0.9),
]

# Negation handling

_NEGATION_RE = re.compile(
    r"(?:\bnot\b|\bno\b|\bdon'?t\b|\bdoesn'?t\b|\bdidn'?t\b|\bwasn'?t\b|\bweren'?t\b|\bhasn'?t\b|\bhaven'?t\b|"
    r"\bcan'?t\b|\bcouldn'?t\b|\bwon'?t\b|\bwouldn'?t\b|\bnever\b|\bneither\b|\bnor\b|\bwithout\b)",
    re.I,
)

# False-positive exclusion patterns
# Queries that look like grievances but are actually just anxiety,
# confusion, or normal questions.

_EXCLUSION_PATTERNS = [
    re.compile(r"\b(?:worried?|anxious|tense|nervous|panicking|freaking\s+out)\b", re.I),
    re.compile(r"\b(?:confused?|don'?t\s+understand|not\s+sure|dilemma)\b", re.I),
    re.compile(r"\b(?:can\s+i\s+get|will\s+i\s+get|possible|chances|eligible)\b", re.I),
]

# Core detector mapping

_SUBTYPE_PATTERNS = {
    "waiting": _WAITING_PATTERNS,
    "ignored": _IGNORED_PATTERNS,
    "website": _WEBSITE_PATTERNS,
    "staff": _STAFF_PATTERNS,
    "process": _PROCESS_PATTERNS,
}


def _is_negated(text: str, match_start: int, match_end: int) -> bool:
    """Check if the matched span is preceded by a negation within 40 chars."""
    window_start = max(0, match_start - 40)
    window = text[window_start:match_start]
    return bool(_NEGATION_RE.search(window))


def detect_grievance(text: str) -> Optional[Signal]:
    """Detect a grievance signal from user text.

    Returns a Signal with the highest-confidence subtype, or None if
    no genuine grievance is detected.

    This detector distinguishes genuine complaints (which have a target
    and a problem) from anxiety, confusion, or ordinary questions.
    """
    if not text or not text.strip():
        return None

    tl = text.strip()

    # Exclusion check: if text matches anxiety/confusion patterns
    # AND does not have any strong grievance evidence, skip.
    has_exclusion = any(p.search(tl) for p in _EXCLUSION_PATTERNS)

    best_subtype = None
    best_score = 0.0

    for subtype, patterns in _SUBTYPE_PATTERNS.items():
        for pat, weight in patterns:
            m = pat.search(tl)
            if m and not _is_negated(tl, m.start(), m.end()):
                # Strong evidence (>= 0.85) overrides exclusion discount.
                # Weak evidence is discounted when exclusion patterns match.
                if has_exclusion and weight < 0.85:
                    score = weight * 0.4
                else:
                    score = weight
                if score > best_score:
                    best_score = score
                    best_subtype = subtype

    # Require minimum confidence threshold
    if best_subtype is None or best_score < 0.5:
        return None

    return Signal(
        value=best_subtype,
        confidence=round(best_score, 2),
        source=_SOURCE,
    )
