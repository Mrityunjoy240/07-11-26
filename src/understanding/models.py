from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.understanding.interpreter import DomainInterpretation as DomainInterpretation

# Import StudentProfile but keep it optional — it's set during pipeline run
from src.understanding.profile import StudentProfile as StudentProfile, compute_missing
from src.understanding.signals.conversation import StructuredSignals as StructuredSignals
from src.understanding.signals.interaction import SignalInteraction as SignalInteraction


@dataclass
class ConversationSignals:
    anxiety: float = 0.0
    urgency: float = 0.0
    confusion: float = 0.0
    hesitation: float = 0.0
    frustration: float = 0.0
    financial_concern: float = 0.0
    parent_influence: float = 0.0

    @property
    def dominant(self) -> tuple[str, float]:
        signals = {
            "anxiety": self.anxiety,
            "urgency": self.urgency,
            "confusion": self.confusion,
            "hesitation": self.hesitation,
            "frustration": self.frustration,
            "financial_concern": self.financial_concern,
            "parent_influence": self.parent_influence,
        }
        return max(signals.items(), key=lambda x: x[1])


@dataclass
class ExtractedFact:
    field: str
    value: Any
    confidence: float = 1.0


@dataclass
class MissingInformation:
    items: list[str] = field(default_factory=list)


@dataclass
class UnderstandingIntent:
    primary: str = "unknown"
    confidence: float = 0.0
    all_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class StageDetail:
    """Per-intent scores and evidence for a single scoring stage."""
    scores: dict[str, float] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)


@dataclass
class IntentDiagnostics:
    """Full per-intent, per-stage scoring trace for debugging."""
    input: str = ""
    stage_details: dict[str, StageDetail] = field(default_factory=dict)
    stage_weights: dict[str, float] = field(default_factory=dict)

    per_intent_breakdown: dict[str, dict[str, float]] = field(default_factory=dict)
    pre_conflict: dict[str, float] = field(default_factory=dict)
    post_conflict: dict[str, float] = field(default_factory=dict)
    conflicts_applied: list[str] = field(default_factory=list)
    winner: str = ""
    confidence: float = 0.0
    winner_reason: str = ""

    ranked_intents: list[tuple[str, float]] = field(default_factory=list)
    runner_up_score: float = 0.0
    margin: float = 0.0
    confidence_class: str = "LOW"
    validation: Any = None


@dataclass
class UnderstandingResult:
    text: str
    language: str = "en"
    intent: UnderstandingIntent = field(default_factory=UnderstandingIntent)
    profile: StudentProfile = field(default_factory=StudentProfile)
    signals: ConversationSignals = field(default_factory=ConversationSignals)
    structured_signals: StructuredSignals = field(default_factory=StructuredSignals)
    signal_interaction: SignalInteraction = field(default_factory=lambda: SignalInteraction(
        overlap_tags=(), primary_dimension="none", confidence_ranking=(),
    ))
    missing_info: MissingInformation = field(default_factory=MissingInformation)
    references_previous: bool = False
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    domain: DomainInterpretation = field(default_factory=DomainInterpretation)
