import logging

from src.engines.interfaces import DecisionInput, DecisionOutput
from src.registry import CapabilityRegistry

logger = logging.getLogger(__name__)

# ── Rule tables ─────────────────────────────────────────────────────────────

_DECISION_RULES: dict[str, tuple[str, str, str]] = {
    "needs_profile_initial": ("collect_profile", "high",
                              "Student profile incomplete — collect rank, PCM, interest"),
    "needs_profile_completion": ("collect_profile", "normal",
                                 "Partial profile — collect remaining fields"),
    "needs_fee_information": ("provide_fee_info", "normal",
                              "Student asking about fees"),
    "needs_admission_guidance": ("provide_admission_guidance", "high",
                                 "Student asking about admission process"),
    "needs_placement_information": ("provide_placement_info", "normal",
                                    "Student asking about placements"),
    "needs_hostel_information": ("provide_hostel_info", "low",
                                 "Student asking about hostel"),
    "needs_scholarship_information": ("provide_scholarship_info", "normal",
                                      "Student asking about scholarships"),
    "needs_cutoff_information": ("provide_cutoff_info", "normal",
                                 "Student asking about cutoffs"),
    "needs_branch_guidance": ("provide_branch_guidance", "normal",
                              "Student asking about branch selection"),
    "needs_reassurance": ("reassure", "high",
                          "Student showing anxiety — need reassurance"),
    "needs_clarification": ("clarify", "normal",
                            "Student confused — clarify question"),
    "needs_personalized_guidance": ("provide_guidance", "normal",
                                    "General personalized guidance"),
}

# knowledge_needed hint → action for when reasoning outputs a generic problem
# but the pipeline's knowledge-need signal is more specific.
_KNOWLEDGE_TO_ACTION: dict[str, str] = {
    "distance_education_information": "provide_distance_ed_info",
    "nri_admission_information": "provide_nri_admission_info",
    "management_quota_information": "explain_management_quota_policy",
    "grievance_information": "provide_grievance_process",
    "transfer_information": "provide_transfer_info",
    "sports_quota_information": "provide_sports_quota_info",
    "lateral_entry_information": "provide_lateral_entry_info",
    "counseling_information": "provide_counseling_schedule",
    "scholarship_information": "provide_scholarship_info",
}

# Generic fallback actions that should be overridden by knowledge_needed.
_GENERIC_ACTIONS = {"collect_profile", "clarify", "provide_guidance"}

# Actions that are gateway/generic enough to be overridden by recommend_branches
# when the brain has eligibility data.
_GATEWAY_ACTIONS = {"collect_profile", "clarify", "provide_guidance",
                     "provide_admission_guidance", "provide_branch_guidance"}


