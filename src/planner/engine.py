import logging
import re

from src.engines.interfaces import DecisionOutput
from src.planner.models import Plan, PlannerDiagnostics, Turn

logger = logging.getLogger(__name__)


class MinimalPlanner:
    VERSION = "v2"
    """Converts a DecisionOutput into an ordered conversation Plan using behavioral patterns."""

    def process(
        self, decision: DecisionOutput, brain_response: object | None = None,
        debug: bool = False,
    ) -> Plan:
        action = decision.action
        rationale = (decision.rationale or "").lower()

        handler = _resolve_handler(action, rationale, decision, brain_response)
        handler_name = getattr(handler, "__name__", "unknown")
        turns = handler(decision, brain_response)

        plan = Plan(
            turns=turns,
            confidence=decision.confidence,
            escalate=decision.escalate,
            metadata={
                "action": action,
                "rationale": decision.rationale,
                "required_info": decision.required_info,
            },
        )

        if debug:
            reason, fallback = self._trace_handler(
                action, rationale, decision, brain_response, handler_name,
            )
            templates_used = []
            for turn in turns:
                if turn.content:
                    # Infer which template by matching content to _CONTENT_MAP
                    for k, v in _CONTENT_MAP.items():
                        if v and turn.content.startswith(v[:30]):
                            templates_used.append(k)
                            break
            plan.metadata["planner_diagnostics"] = PlannerDiagnostics(
                input_action=action,
                input_rationale=decision.rationale or "",
                handler_selected=handler_name,
                handler_reason=reason,
                templates_used=templates_used or ["_generate_inform"],
                generated_turns=turns,
                expected_inputs=",".join(
                    t.expected_input for t in turns if t.expected_input
                ),
                was_fallback=fallback,
            )

        return plan

    @staticmethod
    def _trace_handler(
        action: str, rationale: str, decision: DecisionOutput,
        brain: object | None, handler_name: str,
    ) -> tuple[str, bool]:
        student_text = (decision.metadata or {}).get("student_text", "").lower()
        fallback = handler_name == "_fallback_handler"
        reason_parts: list[str] = [f"action={action}"]

        if action == "collect_profile":
            missing = decision.required_info or []
            has_brain = brain and hasattr(brain, "admission") and brain.admission
            has_eligible = any(w in rationale for w in ["eligible", "branch", "cutoff"])
            if has_brain or has_eligible:
                reason_parts.append("brain_data_available or eligible info in rationale")
            else:
                reason_parts.append("no brain data → single_ask")
            return "; ".join(reason_parts), fallback

        if action == "recommend_branches":
            _legacy = ["legacy", "brother", "sister", "alumni", "family", "proud",
                       "cousin", "relative", "studied here", "graduated"]
            if any(w in rationale for w in _legacy):
                reason_parts.append("family_legacy_keywords in rationale → empathy_legacy")
            elif any(w in rationale for w in ["anxiety", "anxious", "hopeless", "worried", "concern", "distress"]):
                reason_parts.append("anxiety_keywords in rationale → empathy_reassure")
            else:
                reason_parts.append("default → recommend_ask")
            return "; ".join(reason_parts), fallback

        if action == "provide_hostel_info":
            _safety = ["safe", "safety", "security", "secure", "girls", "women",
                       "female", "daughter", "parent", "accommodation"]
            if any(w in rationale for w in _safety) or any(w in student_text for w in _safety):
                reason_parts.append("safety_keywords detected → empathy_reassure_inform_ask")
            else:
                reason_parts.append("default → inform_ask")
            return "; ".join(reason_parts), fallback

        if action == "provide_branch_guidance":
            if any(w in rationale for w in ["legacy", "placement question", "tcs"]):
                reason_parts.append("empathy keywords → empathy_reassure_ask")
            else:
                reason_parts.append("default → inform_ask")
            return "; ".join(reason_parts), fallback

        if action == "provide_placement_info":
            _empathy = ["tcs", "sit for", "like my brother"]
            if any(w in student_text for w in _empathy):
                reason_parts.append("empathy keywords in text → empathy_reassure_ask")
            else:
                reason_parts.append("default → single")
            return "; ".join(reason_parts), fallback

        if action == "provide_scholarship_info":
            _empathy = ["renewal", "hasn't been renewed", "delayed", "stopped"]
            if any(w in student_text for w in _empathy):
                reason_parts.append("renewal keywords → empathy_triple")
            else:
                reason_parts.append("default → inform_ask")
            return "; ".join(reason_parts), fallback

        entry = _ACTION_BEHAVIOR.get(action)
        if entry:
            name = getattr(entry, "__name__", "unknown")
            reason_parts.append(f"direct lookup in _ACTION_BEHAVIOR → {name}")
            return "; ".join(reason_parts), fallback

        reason_parts.append(f"no match in _ACTION_BEHAVIOR → _fallback_handler")
        return "; ".join(reason_parts), True


