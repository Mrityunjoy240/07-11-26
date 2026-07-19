from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EligibilityEstimate:
    likely: bool = False
    branches: list[str] = field(default_factory=list)
    confidence: float = 0.0
    note: str = ""


@dataclass
class ReasoningResult:
    student_stage: str = "discovery"
    profile_completeness: float = 0.0
    eligibility: EligibilityEstimate = field(default_factory=EligibilityEstimate)
    current_problem: str = ""
    unknowns: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    knowledge_needed: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
