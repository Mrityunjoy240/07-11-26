"""Mine candidate signal-bearing turns from benchmark conversations.

This script applies broad lexical/semantic heuristics to find turns that
*may* contain structured signals (grievance, decision, emotion). It
intentionally casts a wider net than the production detectors to capture
cases the detectors might miss.

Output: data/evaluation/structured_signals/mined_candidates.jsonl

Each record includes:
  - conversation_id, turn_id, text
  - mining_scores: per-subtype lexical cue scores
  - overall_likelihood: max per signal type
  - scope: utterance_local | conversation_context_required | ambiguous
  - detector_output: what the current production detectors return
  - is_hard_negative: true if lexical cues exist but the turn is factually
    neutral (e.g., "What is the difference between fees for CSE and IT?")
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ── Broad mining heuristics (wider than detectors) ──────────────────────

_GRIEVANCE_CUES = {
    "waiting": [
        re.compile(r"\bwait(?:ing|ed|s)?\b", re.I),
        re.compile(r"\bno\s+(?:reply|response|update|answer|feedback)\b", re.I),
        re.compile(r"\bnot\s+(?:yet\s+)?(?:responded|replied|answered|updated)\b", re.I),
        re.compile(r"\b(?:hasn|haven)\W?t\s+(?:been|got)\s+(?:any\s+)?(?:reply|response)\b", re.I),
        re.compile(r"\bsame\s+(?:question|answer|response|reply|thing)\b", re.I),
        re.compile(r"\basked?\s+(?:the\s+same|this|that|it)\s+\d+\s+(?:time|hour|day)\b", re.I),
        re.compile(r"\bhow\s+(?:much\s+)?longer?\b", re.I),
        re.compile(r"\bstill\s+(?:waiting|no|haven|hasn)\b", re.I),
        re.compile(r"\b(?:nobody|no\s+one)\s+(?:has\s+)?(?:got back|responded|replied)\b", re.I),
    ],
    "ignored": [
        re.compile(r"\b(?:nobody|no\s+one)\s+(?:has\s+)?(?:responded|replied|answered|got\s+back)\b", re.I),
        re.compile(r"\bignored\b", re.I),
        re.compile(r"\boverlooked\b", re.I),
        re.compile(r"\bno\s+(?:one|body)\s+is\s+responding\b", re.I),
        re.compile(r"\bwhy\s+(?:is\s+)?(?:nobody|no\s+one|you)\s+(?:responding|replying|answering)\b", re.I),
    ],
    "website": [
        re.compile(r"\b(?:website|portal|site|system)\s+(?:is\s+)?(?:not\s+)?(?:working|loading|responding|down|broken|error)\b", re.I),
        re.compile(r"\b(?:cannot|can\W?t)\s+(?:access|open|load|login|submit|upload)\b", re.I),
        re.compile(r"\berror\b", re.I),
        re.compile(r"\b(?:bug|glitch|crash)\b", re.I),
    ],
    "staff": [
        re.compile(r"\b(?:want|need|like)\s+to\s+speak\s+(?:to|with)\s+(?:someone|manager|principal|authority|in\s+charge|admin)\b", re.I),
        re.compile(r"\bstaff\b", re.I),
        re.compile(r"\badmin(?:istration)?\b", re.I),
    ],
    "process": [
        re.compile(r"\bprocess\s+is\s+(?:a\s+)?(?:mess|disaster|nightmare|terrible|awful|horrible|pathetic)\b", re.I),
        re.compile(r"\b(?:unacceptable|ridiculous|absurd)\b", re.I),
        re.compile(r"\b(?:system|process|service)\s+is\s+(?:useless|stupid|broken|terrible|awful|horrible|pathetic|garbage)\b", re.I),
        re.compile(r"\bwaste\s+(?:of|of\s+time)\b", re.I),
        re.compile(r"\bwhat\s+kind\s+of\s+(?:service|system|process)\b", re.I),
    ],
}

_DECISION_CUES = {
    "compare": [
        re.compile(r"\bcompare\b", re.I),
        re.compile(r"\bdifference\s+between\b", re.I),
        re.compile(r"\bvs\.?\b", re.I),
        re.compile(r"\bversus\b", re.I),
        re.compile(r"\bor\b.{1,60}\bor\b", re.I),
        re.compile(r"\bwhich\s+is\s+better\b", re.I),
        re.compile(r"\bwhich\s+(?:one\s+)?(?:can|will)\s+i\s+get\b", re.I),
        re.compile(r"\bwhat\s+(?:are\s+)?my\s+chances?\b", re.I),
        re.compile(r"\bwhat\s+(?:branch|option|choice)\s+(?:should|can)\s+i\b", re.I),
    ],
    "recommend": [
        re.compile(r"\bsuggest\b", re.I),
        re.compile(r"\brecommend(?:ation)?\b", re.I),
        re.compile(r"\bwhat\s+(?:would|do)\s+you\s+(?:recommend|suggest)\b", re.I),
        re.compile(r"\bwhich\s+(?:one\s+)?should\s+i\b", re.I),
        re.compile(r"\bbest\s+(?:option|branch|choice)\s+for\s+me\b", re.I),
        re.compile(r"\bkaun\s+sa\b", re.I),
        re.compile(r"\bkya\s+suggest\b", re.I),
        re.compile(r"\bwhat\s+do\s+you\s+think\b", re.I),
        re.compile(r"\b(?:your\s+)?suggestion?\b", re.I),
    ],
    "choose": [
        re.compile(r"\bchoose?\b", re.I),
        re.compile(r"\bdecide?\b", re.I),
        re.compile(r"\bpick\b", re.I),
        re.compile(r"\bconfused\s+between\b", re.I),
        re.compile(r"\btorn\s+between\b", re.I),
        re.compile(r"\bstuck\s+between\b", re.I),
        re.compile(r"\bhelp\s+me\s+(?:decide|choose|pick)\b", re.I),
        re.compile(r"\bwhat\s+(?:should\s+i|to)\s+(?:choose|pick|take|go\s+for)\b", re.I),
        re.compile(r"\bwhich\s+one\s+to\s+go\s+with\b", re.I),
        re.compile(r"\bwhat\s+(?:should\s+)?i\s+(?:do|take|choose)\b", re.I),
        re.compile(r"\bcan\s+tell\s+(?:me\s+)?which\s+(?:one\s+)?(?:should\s+)?i\b", re.I),
        re.compile(r"\bgoing\s+for\b.{1,30}\b(?:or|and)\b.{1,30}\b(?:too|also|both)\b", re.I),
        re.compile(r"\bkarein?\s+ya\b", re.I),
        re.compile(r"\bchoose\s+kare\b", re.I),
        re.compile(r"\bdecide\s+nahi\s+(?:kar|ho)\b", re.I),
        re.compile(r"\bkaunsa\s+(?:choose|pick)\s+kare\b", re.I),
    ],
    "alternative": [
        re.compile(r"\bwhat\s+other\s+(?:branches?|options?|choices?)\b", re.I),
        re.compile(r"\bwhat\s+else\b", re.I),
        re.compile(r"\bany\s+other\s+(?:options?|choices?|alternatives?)\b", re.I),
        re.compile(r"\bbackup\b", re.I),
        re.compile(r"\balternative\b", re.I),
        re.compile(r"\bfallback\b", re.I),
        re.compile(r"\bplan\s*[bB]\b", re.I),
        re.compile(r"\bother\s+options?\b", re.I),
        re.compile(r"\bis\s+there\s+(?:a|an|any)\b.{1,30}\boption\b", re.I),
    ],
    "tradeoff": [
        re.compile(r"\bpros?\s+(?:and|&|\/)\s+cons?\b", re.I),
        re.compile(r"\bworth\s+it\b", re.I),
        re.compile(r"\b(?:gain|lose)\s+by\b", re.I),
        re.compile(r"\btrade\s*off\b", re.I),
        re.compile(r"\badvantages?\s+(?:and|&|\/)\s+disadvantages?\b", re.I),
        re.compile(r"\bdrawbacks?\b", re.I),
        re.compile(r"\bdownside\b", re.I),
    ],
    "preference": [
        re.compile(r"\b(?:parents?|family|mother|father|mummy|papa)\s+(?:want|prefer|say|think|suggest)\b", re.I),
        re.compile(r"\bI\s+(?:am\s+)?(?:more\s+)?interested?\s+in\b.{1,30}\bbut\b", re.I),
        re.compile(r"\bI\s+like\b.{1,50}\b(?:but|also|too|and)\b.{1,30}\b(?:also|too|and)\b", re.I),
    ],
}

_EMOTION_CUES = {
    "frustration": [
        re.compile(r"\bfrustrated?\b", re.I),
        re.compile(r"\bfed\s+up\b", re.I),
        re.compile(r"\bsick\s+of\b", re.I),
        re.compile(r"\bannoyed?\b", re.I),
        re.compile(r"\buseless\b", re.I),
        re.compile(r"\bterrible\b", re.I),
        re.compile(r"\bhorrible\b", re.I),
        re.compile(r"\bpathetic\b", re.I),
        re.compile(r"\bunacceptable\b", re.I),
        re.compile(r"\bwaste\s+(?:of|of\s+time)\b", re.I),
        re.compile(r"\btoo\s+complicated\b", re.I),
        re.compile(r"\b(?:stupid|dumb)\b", re.I),
        re.compile(r"\b(?:beating\s+around\s+the\s+bush|straight|no\s+beating|tell\s+me\s+straight)\b", re.I),
        re.compile(r"\b(?:seriously|really)\?{2,}\b", re.I),
        re.compile(r"\bwhat\s+is\s+(?:this|that)\s+(?:supposed\s+to\s+mean|all\s+about)\b", re.I),
        re.compile(r"\bnot\s+(?:again|another)\b", re.I),
    ],
    "anxiety": [
        re.compile(r"\bworried?\b", re.I),
        re.compile(r"\bnervous\b", re.I),
        re.compile(r"\bscared\b", re.I),
        re.compile(r"\btense\b", re.I),
        re.compile(r"\banxious\b", re.I),
        re.compile(r"\bafraid\b", re.I),
        re.compile(r"\bstress(?:ed|ful)?\b", re.I),
        re.compile(r"\bpanic(?:king|ked|s)?\b", re.I),
        re.compile(r"\bfreaking\s+out\b", re.I),
        re.compile(r"\buneasy\b", re.I),
        re.compile(r"\bconcerned?\b", re.I),
        re.compile(r"\bworries?\b", re.I),
        re.compile(r"\bpareshan\b", re.I),
        re.compile(r"\b(?:very|so|really|extremely)\s+(?:worried|concerned|nervous|stressed)\b", re.I),
        re.compile(r"\b(?:what|how)\s+(?:about|will|would|shall)\s+(?:my|our|the)\s+(?:child|son|daughter|beti|beta|bacha)\b", re.I),
    ],
    "confusion": [
        re.compile(r"\bconfused?\b", re.I),
        re.compile(r"\bconfusion\b", re.I),
        re.compile(r"\bdon\W?t\s+understand\b", re.I),
        re.compile(r"\bnot\s+sure\b", re.I),
        re.compile(r"\bcan\W?t\s+(?:decide|understand)\b", re.I),
        re.compile(r"\bno\s+idea\b", re.I),
        re.compile(r"\bdilemma\b", re.I),
        re.compile(r"\bunclear\b", re.I),
        re.compile(r"\bunsure\b", re.I),
        re.compile(r"\bconfused?\b.{0,30}\b(?:between|about|with)\b", re.I),
        re.compile(r"\bsamajh\s+(?:mein\s+)?nahi\s+(?:aaya|aati|aa raha)\b", re.I),
        re.compile(r"\b(?:kya|what)\s+(?:hoga|hona|hain)\b", re.I),
        re.compile(r"\b(?:doubt|question)\s+(?:hai|hain)\b", re.I),
    ],
    "urgency": [
        re.compile(r"\burgent\b", re.I),
        re.compile(r"\bimmediately?\b", re.I),
        re.compile(r"\basap\b", re.I),
        re.compile(r"\bhurry\b", re.I),
        re.compile(r"\bdeadline\b", re.I),
        re.compile(r"\brunning\s+out\s+of\s+time\b", re.I),
        re.compile(r"\bsoon\b", re.I),
        re.compile(r"\btime\s+(?:is\s+)?running\b", re.I),
        re.compile(r"\bexpir(?:e|ing|ed)\b", re.I),
        re.compile(r"\bquick(?:ly)?\b", re.I),
        re.compile(r"\bneed\s+.{0,40}?\bat?\s+(?:soon|earliest)\b", re.I),
        re.compile(r"\blast\s+(?:date|day|chance|opportunity)\b", re.I),
        re.compile(r"\brunning\s+(?:late|behind)\b", re.I),
        re.compile(r"\b(?:last|final)\s+(?:minute|moment)\b", re.I),
    ],
}

# ── Contextual / indirect language cues ────────────────────────────────

_CONTEXTUAL_ANXIETY_PATTERNS = [
    re.compile(r"\bmy\s+(?:daughter|son|child|beti|beta|bacha)\b", re.I),
    re.compile(r"\b(?:meri\s+beti|mera\s+beta|hamara\s+bacha)\b", re.I),
    re.compile(r"\bworried\s+(?:about|for)\s+(?:my|the|our)\s+(?:daughter|son|child|beti|beta)\b", re.I),
    re.compile(r"\bI\s+am\s+(?:very\s+)?(?:worried|concerned|nervous)\b", re.I),
    re.compile(r"\b(?:really|very|so)\s+(?:worried|concerned|nervous|stressed|scared)\b", re.I),
    re.compile(r"\b(?:my|our|the)\s+(?:child|son|daughter|beti|beta)\s+(?:scored|got|has|is|wants)\b", re.I),
    re.compile(r"\b(?:what|how)\s+(?:if|about)\s+(?:my|our|the)\s+(?:child|son|daughter|beti|beta)\b", re.I),
    re.compile(r"\b(?:can|will)\s+(?:my|our|the)\s+(?:child|son|daughter|beti|beta)\s+(?:get|secure)\b", re.I),
    re.compile(r"\bis\s+it\s+(?:possible|likely|there\s+a\s+chance)\b", re.I),
    re.compile(r"\bchances?\s+(?:are\s+)?(?:low|slim|not\s+good|bleak|bad)\b", re.I),
]

_CONTEXTUAL_GRIEVANCE_PATTERNS = [
    re.compile(r"\b(?:nobody|no\s+one)\s+(?:responded|replied|answered|got\s+back)\b", re.I),
    re.compile(r"\bI\s+have\s+been\s+(?:waiting|asking)\b", re.I),
    re.compile(r"\bwhy\s+(?:did\s+it\s+take|hasn|haven|has\s+no\s+one|is\s+no\s+one)\b", re.I),
    re.compile(r"\bdid\s+anyone\s+(?:respond|reply|answer|get\s+back)\b", re.I),
    re.compile(r"\bfine\s*,\s*but\b", re.I),
    re.compile(r"\bstill\s+(?:no|haven|hasn|waiting)\b", re.I),
    re.compile(r"\b(?:told|said)\s+you\s+(?:already|before|earlier)\b", re.I),
    re.compile(r"\b(?:i\s+)?already\s+(?:told|said|asked|mentioned)\b", re.I),
    re.compile(r"\bplease\s+(?:listen|pay\s+attention|focus)\b", re.I),
]

_CONTEXTUAL_DECISION_PATTERNS = [
    re.compile(r"\bmy\s+(?:parents?\s+)?(?:want|prefer|say|think|suggest)\b", re.I),
    re.compile(r"\bI\s+like\s+.{1,30}\s+but\s+.{1,30}\s+(?:also|too)\b", re.I),
    re.compile(r"\bI\s+am\s+(?:more\s+)?interested?\s+in\b", re.I),
    re.compile(r"\bwhich\s+(?:college|branch|stream)\s+would\s+be\s+(?:better|good|best)\b", re.I),
    re.compile(r"\bwhat\s+(?:are|do)\s+you\s+(?:think|recommend)\b", re.I),
    re.compile(r"\bI\s+(?:want|need|would\s+like)\s+to\s+(?:know|understand|figure\s+out)\s+(?:which|what)\b", re.I),
    re.compile(r"\bis\s+it\s+(?:better|worse|good|bad)\s+to\b", re.I),
    re.compile(r"\b(?:choosing|selecting|picking)\s+(?:between|among)\b", re.I),
]

# ── Factual domain keywords (reduce but don't override signal cues) ────

_FACTUAL_KEYWORDS = ["fee", "fees", "cutoff", "hostel", "syllabus", "curriculum", "scholarship", "seat", "intake", "college"]


def _score_mining(text: str, cue_dict: dict) -> dict:
    """Score text against a set of cue patterns. Returns {subtype: max_score}."""
    scores = {}
    for subtype, patterns in cue_dict.items():
        best = 0.0
        for pat in patterns:
            m = pat.search(text)
            if m:
                score = 0.7
                match_len = m.end() - m.start()
                if match_len > 15:
                    score = 0.9
                elif match_len > 8:
                    score = 0.8
                if score > best:
                    best = score
        if best > 0:
            scores[subtype] = best
    return scores


def _score_contextual(text: str) -> dict:
    """Score contextual/indirect language that detectors might miss."""
    ctx = {}
    for p in _CONTEXTUAL_ANXIETY_PATTERNS:
        if p.search(text):
            ctx["emotion"] = max(ctx.get("emotion", 0), 0.5)
    for p in _CONTEXTUAL_GRIEVANCE_PATTERNS:
        if p.search(text):
            ctx["grievance"] = max(ctx.get("grievance", 0), 0.5)
    for p in _CONTEXTUAL_DECISION_PATTERNS:
        if p.search(text):
            ctx["decision"] = max(ctx.get("decision", 0), 0.5)
    return ctx


def _factual_downweight(text: str) -> float:
    """Return a multiplier (0.0 to 1.0) based on how factual the text is.

    Texts dominated by factual keywords (fee, cutoff, etc.) get downweighted
    but not zeroed out, since genuine signals CAN co-occur with factual terms.
    """
    tl = text.lower()
    words = tl.split()
    factual_hits = sum(1 for w in _FACTUAL_KEYWORDS if w in tl)
    if factual_hits == 0:
        return 1.0
    # More factual keywords = stronger downweight, but never fully zero
    return max(0.5, 1.0 - factual_hits * 0.15)


# ── Main mining logic ──────────────────────────────────────────────────

BENCH_DIR = Path("data/benchmark/conversations")
OUTPUT_DIR = Path("data/evaluation/structured_signals")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

all_records: list[dict] = []
file_count = 0
turn_count = 0

for fpath in sorted(BENCH_DIR.rglob("*.json")):
    try:
        conv = json.loads(fpath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"SKIP {fpath.name}: {e}", file=sys.stderr)
        continue
    file_count += 1
    cid = conv.get("id", fpath.stem)
    for t_idx, turn in enumerate(conv.get("turns", [])):
        text = (turn.get("student") or "").strip()
        if not text:
            continue
        turn_count += 1

        grief_scores = _score_mining(text, _GRIEVANCE_CUES)
        decis_scores = _score_mining(text, _DECISION_CUES)
        emot_scores = _score_mining(text, _EMOTION_CUES)
        contextual = _score_contextual(text)

        max_grief = max(grief_scores.values()) if grief_scores else 0.0
        max_decis = max(decis_scores.values()) if decis_scores else 0.0
        max_emot = max(emot_scores.values()) if emot_scores else 0.0
        max_ctx_grief = contextual.get("grievance", 0.0)
        max_ctx_decis = contextual.get("decision", 0.0)
        max_ctx_emot = contextual.get("emotion", 0.0)

        overall_grief = max(max_grief, max_ctx_grief)
        overall_decis = max(max_decis, max_ctx_decis)
        overall_emot = max(max_emot, max_ctx_emot)
        overall_max = max(overall_grief, overall_decis, overall_emot)

        has_contextual = bool(contextual)
        has_direct = max_grief > 0 or max_decis > 0 or max_emot > 0
        if has_contextual and not has_direct:
            scope = "conversation_context_required"
        elif has_contextual and has_direct:
            scope = "ambiguous"
        else:
            scope = "utterance_local"

        # Apply factual downweight — factual terms reduce but don't zero scores
        fw = _factual_downweight(text)
        downweighted_grief = overall_grief * fw
        downweighted_decis = overall_decis * fw
        downweighted_emot = overall_emot * fw
        downweighted_max = max(downweighted_grief, downweighted_decis, downweighted_emot)

        has_signal_cue = overall_max >= 0.4
        dominates_signal = any(
            s >= 0.7 for s in [overall_grief, overall_decis, overall_emot]
        )

        from src.understanding.signals.grievance import detect_grievance
        from src.understanding.signals.decision import detect_decision_intent
        from src.understanding.signals.emotion import detect_emotion

        d_g = detect_grievance(text)
        d_d = detect_decision_intent(text)
        d_e = detect_emotion(text)

        record = {
            "conversation_id": cid,
            "turn_id": t_idx,
            "domain": conv.get("domain", ""),
            "features": conv.get("features", []),
            "speaker_profile": conv.get("speaker_profile", ""),
            "text": text,
            "mining_scores": {
                "grievance": grief_scores,
                "decision": decis_scores,
                "emotion": emot_scores,
                "contextual": contextual,
            },
            "overall_likelihood": {
                "grievance": round(overall_grief, 2),
                "decision": round(overall_decis, 2),
                "emotion": round(overall_emot, 2),
                "max": round(overall_max, 2),
            },
            "downweighted_likelihood": {
                "grievance": round(downweighted_grief, 2),
                "decision": round(downweighted_decis, 2),
                "emotion": round(downweighted_emot, 2),
                "max": round(downweighted_max, 2),
                "factual_weight": round(fw, 2),
            },
            "scope": scope,
            "detector_output": {
                "grievance": {
                    "value": d_g.value if d_g else None,
                    "confidence": round(d_g.confidence, 2) if d_g else 0.0,
                },
                "decision": {
                    "value": d_d.value if d_d else None,
                    "confidence": round(d_d.confidence, 2) if d_d else 0.0,
                },
                "emotion": {
                    "value": d_e.value if d_e else None,
                    "confidence": round(d_e.confidence, 2) if d_e else 0.0,
                },
            },
            "source": "mined",
            "has_signal_cue": has_signal_cue,
            "dominates_signal": dominates_signal,
        }
        all_records.append(record)

# ── Select candidates ──────────────────────────────────────────────────
# Use downweighted score for classification, raw score for ordering
def _best_signal_type(r: dict) -> str:
    ol = r["overall_likelihood"]
    return max(
        ["grievance", "decision", "emotion"],
        key=lambda s: ol.get(s, 0),
    )

signal_candidates = [
    r for r in all_records
    if r["downweighted_likelihood"]["max"] >= 0.4 and r["has_signal_cue"]
]
negatives = [r for r in all_records if r not in signal_candidates]

print(f"Files processed: {file_count}")
print(f"Total turns: {turn_count}")
print(f"Signal candidates (downweighted score >= 0.4): {len(signal_candidates)}")
print(f"Pure negatives:                                {len(negatives)}")

# Print per-signal breakdown
sig_types = Counter(_best_signal_type(r) for r in signal_candidates)
print(f"  Per signal type: {dict(sig_types)}")

# Stratified selection — balance across signal types
random.seed(42)

SIGNAL_QUOTA = 80   # total signal candidates to include
NEG_QUOTA = 40      # pure negatives for contrast (hard negatives for detectors)
TARGET_TOTAL = 120

# Step 1: select up to 40 per signal type, prioritize utterance_local
def _selection_priority(r: dict) -> tuple:
    """Priority: utterance_local > ambiguous > conversation_context_required."""
    scope_order = {"utterance_local": 0, "ambiguous": 1, "conversation_context_required": 2}
    return (scope_order.get(r["scope"], 3), -r["overall_likelihood"]["max"])

selected_signal: list[dict] = []
per_sig_counts: dict[str, int] = defaultdict(int)
MAX_PER_SIG = 40

for r in sorted(signal_candidates, key=_selection_priority):
    bsig = _best_signal_type(r)
    if len(selected_signal) >= SIGNAL_QUOTA:
        break
    if per_sig_counts[bsig] >= MAX_PER_SIG:
        continue
    # Skip if already annotated (check annotations.jsonl)
    selected_signal.append(r)
    per_sig_counts[bsig] += 1

# Step 2: select negatives — prioritize detector FPs and near-misses
def _neg_priority(r: dict) -> tuple:
    """Priority: detector FP > near-miss (score > 0) > random."""
    has_detector = any(
        r["detector_output"][s]["value"] is not None
        for s in ["emotion", "grievance", "decision"]
    )
    score = r["overall_likelihood"]["max"]
    return (0 if has_detector else 1, -score if score > 0 else 2, random.random())

# Include current hard negatives (detector FPs / near-misses)
available_negs = [r for r in negatives if r not in selected_signal]
available_negs.sort(key=_neg_priority)
selected_negs = available_negs[:NEG_QUOTA]

candidates = selected_signal + selected_negs
candidates.sort(key=lambda r: f"{r['conversation_id']}.{r['turn_id']}")

output_path = OUTPUT_DIR / "mined_candidates.jsonl"
with open(output_path, "w", encoding="utf-8") as f:
    for r in candidates:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ── Report ──
print(f"\nWritten: {output_path}")
print(f"Total candidates: {len(candidates)}")
print(f"  Signal-bearing: {len(selected_signal)}")
print(f"    Per signal:   {dict(per_sig_counts)}")
print(f"  Negatives:      {len(selected_negs)}")

# Detector overlap on candidates
print("\n--- Detector overlap on selected candidates ---")
detected_by_detector = sum(
    1 for r in candidates
    if r["detector_output"]["grievance"]["value"]
    or r["detector_output"]["decision"]["value"]
    or r["detector_output"]["emotion"]["value"]
)
miner_only = sum(
    1 for r in selected_signal
    if not (r["detector_output"]["grievance"]["value"]
             or r["detector_output"]["decision"]["value"]
             or r["detector_output"]["emotion"]["value"])
)
print(f"  Detected by current detectors: {detected_by_detector} / {len(candidates)}")
print(f"  Miner-flagged but detector-missed: {miner_only} / {len(selected_signal)}")

# Scope distribution (signal candidates only)
print("\n--- Scope distribution (signal candidates) ---")
scope_counts = Counter(r["scope"] for r in selected_signal)
for scope, n in scope_counts.most_common():
    print(f"  {scope:40s} {n}")

# Domain summary
domains: dict[str, Counter] = defaultdict(Counter)
for r in candidates:
    d = domains[r["domain"]]
    if r in selected_signal:
        d["signal"] += 1
    else:
        d["neg"] += 1

print("\n--- Candidates by domain ---")
for dname in sorted(domains):
    d = domains[dname]
    total = d["signal"] + d["neg"]
    print(f"  {dname:20s} total={total:3d}  signal={d['signal']:3d}  neg={d['neg']:3d}")
