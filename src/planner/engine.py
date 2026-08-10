import logging
import re

from src.engines.interfaces import DecisionOutput
from src.planner.models import Plan, PlannerDiagnostics, Turn

logger = logging.getLogger(__name__)


class MinimalPlanner:
    VERSION = "v2"
    """Converts a DecisionOutput into an ordered conversation Plan using behavioral patterns."""

    def __init__(self, knowledge: object | None = None) -> None:
        # Optional knowledge base (src.knowledge.KnowledgeBase). When present
        # and it returns a grounded answer for the student's question, the
        # informative turn of an info action is answered from the uploaded
        # college documents; otherwise the existing deterministic content is
        # used untouched (this is also exactly what happens with knowledge=None).
        self.knowledge = knowledge

    def process(
        self, decision: DecisionOutput, brain_response: object | None = None,
        debug: bool = False, knowledge: object | None = None,
    ) -> Plan:
        action = decision.action
        rationale = (decision.rationale or "").lower()

        handler = _resolve_handler(action, rationale, decision, brain_response)
        handler_name = getattr(handler, "__name__", "unknown")
        kb_answer = _kb_answer_for(
            decision, knowledge if knowledge is not None else self.knowledge,
        )
        turns = handler(decision, brain_response, kb_answer)

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
            if any(m in missing for m in ("academic.rank", "rank")):
                reason_parts.append("rank missing → single_ask")
            else:
                reason_parts.append("rank known → inform_ask")
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
        # Ask for the first genuinely missing core datum (rank) before giving
        # partial eligibility info. Rank is the blocking field for admission;
        # once it is known the counselor can inform + collect the rest.
        needs_rank = any(m in missing for m in ("academic.rank", "rank"))
        if needs_rank:
            return _beh_single_ask
        return _beh_inform_ask

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


def _beh_single(decision: DecisionOutput, brain: object | None, kb_answer: str | None = None) -> list[Turn]:
    action = decision.action
    content = kb_answer or _CONTENT_MAP.get(action, "")
    if not content:
        content = f"Here is information about {action.replace('_', ' ')}."
    return [Turn(action="inform", content=content)]


def _beh_single_ask(decision: DecisionOutput, brain: object | None, kb_answer: str | None = None) -> list[Turn]:
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
        "academic.rank": "your WBJEE rank",
        "academic.pcm_percentage": "your PCM percentage",
        "personal.category": "your category (General/OBC/SC/ST)",
        "career.interest": "the field you are interested in",
        "personal.budget": "your approximate budget",
        "academic.board": "your board (CBSE/WBCHSE/ICSE)",
        "personal.location": "your preferred location",
        "personal.hostel_required": "whether you need hostel",
        "career.preferred_branch": "your preferred branch",
        "career.career_goal": "your career goal",
        "academic.diploma_percentage": "your diploma percentage",
        "personal.scholarship_name": "your scholarship name",
        "academic.qualification": "your qualification",
    }
    questions = [field_labels.get(f, f.replace("_", " ")) for f in missing]
    first_q = questions[0] if questions else "your details"
    return [Turn(
        action="ask",
        content=f"To help you better, could you share {first_q}?",
        expected_input=",".join(missing),
    )]