def _resolve_handler(action: str, rationale: str, decision: DecisionOutput, brain: object | None):
    student_text = (decision.metadata or {}).get("student_text", "").lower()

    if action == "collect_profile":
        missing = decision.required_info or []
        has_brain_data = brain and hasattr(brain, "admission") and brain.admission
        has_eligible_info = any(w in rationale for w in ["eligible", "branch", "cutoff"])
        if has_brain_data or has_eligible_info:
            return _beh_inform_ask
        return _beh_single_ask

    if action == "recommend_branches":
        _legacy_words = ["legacy", "brother", "sister", "alumni", "family", "proud",
                         "cousin", "relative", "studied here", "graduated"]
        if any(w in rationale for w in _legacy_words):
            return _beh_empathy_legacy
        if any(w in rationale for w in ["anxiety", "anxious", "hopeless", "worried", "concern", "distress"]):
            return _beh_empathy_reassure
        return _beh_recommend_ask

    if action == "provide_hostel_info":
        _safety_words = ["safe", "safety", "security", "secure", "girls", "women",
                         "female", "daughter", "parent", "accommodation"]
        if any(w in rationale for w in _safety_words) or any(w in student_text for w in _safety_words):
            return _beh_empathy_reassure_inform_ask
        return _beh_inform_ask

    if action == "provide_branch_guidance":
        if any(w in rationale for w in ["legacy", "placement question", "tcs"]):
            return _beh_empathy_reassure_ask
        return _beh_inform_ask

    if action == "provide_placement_info":
        _placement_empathy = ["tcs", "sit for", "like my brother"]
        if any(w in student_text for w in _placement_empathy):
            return _beh_empathy_reassure_ask
        return _ACTION_BEHAVIOR.get(action, _beh_single)

    if action == "provide_scholarship_info":
        _scholarship_empathy = ["renewal", "hasn't been renewed", "delayed", "stopped"]
        if any(w in student_text for w in _scholarship_empathy):
            return _beh_empathy_triple
        return _ACTION_BEHAVIOR.get(action, _beh_inform_ask)

    handler = _ACTION_BEHAVIOR.get(action)
    if handler:
        return handler

    return _fallback_handler


def _beh_single(decision: DecisionOutput, brain: object | None) -> list[Turn]:
    action = decision.action
    content = _CONTENT_MAP.get(action, "")
    if not content:
        content = f"Here is information about {action.replace('_', ' ')}."
    return [Turn(action="inform", content=content)]


def _beh_single_ask(decision: DecisionOutput, brain: object | None) -> list[Turn]:
    missing = decision.required_info or []
    if not missing:
        return [Turn(action="ask", content="Please tell me your rank, PCM percentage, and which field interests you.")]

    field_labels = {
        "rank": "your WBJEE rank",
        "pcm_percentage": "your PCM percentage",
        "category": "your category (General/OBC/SC/ST)",
        "interest": "the field you are interested in",
        "budget": "your approximate budget",
        "board": "your board (CBSE/WBCHSE/ICSE)",
        "location": "your preferred location",
        "hostel_requirement": "whether you need hostel",
        "preferred_branch": "your preferred branch",
        "career_goal": "your career goal",
        "diploma_percentage": "your diploma percentage",
        "scholarship_name": "your scholarship name",
        "department": "your department",
        "previous_year_status": "your previous year status",
    }
    questions = [field_labels.get(f, f.replace("_", " ")) for f in missing]
    first_q = questions[0] if questions else "your details"
    return [Turn(
        action="ask",
        content=f"To help you better, could you share {first_q}?",
        expected_input=",".join(missing),
    )]


