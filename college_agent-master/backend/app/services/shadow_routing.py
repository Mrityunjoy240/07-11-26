"""Shadow routing — silent signal detection for production traffic.

Runs emotion + grievance detectors at configurable threshold (default 0.8)
and logs would-route decisions to JSONL. Zero behavioral impact — pure
observation. No dependency on src.* modules — self-contained for Docker.

Usage:
    from app.services.shadow_routing import record_shadow

    # After query normalization, before LLM call:
    record_shadow(query_text, session_id="abc", turn_number=5)

Environment variables:
    SHADOW_ROUTING_PATH     — telemetry JSONL path (default: data/telemetry/shadow_routing.jsonl)
    SHADOW_ROUTING_THRESHOLD — confidence threshold (default: 0.8)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_TELEMETRY_PATH = Path(os.getenv("SHADOW_ROUTING_PATH", "data/telemetry/shadow_routing.jsonl"))
_THRESHOLD = float(os.getenv("SHADOW_ROUTING_THRESHOLD", "0.8"))

# ──────────────────────────────────────────────────────────────────────
#  Emotion detection patterns
# ──────────────────────────────────────────────────────────────────────

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
    (re.compile(r"\bconfusion\s+(?:mein|hai|ho|h?\b)", re.I), 0.8),
    (re.compile(r"\bpareshan\b", re.I), 0.75),
]

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

_EMOTION_EXCLUSION_PATTERNS: list[re.Pattern] = [
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

_EMOTION_NEGATION_RE = re.compile(
    r"(?:\bnot\b|\bno\b|\bdon'?t\b|\bdoesn'?t\b|\bdidn'?t\b|"
    r"\bwasn'?t\b|\bweren'?t\b|\bhasn'?t\b|\bhaven'?t\b|"
    r"\bcan'?t\b|\bcouldn'?t\b|\bwon'?t\b|\bwouldn'?t\b|\bnever\b)",
    re.I,
)

_EMOTION_SUBTYPE_PATTERNS: dict[str, list[tuple[re.Pattern, float]]] = {
    "frustration": _FRUSTRATION_PATTERNS,
    "anxiety": _ANXIETY_PATTERNS,
    "confusion": _CONFUSION_PATTERNS,
    "urgency": _URGENCY_PATTERNS,
}

_NEGATION_CHECKED_SUBTYPES = {"frustration", "anxiety", "urgency"}

def _is_negated_emotion(text: str, match_start: int, match_end: int) -> bool:
    window_start = max(0, match_start - 40)
    window = text[window_start:match_start]
    return bool(_EMOTION_NEGATION_RE.search(window))

def detect_emotion(text: str) -> Optional[dict]:
    if not text or not text.strip():
        return None
    tl = text.strip()
    has_exclusion = any(p.search(tl) for p in _EMOTION_EXCLUSION_PATTERNS)
    subtype_scores: dict[str, float] = {}
    for subtype, patterns in _EMOTION_SUBTYPE_PATTERNS.items():
        best_for_subtype = 0.0
        check_negation = subtype in _NEGATION_CHECKED_SUBTYPES
        for pat, weight in patterns:
            m = pat.search(tl)
            if m:
                if check_negation and _is_negated_emotion(tl, m.start(), m.end()):
                    continue
                if has_exclusion and weight < 0.7:
                    score = weight * 0.3
                else:
                    score = weight
                if score > best_for_subtype:
                    best_for_subtype = score
        if best_for_subtype > 0:
            subtype_scores[subtype] = best_for_subtype
    if not subtype_scores:
        return None
    best_subtype = max(subtype_scores, key=subtype_scores.get)
    best_score = subtype_scores[best_subtype]
    if best_score < 0.5:
        return None
    return {"value": best_subtype, "confidence": round(best_score, 2), "source": "emotion"}

# ──────────────────────────────────────────────────────────────────────
#  Grievance detection patterns
# ──────────────────────────────────────────────────────────────────────

_GRIEVANCE_NEGATION_RE = re.compile(
    r"(?:\bnot\b|\bno\b|\bdon'?t\b|\bdoesn'?t\b|\bdidn'?t\b|\bwasn'?t\b|\bweren'?t\b|\bhasn'?t\b|\bhaven'?t\b|"
    r"\bcan'?t\b|\bcouldn'?t\b|\bwon'?t\b|\bwouldn'?t\b|\bnever\b|\bneither\b|\bnor\b|\bwithout\b)",
    re.I,
)

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

_GRIEVANCE_EXCLUSION_PATTERNS = [
    re.compile(r"\b(?:worried?|anxious|tense|nervous|panicking|freaking\s+out)\b", re.I),
    re.compile(r"\b(?:confused?|don'?t\s+understand|not\s+sure|dilemma)\b", re.I),
    re.compile(r"\b(?:can\s+i\s+get|will\s+i\s+get|possible|chances|eligible)\b", re.I),
]

_GRIEVANCE_SUBTYPE_PATTERNS = {
    "waiting": _WAITING_PATTERNS,
    "ignored": _IGNORED_PATTERNS,
    "website": _WEBSITE_PATTERNS,
    "staff": _STAFF_PATTERNS,
    "process": _PROCESS_PATTERNS,
}

def _is_negated_grievance(text: str, match_start: int, match_end: int) -> bool:
    window_start = max(0, match_start - 40)
    window = text[window_start:match_start]
    return bool(_GRIEVANCE_NEGATION_RE.search(window))

def detect_grievance(text: str) -> Optional[dict]:
    if not text or not text.strip():
        return None
    tl = text.strip()
    has_exclusion = any(p.search(tl) for p in _GRIEVANCE_EXCLUSION_PATTERNS)
    best_subtype = None
    best_score = 0.0
    for subtype, patterns in _GRIEVANCE_SUBTYPE_PATTERNS.items():
        for pat, weight in patterns:
            m = pat.search(tl)
            if m and not _is_negated_grievance(tl, m.start(), m.end()):
                if has_exclusion and weight < 0.85:
                    score = weight * 0.4
                else:
                    score = weight
                if score > best_score:
                    best_score = score
                    best_subtype = subtype
    if best_subtype is None or best_score < 0.5:
        return None
    return {"value": best_subtype, "confidence": round(best_score, 2), "source": "grievance"}

# ──────────────────────────────────────────────────────────────────────
#  Shadow routing sink
# ──────────────────────────────────────────────────────────────────────

def _confidence_band(confidence: float) -> str:
    if confidence >= 1.0:
        return "1.0"
    if confidence >= 0.90:
        return "0.90-0.99"
    if confidence >= 0.80:
        return "0.80-0.89"
    return "below_0.80"

def _detect_language_hint(text: str) -> str:
    devanagari = set("अआइईउऊएऐओऔकखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहािीुूृेैोौंः")
    if text and set(text) & devanagari:
        return "hindi"
    bengali = set("অআইঈউঊঋএঐওঔকখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহািীুূৃেৈোৌংঃ")
    if text and set(text) & bengali:
        return "bengali"
    return "english"

class ShadowRoutingSink:
    """Silent signal detection + telemetry logging for production traffic.

    Runs emotion + grievance detectors at threshold. Logs would-route
    decisions to JSONL. Zero behavioral impact — pure observation.

    Deduplication: in-memory set of (session_id, text[:80]) pairs,
    seeded from existing log on init.
    """

    ELIGIBLE_SIGNALS = frozenset({"emotion", "grievance"})

    def __init__(self, path: Path = _TELEMETRY_PATH, threshold: float = _THRESHOLD) -> None:
        self.path = path
        self.threshold = threshold
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").strip().split("\n"):
                if line.strip():
                    try:
                        rec = json.loads(line)
                        key = rec.get("dedup_key", "")
                        if key:
                            self._seen.add(key)
                    except (json.JSONDecodeError, KeyError):
                        continue
        logger.info(
            "ShadowRoutingSink initialized: path=%s threshold=%.1f seen=%d",
            self.path, threshold, len(self._seen),
        )

    def record(self, text: str, session_id: str = "default", turn_number: int = 0) -> None:
        if not text or not text.strip():
            return
        dedup_key = f"{session_id}:{text[:80]}"
        if dedup_key in self._seen:
            return
        self._seen.add(dedup_key)

        t0 = time.time()
        emotion = detect_emotion(text)
        grievance = detect_grievance(text)
        elapsed_ms = (time.time() - t0) * 1000

        would_route = False
        selected_signal: Optional[str] = None
        selected_confidence = 0.0

        for sig_name in sorted(self.ELIGIBLE_SIGNALS):
            sig = emotion if sig_name == "emotion" else grievance
            if sig is not None and sig["confidence"] >= self.threshold:
                would_route = True
                selected_signal = sig_name
                selected_confidence = sig["confidence"]
                break

        record = {
            "event": "shadow_routing",
            "observation_id": dedup_key,
            "dedup_key": dedup_key,
            "session_id": session_id,
            "turn_number": turn_number,
            "text": text[:120],
            "language_hint": _detect_language_hint(text),
            "threshold": self.threshold,
            "would_route": would_route,
            "signal_type": selected_signal,
            "signal_confidence": selected_confidence,
            "confidence_band": _confidence_band(selected_confidence) if would_route else None,
            "emotion": emotion,
            "grievance": grievance,
            "latency_ms": round(elapsed_ms, 3),
            "timestamp": time.time(),
        }
        self._append(record)

    def _append(self, record: dict) -> None:
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            logger.exception("Failed to write shadow routing record to %s", self.path)


_sink: Optional[ShadowRoutingSink] = None


def get_shadow_sink() -> ShadowRoutingSink:
    global _sink
    if _sink is None:
        _sink = ShadowRoutingSink()
    return _sink


def record_shadow(text: str, session_id: str = "default", turn_number: int = 0) -> None:
    get_shadow_sink().record(text, session_id, turn_number)