def _beh_inform_ask(decision: DecisionOutput, brain: object | None, kb_answer: str | None = None) -> list[Turn]:
    action = decision.action
    target = _ASK_TARGET_MAP.get(action, "")
    student_text = (decision.metadata or {}).get("student_text", "").lower()

    ask_content = _CONTENT_MAP.get(f"{action}_ask", "Would you like more details?")

    if action == "provide_hostel_info":
        inform_content = "Boys hostel facilities include single and double sharing rooms with mess and wifi. Hostel fee is approximately Rs 60,000 per year."
        ask_content = "What is your admission status? Could you share your rank and preferred branch?"
    elif action == "provide_fee_info":
        branch = _detect_branch(student_text)
        tuition = _brain_fee_tuition(brain)
        if tuition is not None:
            inform_content = (
                f"The annual tuition fee for {branch or 'all B.Tech programs'} is "
                f"approximately Rs {tuition:,} per year. "
                "Additional hostel and one-time charges apply."
            )
        else:
            inform_content = _CONTENT_MAP.get("provide_fee_info_inform", "")
    elif action == "provide_program_info":
        if any(w in student_text for w in _FACULTY_WORDS):
            inform_content = _CONTENT_MAP.get("provide_program_info_faculty_inform", "")
            ask_content = _CONTENT_MAP.get("provide_program_info_faculty_ask", "Which branch's faculty would you like details about?")
        elif any(w in student_text for w in _TIMING_WORDS):
            inform_content = _CONTENT_MAP.get("provide_program_info_timings_inform", "")
            ask_content = _CONTENT_MAP.get("provide_program_info_timings_ask", "Would you like more details?")
        else:
            inform_content = _CONTENT_MAP.get("provide_program_info_inform", "")
    else:
        inform_content = _CONTENT_MAP.get(f"{action}_inform", "")
        if not inform_content:
            inform_content = _generate_inform(action, decision, brain)

    if kb_answer:
        # Grounded answer from the knowledge base replaces the template text,
        # while the natural follow-up question is preserved.
        inform_content = kb_answer

    return [
        Turn(action="inform", content=inform_content),
        Turn(action="ask", content=ask_content, expected_input=target),
    ]


def _beh_program_inform_ask(decision: DecisionOutput, brain: object | None, kb_answer: str | None = None) -> list[Turn]:
    """Program-curriculum questions: share what the program covers, then check
    whether the student is exploring admission for that program."""
    student_text = (decision.metadata or {}).get("student_text", "").lower()
    branch = _detect_branch(student_text)

    if branch:
        ask_content = f"Are you looking for admission to {branch}?"
    else:
        ask_content = _CONTENT_MAP.get(
            "provide_program_curriculum_ask",
            "Are you looking for admission to any of our programs?",
        )

    if kb_answer:
        inform_content = kb_answer
    elif branch:
        inform_content = _PROGRAM_CURRICULUM.get(
            branch,
            _CONTENT_MAP.get("provide_program_curriculum_inform", ""),
        )
    else:
        inform_content = _CONTENT_MAP.get("provide_program_curriculum_inform", "")

    return [
        Turn(action="inform", content=inform_content),
        Turn(action="ask", content=ask_content, expected_input="admission_intent"),
    ]


def _beh_recommend_ask(decision: DecisionOutput, brain: object | None, kb_answer: str | None = None) -> list[Turn]:
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


def _beh_empathy_reassure(decision: DecisionOutput, brain: object | None, kb_answer: str | None = None) -> list[Turn]:
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


def _beh_empathy_reassure_inform_ask(decision: DecisionOutput, brain: object | None, kb_answer: str | None = None) -> list[Turn]:
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

    if kb_answer:
        inform = kb_answer

    return [
        Turn(action="reassure", content=empathy),
        Turn(action="inform", content=inform),
        Turn(action="ask", content=ask, expected_input=target),
    ]


def _beh_empathy_legacy(decision: DecisionOutput, brain: object | None, kb_answer: str | None = None) -> list[Turn]:
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


def _beh_empathy_reassure_ask(decision: DecisionOutput, brain: object | None, kb_answer: str | None = None) -> list[Turn]:
    branches = _extract_branches(brain, decision)
    if branches:
        info = f"Your profile is strong for {branches[0]} and placements are excellent across all branches."
    else:
        info = "All branches have excellent placement opportunities."
    return [
        Turn(action="reassure", content=info),
        Turn(action="ask", content="Are you interested in confirming your branch preference?", expected_input="interest"),
    ]


