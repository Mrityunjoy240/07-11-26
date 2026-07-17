from __future__ import annotations

from typing import Any

from src.conversation.state import ConversationState


def build_context(state: ConversationState, query: str) -> dict[str, Any]:
    context = {
        "student_profile": state.profile,
        "conversation_stage": state.stage.value,
        "language": state.language,
        "emotional_state": {
            "primary": state.emotional_state.primary,
            "confidence": state.emotional_state.confidence,
        },
        "domain_slots": {
            k: {"intent": v.intent, "department": v.department, "resolved": v.resolved}
            for k, v in state.domain_slots.items()
        },
        "visit_order": state.visit_order,
        "goals": state.goals,
        "recent_history": state.history[-6:] if state.history else [],
        "current_query": query,
    }
    return context


def format_context_for_prompt(context: dict[str, Any]) -> str:
    lines = ["### Conversation Context", ""]

    if context["student_profile"]:
        lines.append("**Student Profile:**")
        for k, v in context["student_profile"].items():
            lines.append(f"  - {k}: {v}")
        lines.append("")

    lines.append(f"**Stage:** {context['conversation_stage']}")
    lines.append(f"**Language:** {context['language']}")
    emo = context["emotional_state"]
    lines.append(f"**Emotion:** {emo['primary']} (confidence: {emo['confidence']})")
    lines.append("")

    if context["domain_slots"]:
        lines.append("**Resolved Domains:**")
        for domain, slot in context["domain_slots"].items():
            status = "resolved" if slot["resolved"] else "pending"
            lines.append(
                f"  - {domain}: intent={slot['intent']}, "
                f"dept={slot['department']}, {status}"
            )
        lines.append("")

    if context["recent_history"]:
        lines.append("**Recent History:**")
        for msg in context["recent_history"]:
            lines.append(f"  {msg['role']}: {msg['content'][:200]}")
        lines.append("")

    lines.append(f"**Current Query:** {context['current_query']}")
    lines.append("")

    return "\n".join(lines)
