import logging

from src.brain.interfaces import BrainResponse
from src.engines.interfaces import DecisionOutput
from src.llm.interfaces import LLMAdapter
from src.planner.models import Plan

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an experienced, empathetic college admission counselor "
    "for a WBJEE-participating engineering college in West Bengal.\n\n"
    "Your role:\n"
    "- Guide students through admission, branch selection, placements, "
    "fees, hostel, and scholarships\n"
    "- Be warm, encouraging, and precise with numbers\n"
    "- Never guess rank cutoffs — use only provided data\n"
    "- Keep responses concise (2-4 sentences per turn)\n"
    "- If a student seems anxious, reassure them first\n"
    "- Always end with a clear next question or action item\n\n"
    "You are given a structured plan below. "
    "Follow it exactly — do not add information not present in the plan."
)


class ResponseComposer:
    VERSION = "v1"

    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    def compose(
        self,
        plan: Plan,
        decision: DecisionOutput | None = None,
        brain_response: BrainResponse | None = None,
        user_text: str = "",
        history: list[dict] | None = None,
    ) -> str:
        plan_block = self._format_plan(plan)
        brain_block = self._format_brain(brain_response)
        decision_block = self._format_decision(decision)
        history_block = self._format_history(history or [])

        prompt = (
            f"{_SYSTEM_PROMPT}\n\n"
            f"## Conversation History\n{history_block}\n"
            f"## Student's Last Message\n{user_text}\n\n"
            f"## Plan — Follow This Exactly\n{plan_block}\n"
            f"## Decision Context\n{decision_block}\n"
            f"## College Data\n{brain_block}\n\n"
            "Generate a natural, conversational assistant response following the plan above."
        )
        result = self._llm.generate(prompt)
        return result.text

    @staticmethod
    def _format_plan(plan: Plan) -> str:
        if not plan or not plan.turns:
            return "No plan available. Respond helpfully."
        action = plan.metadata.get('action', 'unknown')
        lines = [f"Action: {action} (confidence: {plan.confidence:.2f})"]
        if plan.metadata.get("rationale"):
            lines.append(f"Rationale: {plan.metadata['rationale']}")
        if plan.escalate:
            lines.append("[ESCALATION NEEDED]")
        for i, turn in enumerate(plan.turns, 1):
            extra = f" [expects: {turn.expected_input}]" if turn.expected_input else ""
            lines.append(f"  {i}. [{turn.action}] {turn.content}{extra}")
        return "\n".join(lines)

    @staticmethod
    def _format_brain(brain_response: BrainResponse | None) -> str:
        if brain_response is None:
            return "No college data available."
        blocks = []
        for policy_name in ("admission", "placement", "fees", "hostel", "scholarship"):
            policy = getattr(brain_response, policy_name, None)
            if policy and hasattr(policy, "data") and policy.data:
                eligible = policy.data.get("eligible_branches", [])
                why = getattr(policy, "why", [])
                why_lines = []
                for r in why:
                    status = 'met' if r.met else 'not met'
                    why_lines.append(f"    - {r.condition}: {status} — {r.detail}")
                detail = policy.details[:120] if hasattr(policy, 'details') else ''
                blocks.append(f"  {policy_name}: {detail}")
                if eligible:
                    blocks.append(f"    eligible branches: {', '.join(eligible)}")
                if why_lines:
                    blocks.append("    reasons:" + "\n".join(why_lines))
        return "\n".join(blocks) if blocks else "No college data available."

    @staticmethod
    def _format_decision(decision: DecisionOutput | None) -> str:
        if decision is None:
            return "No decision available."
        req_info = ', '.join(decision.required_info) if decision.required_info else 'none'
        return (
            f"Action: {decision.action}\n"
            f"Priority: {decision.priority}\n"
            f"Confidence: {decision.confidence:.2f}\n"
            f"Rationale: {decision.rationale}\n"
            f"Required info: {req_info}\n"
            f"Escalate: {decision.escalate}"
        )

    @staticmethod
    def _format_history(history: list[dict]) -> str:
        if not history:
            return "(no prior conversation)"
        lines = []
        for msg in history[-6:]:
            role = msg.get("role", "user")
            text = msg.get("content", "")
            lines.append(f"  {role}: {text[:200]}")
        return "\n".join(lines)
