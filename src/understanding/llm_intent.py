"""LLM-first structured understanding.

Every student turn can be read by a real LLM which returns the full meaning in
one JSON call: the domain intent chosen from the whole vocabulary, any profile
fields the student stated, and an out-of-scope flag.

It is strictly optional. When no LLM is attached, or the output is missing /
invalid / carries an unexpected label, :meth:`LLMFirstUnderstanding.understand`
returns ``None`` and the deterministic engine keeps its own result unchanged —
so the default pipeline (benchmarks/tests without an explicit LLM) stays
byte-identical to the deterministic engine.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from src.llm.interfaces import LLMAdapter

logger = logging.getLogger(__name__)

# Intent labels the model is allowed to return. ``out_of_scope`` and ``unknown``
# never override the deterministic winner — they keep it.
VALID_INTENTS = (
    "admission", "fee", "hostel", "placement", "scholarship", "cutoff",
    "program", "department", "faculty", "hod", "seats", "timings",
    "safety", "transfer", "distance_education", "grievance",
    "counseling_info", "document", "career_confusion", "lateral_entry",
    "management_quota", "nri_admission", "sports_quota", "loan",
    "institution", "backlog", "greeting", "help_request",
    "self_introduction", "social_return", "general", "unknown",
)

# Conversational glue labels (not a subject the student is asking about).
CONVERSATIONAL_INTENTS = frozenset(
    {"greeting", "help_request", "self_introduction", "social_return", "general"},
)

_INTENT_DESCRIPTIONS = {
    "admission": "applying to / getting admission, eligibility, counseling for admission",
    "fee": "fees, tuition, cost, installment",
    "hostel": "hostel, accommodation, mess, staying on campus",
    "placement": "placements, jobs, packages, companies",
    "scholarship": (
        "scholarships, stipend, financial aid, "
        "scholarship eligibility or disqualification"
    ),
    "cutoff": "cutoff ranks, branch-wise cutoff",
    "program": "what is taught, subjects, curriculum of a branch",
    "department": "departments in the college",
    "faculty": "teachers, professors, faculty information",
    "hod": "head of department",
    "seats": "seat availability, seat intake",
    "timings": "class or college timings",
    "safety": "campus safety, security, ragging, girls' hostel safety",
    "transfer": "transferring or migrating between colleges",
    "distance_education": "distance or online learning programs",
    "grievance": "complaints, re-evaluation, poor experience, lodging an issue",
    "counseling_info": "counseling dates, process, steps, counseling documents",
    "document": "documents required for admission",
    "career_confusion": "confused about which branch or career to pick",
    "lateral_entry": "diploma or degree lateral entry",
    "management_quota": "management quota seats",
    "nri_admission": "NRI admission",
    "sports_quota": "sports quota",
    "loan": "education loan",
    "institution": "general facts about the college or institution",
    "backlog": (
        "backlog or arrear subjects, failed subjects, "
        "clearing arrears, effect of backlog"
    ),
    "greeting": "casual hello or hi",
    "help_request": "asking for general help or topics (i need help, can you help me)",
    "self_introduction": "asking who or what you are",
    "social_return": (
        "rejoining the conversation (i'm back, i am back). "
        "CAUTION: 'back in a subject' or 'got a back' means BACKLOG, not social return"
    ),
    "general": "vague or unspecific college talk",
    "unknown": "cannot determine",
}

_PROMPT_TEMPLATE = (
    "You are the understanding layer of a college admission chatbot.\n"
    "Read the student's message and answer with ONLY one JSON object, no extra text:\n"
    "{{\"intent\": \"admission\", \"out_of_scope\": false, "
    "\"profile\": {{\"rank\": null, \"pcm_percentage\": null, \"category\": null, "
    "\"interest\": null, \"budget_lakh\": null, \"board\": null, \"location\": null}}}}\n"
    "\n"
    "intent must be exactly one of these labels:\n"
    "{intents}\n"
    "\n"
    "out_of_scope: true only when the message is NOT about this college chatbot "
    "at all (weather, jokes, unrelated topics). Otherwise false.\n"
    "\n"
    "profile: extract ONLY fields the student explicitly stated. "
    "rank is the WBJEE rank as a number (\"25k\" -> 25000). "
    "pcm_percentage is a 0-100 number (\"65%\" -> 65). "
    "category is one of general/obc/sc/st/ews. "
    "interest is the branch or stream the student prefers (CSE, ECE, IT, ME, ...). "
    "budget_lakh is family budget in lakhs. board is the school board. "
    "location is a town or city. Use null for anything not stated.\n"
    "\n"
    "Student message: {text}"
)


def parse_llm_json(raw: str) -> dict[str, Any] | None:
    """Tolerant JSON parse for LLM structured output.

    Strips ```json fences and stray backticks, then returns the object.
    Returns ``None`` for empty/non-JSON/non-object output so callers can
    fall back to the deterministic reading.
    """
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    text = text.strip("`").strip()
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def validate_profile_fields(raw: dict[str, Any]) -> dict[str, Any]:
    """Strictly validate LLM-extracted profile fields (shared by the semantic NLU).

    Only well-formed, in-range values survive; anything ambiguous is dropped
    so the interpreter never invents profile facts.
    """
    clean: dict[str, Any] = {}

    rank = raw.get("rank")
    if isinstance(rank, bool):
        pass
    elif isinstance(rank, (int, float)) and 0 < rank <= 500000:
        clean["rank"] = int(rank)
    elif isinstance(rank, str) and rank.strip().isdigit():
        value = int(rank.strip())
        if 0 < value <= 500000:
            clean["rank"] = value

    pcm = raw.get("pcm_percentage")
    if isinstance(pcm, bool):
        pass
    elif isinstance(pcm, (int, float)) and 0 <= pcm <= 100:
        clean["pcm_percentage"] = float(pcm)
    elif isinstance(pcm, str):
        match = re.match(r"^\s*(\d{1,3}(?:\.\d+)?)", pcm)
        if match and 0 <= float(match.group(1)) <= 100:
            clean["pcm_percentage"] = float(match.group(1))

    category = raw.get("category")
    if isinstance(category, str):
        cat = category.strip().lower().replace(" ", "")
        if cat in ("gn", "gen", "generalcategory"):
            cat = "general"
        if cat in ("obc", "sc", "st", "ews", "general", "other", "others"):
            clean["category"] = cat if cat != "other" else "others"

    for key in ("interest", "board", "location"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            clean[key] = value.strip()[:40]

    budget = raw.get("budget_lakh")
    if isinstance(budget, bool):
        pass
    elif isinstance(budget, (int, float)) and 0 < budget:
        clean["budget_lakh"] = float(budget)
    elif isinstance(budget, str):
        match = re.match(r"^\s*(\d+(?:\.\d+)?)", budget)
        if match and float(match.group(1)) > 0:
            clean["budget_lakh"] = float(match.group(1))

    return clean


@dataclass
class LLMUnderstandingResult:
    intent: str = "unknown"
    profile: dict[str, Any] = field(default_factory=dict)
    out_of_scope: bool = False


class LLMFirstUnderstanding:
    """Structured LLM understanding (intent + profile + out-of-scope flag)."""

    def __init__(self, llm: LLMAdapter | None = None) -> None:
        self._llm = llm
        self._intent_list = "\n".join(
            f"- {label}: {desc}" for label, desc in _INTENT_DESCRIPTIONS.items()
        )

    @property
    def llm(self) -> LLMAdapter | None:
        return self._llm

    def understand(self, text: str) -> LLMUnderstandingResult | None:
        """Return the structured reading, or None to keep the deterministic result.

        None on: no LLM, unparseable output, an unexpected intent label, or any
        exception.
        """
        if self._llm is None:
            return None
        try:
            response = self._llm.generate(
                self._build_prompt(text), temperature=0.0, max_tokens=256,
            )
            parsed = self._parse(response.text)
        except Exception as exc:  # noqa: BLE001 - understanding must never raise
            logger.warning("LLM understanding failed: %s", exc)
            return None
        if parsed is None:
            return None
        intent, raw_profile, out_of_scope = parsed
        if intent not in VALID_INTENTS:
            return None
        return LLMUnderstandingResult(
            intent=intent,
            profile=self._validate_profile(raw_profile),
            out_of_scope=out_of_scope,
        )

    def _build_prompt(self, text: str) -> str:
        return _PROMPT_TEMPLATE.format(
            intents=self._intent_list, text=text.strip()[:400],
        )

    @staticmethod
    def _parse(raw: str) -> tuple[str, dict[str, Any], bool] | None:
        data = parse_llm_json(raw)
        if data is None:
            return None
        intent = data.get("intent")
        if not isinstance(intent, str) or not intent:
            return None
        profile = data.get("profile")
        if not isinstance(profile, dict):
            profile = {}
        return intent, profile, bool(data.get("out_of_scope", False))

    @staticmethod
    def _validate_profile(raw: dict[str, Any]) -> dict[str, Any]:
        return validate_profile_fields(raw)
