"""
Admission vocabulary — structured concepts, not regexes.

Each concept maps spoken/written terms to a canonical concept ID.
The DomainInterpreter uses these to infer what the student actually means.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Concept:
    id: str
    category: str
    synonyms: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Admission pathways ────────────────────────────────────────────────

PATHWAYS: list[Concept] = [
    Concept("regular", "pathway", synonyms=["regular admission", "fresh admission"]),
    Concept("lateral_entry", "pathway",
            synonyms=["lateral", "lateral entry", "direct entry", "direct second year",
                      "diploma admission", "jexpo"],
            patterns=[r"\blateral\b", r"\bdiploma\b", r"\bpolytechnic\b", r"\bjexpo\b",
                      r"second\s*year", r"direct\s*admission"]),
    Concept("management_quota", "pathway",
            synonyms=["management quota", "management seat", "paid seat",
                      "donation seat", "payment seat"],
            patterns=[r"management\s*quota", r"donation", r"paid\s*seat",
                      r"management\s*seat"]),
    Concept("sports_quota", "pathway",
            synonyms=["sports quota", "sports admission"],
            patterns=[r"sports\s*quota", r"athlete\b", r"state.level\s+(player|athlete)",
                      r"national\s+level"]),
    Concept("nri", "pathway",
            synonyms=["nri", "nri quota", "nri seat", "foreign", "international",
                      "foreign national"],
            patterns=[r"\bnri\b", r"foreign\b", r"international\b", r"abroad\b",
                      r"dubai\b", r"us\b", r"uk\b", r"usa\b"]),
    Concept("transfer", "pathway",
            synonyms=["transfer", "college change", "migration", "switch college"],
            patterns=[r"\btransfer\b", r"\bmigration\b", r"change\s+college",
                      r"shift\s+to", r"current.*college"]),
    Concept("scholarship", "pathway",
            synonyms=["scholarship", "financial aid", "fee waiver", "stipend"],
            patterns=[r"scholarship", r"financial\s*aid", r"fee\s*waiver",
                      r"scholarship\s*renewal", r"post.matric"]),
]

# ── Qualifications ────────────────────────────────────────────────────

QUALIFICATIONS: list[Concept] = [
    Concept("diploma", "qualification",
            patterns=[r"\bdiploma\b", r"\bpolytechnic\b", r"3.year\s*diploma"]),
    Concept("btech", "qualification",
            patterns=[r"\bb\.?\s*tech\b", r"\bbe\b", r"\bengineering\b"]),
    Concept("12th", "qualification",
            patterns=[r"\b12(th|th std|th class|th grade)\b", r"\bhsc\b",
                      r"higher\s*secondary", r"\bintermediate\b"]),
]

# ── Student types ─────────────────────────────────────────────────────

STUDENT_TYPES: list[Concept] = [
    Concept("prospective", "student_type",
            patterns=[r"want\s+to\s+(join|take|study|pursue)", r"can\s+I\s+get",
                      r"admission", r"apply\s+for"]),
    Concept("existing", "student_type",
            patterns=[r"\d(st|nd|rd|th)\s*year", r"current\s+student",
                      r"already\s+(studying|enrolled)", r"semester"]),
    Concept("parent", "student_type",
            patterns=[r"\b(?:my\s+)?(?:son|daughter|child|ward)\b", r"\bparent\b",
                      r"my\s+(?:boy|girl)\b"]),
]

# ── Intents (extended beyond regex patterns) ──────────────────────────

INTENT_CONCEPTS: list[Concept] = [
    Concept("admission", "intent",
            patterns=[r"admission", r"apply", r"eligib", r"can.*get",
                      r"\d+\s*[k]?\s*rank", r"rank.*(\d+)",
                      r"cutoff", r"counseling",
                      r"(?:got|have|secured|scored)\s+\d+", r"want\s+(?:to\s+)?(?:study|do|take|pursue|get)",
                      r"interest\s+(?:is|in)"]),
    Concept("fee", "intent",
            patterns=[r"\bfee[s]?\b", r"tuition", r"cost\s+of", r"how\s+much",
                      r"kitna\s+fee", r"fees\s+structure"]),
    Concept("scholarship", "intent",
            patterns=[r"scholarship", r"financial\s+a[idy]", r"stipend",
                      r"concession", r"free.ship"]),
    Concept("hostel", "intent",
            patterns=[r"\bhostel\b", r"accommodation", r"\broom\b", r"mess\b",
                      r"boarding", r"safety\b.*(?:girl|women|hostel)"]),
    Concept("placement", "intent",
            patterns=[r"placement", r"\bpackage\b", r"\brecruit", r"\bjobs?\b",
                      r"salary", r"\bCTC\b"]),
    Concept("lateral_entry", "intent",
            patterns=[r"lateral", r"diploma.*admission", r"jexpo"]),
    Concept("management_quota", "intent",
            patterns=[r"management\s*quota", r"donation", r"payment\s*seat"]),
    Concept("sports_quota", "intent",
            patterns=[r"sports\s*quota", r"sports\s+admission"]),
    Concept("transfer", "intent",
            patterns=[r"transfer", r"migration", r"change.*college", r"shift.*college"]),
    Concept("grievance", "intent",
            patterns=[r"grievance", r"complaint", r"re.evaluation",
                      r"marks.*lower", r"issue.*exam"]),
    Concept("distance_education", "intent",
            patterns=[r"distance", r"online.*(?:course|degree|program)",
                      r"correspondence", r"blended"]),
    Concept("counseling_info", "intent",
            patterns=[r"counseling", r"document.*(?:need|required)",
                      r"when.*counseling", r"counseling.*date"]),
    Concept("career_confusion", "intent",
            patterns=[r"confused", r"not\s+sure", r"don.t\s+know\s+what",
                      r"parent.*want", r"should\s+I\s+(?:do|take|choose)"]),
    Concept("nri_admission", "intent",
            patterns=[r"\bnri\b", r"foreign\b", r"international\b.*(?:student|admission)",
                      r"abroad"]),
    Concept("recommendation", "intent",
            patterns=[r"recommend", r"suggest", r"which\s+(?:branch|course|subject)",
                      r"what\s+should\s+I\s+(?:choose|take|do|opt)"]),
    Concept("loan", "intent",
            patterns=[r"\bloan\b", r"education\s+loan", r"bank\s+loan",
                      r"finance", r"emi\b"]),
    Concept("document", "intent",
            patterns=[r"document", r"certificate", r"marksheet", r"transcript",
                      r"proof", r"id\s+proof"]),
]

# ── Admission-specific entities ───────────────────────────────────────

ADMISSION_ENTITIES: list[Concept] = [
    Concept("current_college", "entity",
            patterns=[r"current.*college", r"at\s+\w+\s+college",
                      r"studying\s+(?:in|at)\s+\w+", r"in\s+\w+\s+year\s+at",
                      r"private\s+college", r"another\s+college"]),
    Concept("current_branch", "entity",
            patterns=[r"(?:studying|pursuing|doing)\s+\w+\s+(?:in|at)",
                      r"(?:1st|2nd|3rd|4th)\s*year.*(?:in|of)",
                      r"\w+\s+(?:branch|stream|subject)\s+at",
                      r"year\s+(EE|ECE|CSE|ME|CE|IT)"]),
    Concept("diploma_holder", "entity",
            patterns=[r"\bdiploma\b", r"\bpolytechnic\b"]),
    Concept("existing_student", "entity",
            patterns=[r"(?:2nd|3rd|4th)\s*year", r"current\s+student",
                      r"semester", r"\d+th\s+sem"]),
    Concept("career_goal", "entity",
            patterns=[r"want\s+to\s+become", r"career", r"future\s+plan",
                      r"aim\s+(?:is|in)"]),
    Concept("safety_concern", "entity",
            patterns=[r"\bsafe\b", r"\bsafety\b", r"\bsecurity\b",
                      r"heard\s+things", r"worried\s+about"]),
    Concept("budget_concern", "entity",
            patterns=[r"budget\s+(?:is\s+)?tight", r"expensive", r"afford\b",
                      r"costly", r"tight\s+budget", r"financial\s+constraint"]),
    Concept("parent_pressure", "entity",
            patterns=[r"parent.*want", r"father.*want", r"mother.*want",
                      r"family.*pressure", r"but\s+my\s+(?:parents|father|mother)"]),
    Concept("existing_grievance", "entity",
            patterns=[r"hasn.*t\s+been\s+renewed", r"not\s+renewed",
                      r"re-evaluation", r"lower\s+than\s+expected",
                      r"marks\s+are\s+low"]),
    Concept("conversational_mixed", "entity",
            patterns=[r"\b(?:mera|tera|kya|kaise|hai|hain)\b"]),
]


def match_concept(text: str, concepts: list[Concept]) -> list[Concept]:
    """Return all concepts whose patterns or synonyms match the text."""
    tl = text.lower()
    matched: list[Concept] = []
    for c in concepts:
        for syn in c.synonyms:
            if syn.lower() in tl:
                matched.append(c)
                break
        else:
            for pat in c.patterns:
                import re
                if re.search(pat, tl):
                    matched.append(c)
                    break
    return matched


def best_concept(text: str, concepts: list[Concept]) -> Concept | None:
    """Return the best-matching concept (most overlap)."""
    tl = text.lower()
    best = None
    best_score = 0
    for c in concepts:
        score = 0
        for syn in c.synonyms:
            if syn.lower() in tl:
                score += 2
        for pat in c.patterns:
            import re
            if re.search(pat, tl):
                score += 1
        if score > best_score:
            best_score = score
            best = c
    return best