class DecisionEngine:
    VERSION = "v2"

    def process(self, input: DecisionInput) -> DecisionOutput:
        reasoning = input.reasoning
        brain = input.brain_response
        registry: CapabilityRegistry | None = input.capabilities

        problem = getattr(reasoning, "current_problem", "")
        confidence = getattr(reasoning, "confidence", 0.0)
        stage = getattr(reasoning, "student_stage", "discovery")
        risks = getattr(reasoning, "risks", [])
        completeness = getattr(reasoning, "profile_completeness", 0.0)
        knowledge_needed = getattr(reasoning, "knowledge_needed", None) or []

        # ── Step 1: Resolve from current_problem ────────────────────
        rule = _DECISION_RULES.get(problem)
        if rule:
            action, priority, rationale = rule
        else:
            action = "clarify"
            priority = "normal"
            rationale = f"Unknown problem '{problem}' — request clarification"

        # ── Step 2: Refine generic fallbacks via knowledge_needed ───
        # When reasoning says "collect profile" but actually knows the
        # student is asking about transfer / distance-ed / NRI / etc.
        if action in _GENERIC_ACTIONS:
            for need in knowledge_needed:
                mapped = _KNOWLEDGE_TO_ACTION.get(need)
                if mapped:
                    action = mapped
                    priority = "normal"
                    rationale = f"Student needs {need.replace('_', ' ')}"
                    break

        # ── Step 2b: Student text-based intent routing ────────────
        # When the student's text reveals specific needs (career guidance,
        # legacy context, low confidence, counseling questions) that the
        # reasoning engine didn't fully capture.
        _student_text = (input.metadata or {}).get("student_text", "").lower()
        if action in _GENERIC_ACTIONS | {"provide_admission_guidance", "provide_branch_guidance"}:
            if any(w in _student_text for w in ["not engineering", "anthropology", "economics",
                                                  "psychology", "medicine", "design",
                                                  "actually want"]):
                action = "provide_career_guidance"
                priority = "normal"
                rationale = "Student interested in non-engineering career"
            elif any(w in _student_text for w in ["don't think", "not sure", "not confident",
                                                   "doubt", "hopeless", "not get"]):
                action = "encourage_and_collect_profile"
                priority = "high"
                rationale = "Student showing low confidence — encourage first"
            elif any(w in _student_text for w in ["brother", "sister", "cousin", "relative",
                                                   "alumni", "family member", "family",
                                                   "studied here", "graduated"]):
                action = "recommend_branches"
                priority = "high"
                rationale = "Student has family legacy at this college"
            elif any(w in _student_text for w in ["when is", "counseling", "documents do i need"]):
                action = "provide_counseling_schedule"
                priority = "normal"
                rationale = "Student asking about counseling schedule and documents"

        # ── Step 3: Gateway → collect_profile when very incomplete ──
        # If reasoning chose admission/branch guidance but the profile
        # is too sparse, collect more info first.
        if action in ("provide_admission_guidance", "provide_branch_guidance") and completeness < 0.5:
            action = "collect_profile"
            priority = "high"
            rationale = "Profile too incomplete for guidance — collect missing fields first"

        # ── Step 4: Brain override (only for gateway actions) ───────
        # Skip brain override when student needs empathy, has special context,
        # or is asking for specific information — recommend can come next turn.
        has_eligible = (brain and hasattr(brain, "admission") and brain.admission
                        and brain.admission.applicable
                        and brain.admission.data.get("eligible_branches"))
        _has_anxiety = "student_shows_anxiety" in risks or "student_shows_frustration" in risks
        _special_knowledge = {
            "distance_education_information", "nri_admission_information",
            "management_quota_information", "grievance_information",
            "transfer_information", "sports_quota_information",
        }
        _has_special_context = bool(set(knowledge_needed) & _special_knowledge)
        _is_info_request = problem in (
            "needs_fee_information", "needs_placement_information",
            "needs_hostel_information", "needs_scholarship_information",
            "needs_cutoff_information",
        )
        # Skip brain override when student has empathy needs, special context,
        # or specific info requests — recommend can come next turn.
        _student_text = (input.metadata or {}).get("student_text", "").lower()
        _has_empathy_context = any(w in _student_text for w in [
            "brother", "sister", "cousin", "relative", "alumni", "family", "proud",
            "studied here", "graduated",
            "anthropology", "economics", "psychology", "medicine", "design",
            "not engineering", "not interested",
            "don't think", "not sure", "not confident", "doubt", "hopeless",
            "counseling", "documents", "when is", "paperwork", "registration",
        ])
        if (has_eligible and action in _GATEWAY_ACTIONS
                and not _has_anxiety and not _has_special_context
                and not _is_info_request and not _has_empathy_context
                and completeness >= 0.3):
            action = "recommend_branches"
            branches_list = brain.admission.data["eligible_branches"][:3]
            rationale = f"Eligible for {', '.join(branches_list)}"
            priority = "high"

        # ── Remaining fields ────────────────────────────────────────
        escalate = _has_anxiety

        # Enrich rationale with risk/context signals so Planner empathy
        # routing can detect them (e.g., safety, legacy, anxiety keywords).
        if risks:
            risk_tags = " ".join(r.replace("_", " ") for r in risks)
            rationale = f"{rationale} {risk_tags}" if rationale else risk_tags
        if knowledge_needed:
            ctx_tags = " ".join(k.replace("_", " ") for k in knowledge_needed)
            rationale = f"{rationale} {ctx_tags}" if rationale else ctx_tags
        if stage == "decision":
            priority = "high"

        required = list(getattr(reasoning, "unknowns", []))

        if not required and registry:
            matches = registry.find(problem)
            if matches:
                required = list(matches[0].metadata.get("required_info", []))

        return DecisionOutput(
            action=action,
            priority=priority,
            confidence=confidence,
            rationale=rationale,
            required_info=required,
            escalate=escalate,
            metadata=input.metadata,
        )