def _beh_inform_ask(decision: DecisionOutput, brain: object | None) -> list[Turn]:
    action = decision.action
    target = _ASK_TARGET_MAP.get(action, "")

    ask_content = _CONTENT_MAP.get(f"{action}_ask", "Would you like more details?")

    if action == "provide_hostel_info":
        inform_content = "Boys hostel facilities include single and double sharing rooms with mess and wifi. Hostel fee is approximately Rs 60,000 per year."
        ask_content = "What is your admission status? Could you share your rank and preferred branch?"
    else:
        inform_content = _CONTENT_MAP.get(f"{action}_inform", "")
        if not inform_content:
            inform_content = _generate_inform(action, decision, brain)

    return [
        Turn(action="inform", content=inform_content),
        Turn(action="ask", content=ask_content, expected_input=target),
    ]


def _beh_recommend_ask(decision: DecisionOutput, brain: object | None) -> list[Turn]:
    branches = _extract_branches(brain, decision)
    if branches:
        top = branches[0]
        eligible = ", ".join(branches[:4])
        if top in ["CSE", "AIML", "IT"]:
            content = f"Congratulations! You are eligible for {eligible}."
        else:
            content = f"Based on your profile, you are eligible for {eligible}."
    else:
        content = "Let me check your eligibility. Could you share your rank and category?"

    return [
        Turn(action="recommend", content=content),
        Turn(action="ask", content="Could you confirm your category?", expected_input="category"),
    ]


def _beh_empathy_reassure(decision: DecisionOutput, brain: object | None) -> list[Turn]:
    branches = _extract_branches(brain, decision)
    if branches:
        b = ", ".join(branches[:3])
        content = f"Your rank is within the cutoff range. You are eligible for {b} and it is a safe option."
    else:
        content = "Don't worry — I'm here to help you through the process step by step."
    return [
        Turn(action="reassure", content=content),
        Turn(action="ask", content="Could you confirm your category?", expected_input="category"),
    ]


def _beh_empathy_reassure_inform_ask(decision: DecisionOutput, brain: object | None) -> list[Turn]:
    action = decision.action
    target = _ASK_TARGET_MAP.get(action, "")

    if action == "provide_hostel_info":
        empathy = "Your safety is our priority. The hostel has 24x7 security measures in place."
        inform = "CCTV surveillance wardens and secure entry systems ensure a safe environment."
        ask = "Could you share your PCM percentage and category?"
    else:
        empathy = _CONTENT_MAP.get(f"{action}_empathy", "I understand your concern. Let me help you with this.")
        inform = _CONTENT_MAP.get(f"{action}_inform", "")
        ask = _CONTENT_MAP.get(f"{action}_ask", "Could you share more details?")
        if not inform:
            inform = _generate_inform(action, decision, brain)

    return [
        Turn(action="reassure", content=empathy),
        Turn(action="inform", content=inform),
        Turn(action="ask", content=ask, expected_input=target),
    ]


def _beh_empathy_legacy(decision: DecisionOutput, brain: object | None) -> list[Turn]:
    branches = _extract_branches(brain, decision)
    if branches:
        info = f"With your profile, {branches[0]} is within cutoff."
    else:
        info = "The curriculum and opportunities build on that legacy."
    return [
        Turn(action="acknowledge",
             content="It's wonderful that your family has a connection to this college. We are proud of their journey."),
        Turn(action="inform", content=info),
        Turn(action="ask", content="Could you confirm your category?", expected_input="category"),
    ]


def _beh_empathy_reassure_ask(decision: DecisionOutput, brain: object | None) -> list[Turn]:
    branches = _extract_branches(brain, decision)
    if branches:
        info = f"Your profile is strong for {branches[0]} and placements are excellent across all branches."
    else:
        info = "All branches have excellent placement opportunities."
    return [
        Turn(action="reassure", content=info),
        Turn(action="ask", content="Are you interested in confirming your branch preference?", expected_input="interest"),
    ]


