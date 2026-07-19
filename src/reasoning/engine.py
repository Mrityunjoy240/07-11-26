from __future__ import annotations

import logging
from typing import Any

from src.conversation.state import ConversationState
from src.engines.interfaces import ReasoningInput
from src.reasoning.models import EligibilityEstimate, ReasoningResult
from src.understanding.models import UnderstandingResult
from src.understanding.profile import is_field_set

logger = logging.getLogger(__name__)

_REQUIRED_PROFILE_FIELDS = [
    "academic.rank", "academic.pcm_percentage", "academic.board",
    "personal.category", "career.interest", "personal.budget", "personal.location",
]


class ReasoningEngine:
    VERSION = "v2"

    def process(self, input: ReasoningInput) -> ReasoningResult:
        return self.reason(
            input.understanding, input.state, input.college_brain
        )

    def reason(
        self,
        understanding: UnderstandingResult,
        state: ConversationState | None = None,
        college_brain: Any | None = None,
    ) -> ReasoningResult:
        stage = self._determine_stage(understanding, state)
        completeness = self._assess_completeness(understanding, state)
        eligibility = self._estimate_eligibility(understanding, state, college_brain)
        problem = self._identify_problem(understanding, completeness)
        unknowns = self._find_unknowns(understanding)
        risks = self._identify_risks(understanding, completeness)
        opportunities = self._identify_opportunities(understanding, state)
        knowledge = self._determine_knowledge_needed(understanding, stage)
        confidence = self._score_confidence(understanding, completeness)

        return ReasoningResult(
            student_stage=stage,
            profile_completeness=completeness,
            eligibility=eligibility,
            current_problem=problem,
            unknowns=unknowns,
            risks=risks,
            opportunities=opportunities,
            knowledge_needed=knowledge,
            confidence=confidence,
        )

    # ── Profile helpers ───────────────────────────────────────────────

    @staticmethod
    def _get_profile(understanding: UnderstandingResult):
        return getattr(understanding, "profile", None)

    @staticmethod
    def _has_field(understanding: UnderstandingResult, field: str) -> bool:
        profile = ReasoningEngine._get_profile(understanding)
        if profile is not None:
            return is_field_set(profile, field)
        return False

    @staticmethod
    def _get_field(understanding: UnderstandingResult, field: str) -> Any:
        profile = ReasoningEngine._get_profile(understanding)
        if profile is not None:
            from src.understanding.profile import get_field
            return get_field(profile, field)
        return None

    # ── Stage detection ───────────────────────────────────────────────

    def _determine_stage(
        self, understanding: UnderstandingResult, state: ConversationState | None
    ) -> str:
        profile = state.profile if state else {}
        history_count = len(state.history) // 2 if state else 0

        primary = str(understanding.intent.primary)
        if "decision" in primary or "choice" in primary:
            return "decision"
        if "apply" in primary or "form" in primary:
            return "application"

        has_rank = profile.get("rank") or self._has_field(understanding, "academic.rank")
        has_interest = profile.get("interest") or self._has_field(understanding, "career.interest")
        if history_count >= 4 and has_rank and has_interest:
            return "evaluation"

        known = set(profile.keys())
        if self._has_field(understanding, "academic.rank"):
            known.add("rank")
        if self._has_field(understanding, "academic.pcm_percentage"):
            known.add("pcm_percentage")
        if self._has_field(understanding, "career.interest"):
            known.add("interest")
        required = ["rank", "pcm_percentage", "interest"]
        if all(r in known for r in required):
            return "evaluation"

        if history_count >= 2:
            return "discovery"

        return "discovery"

    # ── Completeness ──────────────────────────────────────────────────

    def _assess_completeness(
        self, understanding: UnderstandingResult, state: ConversationState | None
    ) -> float:
        state_keys = set()
        if state:
            state_keys = set(k.lower().replace(" ", "_") for k in (state.profile or {}))

        filled = 0
        for f in _REQUIRED_PROFILE_FIELDS:
            if self._has_field(understanding, f):
                filled += 1
            else:
                short = f.split(".")[-1]
                if short in state_keys:
                    filled += 1

        if not _REQUIRED_PROFILE_FIELDS:
            return 1.0
        return min(1.0, filled / len(_REQUIRED_PROFILE_FIELDS))

    # ── Eligibility ───────────────────────────────────────────────────

    def _estimate_eligibility(
        self,
        understanding: UnderstandingResult,
        state: ConversationState | None,
        college_brain: Any | None,
    ) -> EligibilityEstimate:
        if college_brain is not None:
            return self._estimate_via_brain(understanding, state, college_brain)
        return self._estimate_fallback(understanding, state)

    def _estimate_via_brain(
        self,
        understanding: UnderstandingResult,
        state: ConversationState | None,
        college_brain: Any,
    ) -> EligibilityEstimate:
        rank = self._resolve_rank(understanding, state)
        pcm = self._resolve_pcm(understanding, state)
        category = self._resolve_category(understanding, state)
        try:
            pr = college_brain.estimate_eligibility(
                rank=rank, category=category, pcm=pcm,
            )
            return EligibilityEstimate(
                likely=pr.applicable,
                branches=pr.data.get("eligible_branches", []),
                confidence=pr.confidence,
                note=pr.details,
            )
        except Exception:
            logger.warning("CollegeBrain.estimate_eligibility failed", exc_info=True)
            return EligibilityEstimate(
                likely=False, branches=[], confidence=0.0,
                note="Eligibility check unavailable at this time",
            )

    def _resolve_rank(
        self, understanding: UnderstandingResult, state: ConversationState | None
    ) -> int | float | None:
        val = self._get_field(understanding, "academic.rank")
        if val is not None:
            return val
        if state:
            return state.profile.get("rank")
        return None

    def _resolve_pcm(
        self, understanding: UnderstandingResult, state: ConversationState | None
    ) -> float | None:
        val = self._get_field(understanding, "academic.pcm_percentage")
        if val is not None:
            return val
        if state:
            return state.profile.get("pcm_percentage")
        return None

    def _resolve_category(
        self, understanding: UnderstandingResult, state: ConversationState | None
    ) -> str:
        val = self._get_field(understanding, "personal.category")
        if val:
            return str(val)
        if state:
            return state.profile.get("category", "general")
        return "general"

    def _estimate_fallback(
        self,
        understanding: UnderstandingResult,
        state: ConversationState | None,
    ) -> EligibilityEstimate:
        rank = self._resolve_rank(understanding, state)
        pcm = self._resolve_pcm(understanding, state)

        if rank is None and pcm is None:
            return EligibilityEstimate(
                likely=False,
                branches=[],
                confidence=0.0,
                note="Insufficient data to estimate eligibility",
            )

        likely = False
        branches: list[str] = []
        note = ""
        confidence = 0.0

        if rank is not None and isinstance(rank, (int, float)):
            if rank <= 30000:
                likely = True
                branches = ["CSE", "AIML", "IT", "ECE"]
                note = "Strong rank — likely eligible for most branches"
                confidence = 0.85
            elif rank <= 60000:
                likely = True
                branches = ["IT", "ECE", "EE", "ME"]
                note = "Good rank — eligible for multiple branches"
                confidence = 0.7
            elif rank <= 120000:
                likely = True
                branches = ["ME", "CE", "EE"]
                note = "Moderate rank — eligible for core branches"
                confidence = 0.55
            else:
                branches = []
                note = "Rank may be above typical cutoff — verify with counseling data"
                confidence = 0.3

        if pcm is not None and isinstance(pcm, (int, float)):
            if pcm < 45:
                note += " | PCM below 45% — eligibility may be restricted"
                confidence *= 0.8

        return EligibilityEstimate(
            likely=likely,
            branches=branches,
            confidence=round(confidence, 2),
            note=note.strip(),
        )

    # ── Problem identification ────────────────────────────────────────

    def _identify_problem(
        self, understanding: UnderstandingResult, completeness: float
    ) -> str:
        intent = understanding.intent.primary
        dominant_signal, signal_score = understanding.signals.dominant

        if signal_score > 0.5 and dominant_signal == "anxiety":
            return "needs_reassurance"
        if signal_score > 0.5 and dominant_signal == "confusion":
            return "needs_clarification"
        if signal_score > 0.5 and dominant_signal == "frustration":
            return "needs_clarification"
        if intent == "fee":
            return "needs_fee_information"
        if intent == "admission":
            return "needs_admission_guidance"
        if intent == "placement":
            return "needs_placement_information"
        if intent == "hostel":
            return "needs_hostel_information"
        if intent == "scholarship":
            return "needs_scholarship_information"
        if intent == "cutoff":
            return "needs_cutoff_information"
        if intent == "department":
            return "needs_branch_guidance"
        if intent in ("transfer",):
            return "needs_transfer_information"
        if intent in ("sports", "sports_quota"):
            return "needs_sports_quota_information"
        if intent in ("nri", "nri_admission"):
            return "needs_nri_admission_information"
        if intent in ("management", "management_quota"):
            return "needs_management_quota_information"
        if intent in ("distance_ed", "distance_education"):
            return "needs_distance_education_information"
        if intent in ("grievance",):
            return "needs_grievance_resolution"
        if intent in ("lateral_entry",):
            return "needs_lateral_entry_information"
        if completeness < 0.3:
            return "needs_profile_initial"
        if completeness < 0.6:
            return "needs_profile_completion"
        return "needs_personalized_guidance"

    def _find_unknowns(
        self, understanding: UnderstandingResult
    ) -> list[str]:
        return list(understanding.missing_info.items)

    def _identify_risks(
        self, understanding: UnderstandingResult, completeness: float
    ) -> list[str]:
        risks: list[str] = []
        if understanding.signals.anxiety > 0.5:
            risks.append("student_shows_anxiety")
        if understanding.signals.confusion > 0.5:
            risks.append("student_shows_confusion")
        if understanding.signals.frustration > 0.5:
            risks.append("student_shows_frustration")
        if completeness < 0.3:
            risks.append("insufficient_profile_for_guidance")
        return risks

    def _identify_opportunities(
        self, understanding: UnderstandingResult, state: ConversationState | None
    ) -> list[str]:
        opportunities: list[str] = []
        rank = self._resolve_rank(understanding, state)
        if rank is not None and isinstance(rank, (int, float)) and rank <= 60000:
            opportunities.append("competitive_rank")
        if self._has_field(understanding, "career.interest"):
            opportunities.append("clear_interest_identified")
        if understanding.intent.confidence > 0.7:
            opportunities.append("clear_intent_detected")
        return opportunities

    def _determine_knowledge_needed(
        self, understanding: UnderstandingResult, stage: str
    ) -> list[str]:
        needed: list[str] = []
        intent = understanding.intent.primary
        if intent != "unknown":
            needed.append(f"{intent}_information")
        if stage in ("evaluation", "decision"):
            needed.append("comparison_data")
            needed.append("cutoff_data")
        if understanding.signals.financial_concern > 0.3:
            needed.append("scholarship_data")
        if not needed:
            needed.append("general_information")
        return needed

    def _score_confidence(
        self, understanding: UnderstandingResult, completeness: float
    ) -> float:
        score = understanding.confidence * 0.5
        score += completeness * 0.3
        has_rank = self._has_field(understanding, "academic.rank")
        if has_rank:
            score += 0.1
        if understanding.intent.confidence > 0.5:
            score += 0.1
        return min(1.0, score)
