from src.planner.models import Plan


def format_plan_as_response(plan: Plan) -> str:
    """Format a plan into a natural assistant response when LLM is unavailable."""
    if not plan or not plan.turns:
        return "I'm here to help with your admission questions. What can I assist with?"

    parts: list[str] = []
    for turn in plan.turns:
        parts.append(turn.content)
    return " ".join(parts)
