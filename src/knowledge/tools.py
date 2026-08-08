from __future__ import annotations

from src.fabric.tools import ToolSpec
from src.knowledge.service import CollegeKnowledgeService

_FEE_PARAMETERS = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "description": "Category: general, obc, sc, st"},
        "interest": {"type": "string", "description": "Preferred branch/interest"},
    },
}

_ELIGIBILITY_PARAMETERS = {
    "type": "object",
    "properties": {
        "rank": {"type": "integer", "description": "Entrance exam rank"},
        "pcm_percentage": {"type": "number", "description": "PCM percentage in qualifying exam"},
        "category": {"type": "string", "description": "Category: general, obc, sc, st"},
        "interest": {"type": "string", "description": "Preferred branch/interest"},
    },
    "required": ["rank"],
}

_SCHOLARSHIP_PARAMETERS = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "description": "Category: general, obc, sc, st"},
        "board": {"type": "string", "description": "Board name"},
        "pcm_percentage": {"type": "number", "description": "PCM percentage"},
    },
}


def build_knowledge_tools(knowledge: CollegeKnowledgeService | None = None) -> list[ToolSpec]:
    svc = knowledge or CollegeKnowledgeService()

    def fee_handler(category: str = "general", interest: str = "") -> str:
        return svc.query("fee", category=category, interest=interest).content

    def eligibility_handler(
        rank: int, pcm_percentage: float | None = None,
        category: str = "general", interest: str = "",
    ) -> str:
        return svc.query(
            "eligibility",
            rank=rank, pcm_percentage=pcm_percentage,
            category=category, interest=interest,
        ).content

    def scholarship_handler(
        category: str = "general", board: str = "", pcm_percentage: float | None = None,
    ) -> str:
        return svc.query(
            "scholarship",
            category=category, board=board, pcm_percentage=pcm_percentage,
        ).content

    return [
        ToolSpec(
            name="calculate_fee",
            description="Compute annual fee breakdown for a category",
            parameters=_FEE_PARAMETERS,
            handler=fee_handler,
            deterministic=True,
        ),
        ToolSpec(
            name="check_eligibility",
            description="Check branch eligibility from entrance rank, category and PCM",
            parameters=_ELIGIBILITY_PARAMETERS,
            handler=eligibility_handler,
            deterministic=True,
        ),
        ToolSpec(
            name="get_scholarships",
            description="List scholarships applicable to a student profile",
            parameters=_SCHOLARSHIP_PARAMETERS,
            handler=scholarship_handler,
            deterministic=True,
        ),
    ]