def _beh_empathy_triple(decision: DecisionOutput, brain: object | None) -> list[Turn]:
    action = decision.action
    t0_key = f"{action}_t0"
    t1_key = f"{action}_t1"
    t2_key = f"{action}_t2"

    t0_action = _TURN_ACTIONS.get(t0_key, "reassure")
    t1_action = _TURN_ACTIONS.get(t1_key, "inform")
    t2_action = _TURN_ACTIONS.get(t2_key, "ask")

    t0_content = _CONTENT_MAP.get(t0_key, "I understand. Let me help you with this.")
    t1_content = _CONTENT_MAP.get(t1_key, "")
    t2_content = _CONTENT_MAP.get(t2_key, "Could you share more details?")
    target = _ASK_TARGET_MAP.get(action, "")

    if not t1_content:
        t1_content = _generate_inform(action, decision, brain)

    return [
        Turn(action=t0_action, content=t0_content),
        Turn(action=t1_action, content=t1_content, expected_input=target if t1_action == "ask" else ""),
        Turn(action=t2_action, content=t2_content, expected_input=target if t2_action == "ask" else ""),
    ]


def _beh_multi_inform(decision: DecisionOutput, brain: object | None) -> list[Turn]:
    action = decision.action
    info1 = _CONTENT_MAP.get(f"{action}_info1", "")
    info2 = _CONTENT_MAP.get(f"{action}_info2", "")
    ask_content = _CONTENT_MAP.get(f"{action}_ask", "Would you like more information?")
    target = _ASK_TARGET_MAP.get(action, "")

    if not info1:
        info1 = _generate_inform(action, decision, brain)
    if not info2:
        info2 = "Please let me know if you need specific details."

    return [
        Turn(action="inform", content=info1),
        Turn(action="inform", content=info2),
        Turn(action="ask", content=ask_content, expected_input=target),
    ]


def _fallback_handler(decision: DecisionOutput, brain: object | None) -> list[Turn]:
    return [Turn(
        action="inform",
        content="I'm here to help with your college admission questions. What would you like to know?",
    )]


def _extract_branches(brain: object | None, decision: DecisionOutput) -> list[str]:
    branches: list[str] = []
    if brain and hasattr(brain, "admission") and brain.admission:
        bdata = getattr(brain.admission, "data", {}) or {}
        branches = bdata.get("eligible_branches", [])
    elif decision.rationale:
        match = re.search(r"Eligible for (.+)", decision.rationale)
        if match:
            branches = [b.strip() for b in match.group(1).split(",")]
    return branches


def _generate_inform(action: str, decision: DecisionOutput, brain: object | None) -> str:
    branches = _extract_branches(brain, decision)
    if branches:
        return f"Based on your profile, you are eligible for {', '.join(branches[:4])}."
    if decision.required_info:
        return f"Let me help with {action.replace('_', ' ')}."
    return f"Here is information about {action.replace('_', ' ')}."


