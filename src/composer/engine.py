import logging
import time
import re
from typing import Any

from src.brain.interfaces import BrainResponse
from src.composer.models import ComposerDiagnostics, ComposerResult
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
    VERSION = "v2"

    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    def compose(
        self,
        plan: Plan,
        decision: DecisionOutput | None = None,
        brain_response: BrainResponse | None = None,
        user_text: str = "",
        history: list[dict] | None = None,
        debug: bool = False,
    ) -> ComposerResult:
        t0 = time.perf_counter()
        plan_block = self._format_plan(plan)
        brain_block = self._format_brain(brain_response)
        decision_block = self._format_decision(decision)
        history_list = history or []
        history_block = self._format_history(history_list)

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
        latency_ms = (time.perf_counter() - t0) * 1000

        output = result.text
        diag: ComposerDiagnostics | None = None

        if debug:
            tokens = result.usage or {}
            followed_plan, violations = self._check_plan_following(
                output, plan, decision, brain_response,
            )
            hallucination_risk = self._assess_hallucination_risk(
                output, plan, brain_response,
            )
            diag = ComposerDiagnostics(
                system_prompt=_SYSTEM_PROMPT,
                history_used=history_list[-6:] if history_list else [],
                user_message=user_text,
                serialized_plan=plan_block,
                decision_context=decision_block,
                brain_context=brain_block,
                final_prompt=prompt,
                prompt_tokens=tokens.get("prompt_tokens", 0),
                completion_tokens=tokens.get("completion_tokens", 0),
                total_tokens=tokens.get("total_tokens", 0),
                latency_ms=round(latency_ms, 1),
                model=getattr(self._llm, "model", "unknown"),
                temperature=0.3,
                finish_reason=result.finish_reason,
                raw_llm_response=result.text,
                parsed_response=output,
                final_output=output,
                followed_plan=followed_plan,
                violations=violations,
                hallucination_risk=hallucination_risk,
            )

        return ComposerResult(text=output, diagnostics=diag)

    @staticmethod
    def _check_plan_following(
        output: str, plan: Plan, decision: DecisionOutput | None,
        brain_response: BrainResponse | None,
    ) -> tuple[bool, list[str]]:
        violations: list[str] = []
        output_lower = output.lower()

        # Check: response should address at least one turn from the plan
        turn_actions_found = set()
        for turn in plan.turns:
            if turn.action == "ask":
                # Response should contain a question
                if "?" not in output:
                    violations.append("plan expects ask turn but response has no question")
            if turn.action in ("reassure", "encourage", "acknowledge"):
                turn_actions_found.add(turn.action)
            if turn.content:
                # Key content should appear in response
                key_phrases = [p.strip().lower() for p in turn.content.split() if len(p.strip()) > 4]
                if key_phrases and not any(p in output_lower for p in key_phrases[:3]):
                    violations.append(f"plan turn '{turn.action}' content not reflected in response")

        # Check: no specific numbers not in brain data
        if brain_response:
            brain_text = str(brain_response).lower()
            numbers_found = re.findall(r'\b(\d{3,5})\b', output)
            for num in numbers_found:
                if num not in brain_text and int(num) not in range(1, 100):
                    violations.append(f"number {num} in response not found in brain data")

        # Check: no unauthorized actions
        plan_actions = {t.action for t in plan.turns}
        if "recommend" in plan_actions and "recommend" not in output_lower and "eligible" not in output_lower:
            violations.append("plan expects recommend but response lacks recommendation")

        return len(violations) < 2, violations  # allow minor violations

    @staticmethod
    def _assess_hallucination_risk(
        output: str, plan: Plan, brain_response: BrainResponse | None,
    ) -> str:
        """Heuristic: low/medium/high based on unsupported content."""
        output_lower = output.lower()
        risks = 0

        # Check for specific cutoff numbers without brain data
        if not brain_response:
            if re.search(r'\b\d+\s*(?:cutoff|rank|percentile)\b', output_lower):
                risks += 2

        # Check for unauthorized specifics
        specific_patterns = [
            r'\b(?:exact|specific|precise)\s+(?:fee|cost|amount)\b',
            r'\b(?:guarantee|promise|100%|definitely)\b',
        ]
        for pat in specific_patterns:
            if re.search(pat, output_lower):
                risks += 1

        if risks >= 2:
            return "high"
        if risks >= 1:
            return "medium"
        return "low"

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
