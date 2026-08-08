from __future__ import annotations

from typing import Any

from src.brain.admission import AdmissionPolicy
from src.brain.fees import FeesPolicy
from src.brain.interfaces import BrainQuery
from src.brain.scholarship import ScholarshipPolicy
from src.fabric.knowledge import KnowledgeResult, KnowledgeService


class CollegeKnowledgeService(KnowledgeService):
    """Deterministic college knowledge backed by the src/brain policies.

    Runs entirely in the application layer with zero framework imports. Each
    topic maps to a deterministic rule set; the LLM/runtime never computes
    these numbers itself.
    """

    def __init__(
        self,
        fees: FeesPolicy | None = None,
        admission: AdmissionPolicy | None = None,
        scholarship: ScholarshipPolicy | None = None,
    ) -> None:
        self._fees = fees or FeesPolicy()
        self._admission = admission or AdmissionPolicy()
        self._scholarship = scholarship or ScholarshipPolicy()

    def query(self, topic: str, **params: Any) -> KnowledgeResult:
        query = self._to_brain_query(params)
        if topic == "fee":
            return self._from_policy(self._fees.evaluate(query), "fee")
        if topic == "eligibility":
            return self._from_policy(self._admission.evaluate(query), "eligibility")
        if topic == "scholarship":
            return self._from_policy(self._scholarship.evaluate(query), "scholarship")
        return KnowledgeResult(
            content=f"unknown knowledge topic: {topic}",
            data={},
            confidence=0.0,
            source="deterministic",
        )

    def _to_brain_query(self, params: dict[str, Any]) -> BrainQuery:
        return BrainQuery(
            rank=params.get("rank"),
            pcm_percentage=params.get("pcm_percentage"),
            category=params.get("category") or "general",
            board=params.get("board") or "",
            interest=params.get("interest") or "",
            budget=params.get("budget"),
            location=params.get("location") or "",
        )

    def _from_policy(self, result, topic: str) -> KnowledgeResult:
        return KnowledgeResult(
            content=result.details,
            data={
                "topic": topic,
                "applicable": result.applicable,
                "result": result.data,
            },
            confidence=result.confidence,
            source="deterministic",
        )