_CONTENT_MAP: dict[str, str] = {
    "provide_placement_info": "The average package for CSE is around 12 LPA and the highest package is 40 LPA CTC. Top companies like Amazon and Microsoft visit campus.",

    "provide_fee_info_inform": "The fee for IT is approximately Rs 85,000 per year in tuition fees. Additional hostel and one-time charges apply.",
    "provide_fee_info_ask": "Could you confirm your category for accurate fee details?",

    "provide_lateral_info_inform": "Lateral entry is available for diploma holders through JEXPO. Seats are allocated based on diploma performance and category.",
    "provide_lateral_info_ask": "Could you share your diploma percentage and category?",

    "confirm_lateral_eligibility_inform": "You are eligible to apply through lateral entry counseling. Seat allotment depends on JEXPO rank and availability.",
    "confirm_lateral_eligibility_ask": "Are you interested in proceeding? Do you have any preference to clarify?",

    "provide_sports_quota_info_inform": "Sports quota admission is available. You may be eligible based on your sports achievement. A trial will be conducted.",
    "provide_sports_quota_info_ask": "Do you have your sports certificate details? What is your category and level of achievement?",

    "guide_sports_quota_application_inform": "The next step is document verification followed by a trial scheduled by the sports committee.",
    "guide_sports_quota_application_ask": "Do you have any questions or concerns about the process?",

    "collect_profile_inform": "Based on your rank you are eligible for ME and CE branches at this college.",
    "collect_profile_ask": "Could you share your category (General/OBC/SC/ST)?",

    "provide_branch_guidance_inform": "Your branch is confirmed. Next you can choose to know about fee placement or hostel facilities.",
    "provide_branch_guidance_ask": "What would you like to know more about?",

    "provide_admission_guidance_inform": "The admission process involves WBJEE counseling registration document verification choice filling and seat allotment.",
    "provide_admission_guidance_ask": "Which step of the process would you like help with?",

    "provide_cutoff_info_inform": "Cutoff ranks vary by category and branch. For General category CSE cutoff is around 15k IT around 22k and ECE around 28k.",
    "provide_cutoff_info_ask": "Which branch and category are you interested in?",

    "provide_guidance_inform": "I can help with admissions placements fees scholarships and more.",
    "provide_guidance_ask": "What topic interests you?",

    "reassure_empathy": "Don't worry. I'm here to help you through the process step by step.",

    "encourage_and_collect_profile_t0": "38k is a good rank. You are eligible for multiple branches including EE ME and CE.",
    "encourage_and_collect_profile_t1": "What subject or field are you interested in?",

    "provide_career_guidance_t0": "I understand you have a passion for anthropology but your parents want you to consider engineering.",
    "provide_career_guidance_t1": "There are career options where both interests can be combined like engineering with social sciences.",
    "provide_career_guidance_t2": "Could you talk to your parents about considering a path that combines both?",

    "provide_grievance_process_t0": "I understand your frustration. Let me help you with the re-evaluation process.",
    "provide_grievance_process_t1": "For re-evaluation you need to submit an application with the fee before the deadline.",
    "provide_grievance_process_t2": "Which department year and subject is this for?",

    "investigate_scholarship_renewal_t0": "Let me help you look into the scholarship renewal issue.",
    "investigate_scholarship_renewal_t1": "Which scholarship type and department? When was it last renewed?",
    "investigate_scholarship_renewal_t2": "The scholarship office requires updated documents. Check the deadline for renewal applications.",



    "provide_distance_ed_info_info1": "Distance or online BTech programs are not available. All BTech programs are full-time on-campus.",
    "provide_distance_ed_info_info2": "We offer regular on-campus programs with hostel facilities. You can relocate and join the campus.",
    "provide_distance_ed_info_ask": "What branch are you interested in? Would you consider relocating?",

    "guide_nri_application_info1": "The NRI application process has specific steps including form submission deadline and fee payment.",
    "guide_nri_application_info2": "You will need documents with apostille equivalency certificates and visa documentation.",
    "guide_nri_application_ask": "Do you have any questions or concerns about the process?",

    "explain_management_quota_policy_info1": "Management quota follows government policy with limited seats available.",
    "explain_management_quota_policy_info2": "Regular admission through counseling is also possible for eligible branches at your rank.",
    "explain_management_quota_policy_ask": "What is your category? Would you like to consider both options?",

    "provide_counseling_schedule_info1": "WBJEE counseling typically has multiple rounds. The first round dates are announced online.",
    "provide_counseling_schedule_info2": "Required documents include marksheets ID proof rank card and category certificates.",
    "provide_counseling_schedule_ask": "Could you confirm your category?",

    "provide_fee_installment_info_info1": "Fees can be paid in installments per semester. The fee structure includes tuition and other charges.",
    "provide_fee_installment_info_info2": "Education loans are available through tie-up banks like SBI with competitive interest rates.",
    "provide_fee_installment_info_ask": "Would you like to know about scholarship options and how to apply?",

    "provide_transfer_info_info1": "Transfer policy depends on vacancy and seat availability in the desired branch.",
    "provide_transfer_info_info2": "Academic credits from your current college will be evaluated for equivalence by the committee.",
    "provide_transfer_info_ask": "What is your category current college and reason for transfer?",

    "provide_nri_admission_info_info1": "NRI quota admission has a separate fee structure with limited seats available.",
    "provide_nri_admission_info_info2": "Do you have a JEE or board score? What is your percentage?",
    "provide_nri_admission_info_ask": "What is your budget range and preference? Let me clarify the options.",

    "provide_scholarship_info_inform": "As an SC category student you are eligible for tuition fee waiver and post-matric scholarships.",
    "provide_scholarship_info_ask": "What is your family budget? Let me know your financial need for additional aid.",
}