def _beh_empathy_triple(decision: DecisionOutput, brain: object | None, kb_answer: str | None = None) -> list[Turn]:
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
    if kb_answer and t1_action == "inform":
        t1_content = kb_answer

    return [
        Turn(action=t0_action, content=t0_content),
        Turn(action=t1_action, content=t1_content, expected_input=target if t1_action == "ask" else ""),
        Turn(action=t2_action, content=t2_content, expected_input=target if t2_action == "ask" else ""),
    ]


def _beh_multi_inform(decision: DecisionOutput, brain: object | None, kb_answer: str | None = None) -> list[Turn]:
    action = decision.action
    info1 = _CONTENT_MAP.get(f"{action}_info1", "")
    info2 = _CONTENT_MAP.get(f"{action}_info2", "")
    ask_content = _CONTENT_MAP.get(f"{action}_ask", "Would you like more information?")
    target = _ASK_TARGET_MAP.get(action, "")

    if kb_answer:
        return [
            Turn(action="inform", content=kb_answer),
            Turn(action="ask", content=ask_content, expected_input=target),
        ]

    if not info1:
        info1 = _generate_inform(action, decision, brain)
    if not info2:
        info2 = "Please let me know if you need specific details."

    return [
        Turn(action="inform", content=info1),
        Turn(action="inform", content=info2),
        Turn(action="ask", content=ask_content, expected_input=target),
    ]


def _fallback_handler(decision: DecisionOutput, brain: object | None, kb_answer: str | None = None) -> list[Turn]:
    return [Turn(
        action="inform",
        content="I'm here to help with your college admission questions. What would you like to know?",
    )]


_FACULTY_WORDS = ["faculty", "teacher", "professor", "lecturer", "lab instructor", "staff member"]

_TIMING_WORDS = ["timing", "class hours", "college hours", "opening time", "closing time"]

_BRANCH_KEYWORDS: list[tuple[list[str], str]] = [
    (["cse", "computer science", "computer science engineering", "computer engineering", "computers"], "CSE"),
    (["ece", "electronics and communication", "electronics & communication", "electronics"], "ECE"),
    (["it", "information technology", "information tech"], "IT"),
    (["ee", "electrical engineering", "electrical"], "EE"),
    (["mechanical engineering", "mechanical", "machanical"], "ME"),
    (["civil engineering", "civil"], "CE"),
    (["aiml", "ai ml", "ai and ml", "artificial intelligence and machine learning", "artificial intelligence"], "AIML"),
    (["data science", "data analytics"], "Data Science"),
    (["biotechnology", "biotech", "bio technology"], "Biotechnology"),
    (["cyber security", "cybersecurity", "cyber"], "Cyber Security"),
    (["iot", "internet of things"], "IoT"),
    (["robotics", "robot"], "Robotics"),
]

_PROGRAM_CURRICULUM: dict[str, str] = {
    "CSE": "CSE covers programming, data structures, algorithms, databases, operating systems, computer networks and software engineering.",
    "ECE": "ECE covers electronic devices and circuits, digital electronics, signals and systems, communication systems, microprocessors and embedded systems.",
    "IT": "IT covers programming, data structures, web technologies, computer networks, databases and software project management.",
    "EE": "EE covers electric circuits, electrical machines, power systems, control systems and electrical measurements.",
    "ME": "ME covers engineering mechanics, thermodynamics, machine design, manufacturing processes and CAD.",
    "CE": "CE covers structural analysis, geotechnical engineering, transportation engineering and construction management.",
    "AIML": "AIML covers machine learning, deep learning, data analytics, neural networks and AI applications.",
    "Data Science": "Data Science covers statistics, data analytics, machine learning, big data and data visualization.",
    "Biotechnology": "Biotechnology covers molecular biology, biochemistry, genetic engineering and bioprocess technology.",
    "Cyber Security": "Cyber Security covers network security, cryptography, ethical hacking and security operations.",
    "IoT": "IoT covers sensors and actuators, embedded systems, wireless communication and IoT application development.",
    "Robotics": "Robotics covers mechatronics, control systems, sensors, kinematics and robot programming.",
}