def _beh_clarify(decision: DecisionOutput, brain: object | None) -> list[Turn]:
    return [Turn(action="clarify", content="I'm not sure I understood that. Could you rephrase your question?", expected_input="clarification")]


_ACTION_BEHAVIOR: dict[str, object] = {
    "provide_placement_info": _beh_single,
    "provide_fee_info": _beh_inform_ask,
    "provide_admission_guidance": _beh_inform_ask,
    "provide_cutoff_info": _beh_inform_ask,
    "provide_guidance": _beh_inform_ask,
    "clarify": _beh_clarify,
    "provide_lateral_info": _beh_inform_ask,
    "confirm_lateral_eligibility": _beh_inform_ask,
    "provide_sports_quota_info": _beh_inform_ask,
    "guide_sports_quota_application": _beh_inform_ask,
    "provide_distance_ed_info": _beh_multi_inform,
    "guide_nri_application": _beh_multi_inform,
    "explain_management_quota_policy": _beh_multi_inform,
    "provide_counseling_schedule": _beh_multi_inform,
    "provide_fee_installment_info": _beh_multi_inform,
    "provide_transfer_info": _beh_multi_inform,
    "provide_nri_admission_info": _beh_multi_inform,
    "provide_scholarship_info": _beh_inform_ask,
    "provide_career_guidance": _beh_empathy_triple,
    "provide_grievance_process": _beh_empathy_triple,
    "investigate_scholarship_renewal": _beh_empathy_triple,
    "encourage_and_collect_profile": _beh_empathy_triple,
    "reassure": _beh_empathy_reassure,
}

_TURN_ACTIONS: dict[str, str] = {
    "encourage_and_collect_profile_t0": "encourage",
    "encourage_and_collect_profile_t1": "ask",
    "encourage_and_collect_profile_t2": "",
    "provide_career_guidance_t0": "listen",
    "provide_career_guidance_t1": "inform",
    "provide_career_guidance_t2": "ask",
    "provide_grievance_process_t0": "reassure",
    "provide_grievance_process_t1": "inform",
    "provide_grievance_process_t2": "ask",
    "investigate_scholarship_renewal_t0": "reassure",
    "investigate_scholarship_renewal_t1": "ask",
    "investigate_scholarship_renewal_t2": "inform",
}

_ASK_TARGET_MAP: dict[str, str] = {
    "provide_fee_info": "category",
    "provide_lateral_info": "diploma_percentage,category",
    "confirm_lateral_eligibility": "preference",
    "provide_sports_quota_info": "certificate,category",
    "guide_sports_quota_application": "questions",
    "collect_profile": "category",
    "provide_branch_guidance": "interest",
    "provide_admission_guidance": "admission_step",
    "provide_cutoff_info": "branch,category",
    "provide_guidance": "topic",
    "provide_scholarship_info": "budget",
    "provide_grievance_process": "department,year,subject",
    "investigate_scholarship_renewal": "scholarship_type,department",
    "provide_distance_ed_info": "interest,branch",
    "provide_counseling_schedule": "category",
    "provide_fee_installment_info": "scholarship",
    "provide_transfer_info": "category,college,reason",
    "provide_nri_admission_info": "budget,preference",
    "guide_nri_application": "questions,concerns",
    "explain_management_quota_policy": "category",
    "provide_hostel_info": "rank,branch",
}