def _detect_branch(text: str) -> str | None:
    for keywords, canonical in _BRANCH_KEYWORDS:
        for kw in keywords:
            if len(kw) <= 4:
                if re.search(rf"\b{re.escape(kw)}\b", text):
                    return canonical
            elif kw in text:
                return canonical
    return None


def _brain_fee_tuition(brain: object | None) -> int | None:
    if brain is None:
        return None
    fees = getattr(brain, "fees", None)
    data = getattr(fees, "data", None) or {}
    tuition = data.get("tuition_per_year")
    if isinstance(tuition, (int, float)) and tuition > 0:
        return int(tuition)
    return None


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


def _kb_answer_for(decision: DecisionOutput, knowledge: object | None) -> str | None:
    """Return a grounded knowledge-base answer for the student's question.

    Returns None when no KB is wired, the query is empty, retrieval finds
    nothing relevant, or anything raises — in every one of those cases the
    planner keeps its existing deterministic content, so the no-KB path is
    byte-for-byte identical to today.
    """
    if knowledge is None:
        return None
    query = (decision.metadata or {}).get("student_text", "").strip()
    if not query:
        return None
    try:
        answer = knowledge.answer(query)
    except Exception:
        return None
    return answer.text if answer is not None else None


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

    "explain_policy_info1": "Management quota follows government policy with limited seats available.",
    "explain_policy_info2": "Regular admission through counseling is also possible for eligible branches at your rank.",
    "explain_policy_ask": "What is your category? Would you like to consider both options?",

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

    "provide_program_info_inform": "Our college offers B.Tech programs through regular admission counseling. Program details depend on the branch and your profile.",
    "provide_program_info_ask": "Which program or branch would you like details about?",

    "provide_program_info_faculty_inform": "The college has qualified and experienced faculty in every department. Faculty profiles including qualifications and research areas can be shared for any branch.",
    "provide_program_info_faculty_ask": "Which branch's faculty would you like details about?",

    "provide_program_info_timings_inform": "College classes typically run on weekdays and the academic office is open during working hours for admission queries.",
    "provide_program_info_timings_ask": "Would you like help with admissions as well?",

    "provide_program_curriculum_inform": "Our B.Tech programs follow the standard engineering curriculum with core subjects in the first two years and branch-specific subjects later.",
    "provide_program_curriculum_ask": "Are you looking for admission to any of our programs?",

    "provide_scholarship_info_inform": "As an SC category student you are eligible for tuition fee waiver and post-matric scholarships.",
    "provide_scholarship_info_ask": "What is your family budget? Let me know your financial need for additional aid.",
}

def _beh_clarify(decision: DecisionOutput, brain: object | None, kb_answer: str | None = None) -> list[Turn]:
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
    "explain_policy": _beh_multi_inform,
    "provide_counseling_schedule": _beh_multi_inform,
    "provide_fee_installment_info": _beh_multi_inform,
    "provide_transfer_info": _beh_multi_inform,
    "provide_nri_admission_info": _beh_multi_inform,
    "provide_scholarship_info": _beh_inform_ask,
    "provide_program_info": _beh_inform_ask,
    "provide_program_curriculum": _beh_program_inform_ask,
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
    "provide_program_info": "branch",
    "provide_program_curriculum": "admission_intent",
    "provide_grievance_process": "department,year,subject",
    "investigate_scholarship_renewal": "scholarship_type,department",
    "provide_distance_ed_info": "interest,branch",
    "provide_counseling_schedule": "category",
    "provide_fee_installment_info": "scholarship",
    "provide_transfer_info": "category,college,reason",
    "provide_nri_admission_info": "budget,preference",
    "explain_policy": "category",
    "provide_hostel_info": "rank,branch",
}
