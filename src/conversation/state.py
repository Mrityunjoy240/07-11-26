from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ConversationStage(StrEnum):
    DISCOVERY = "discovery"
    EVALUATION = "evaluation"
    DECISION = "decision"
    APPLICATION = "application"


@dataclass
class EmotionalState:
    primary: str = "neutral"
    confidence: float = 0.0


@dataclass
class DomainSlot:
    domain: str
    intent: str | None = None
    department: str | None = None
    resolved: bool = False
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ConversationState:
    session_id: str
    student_id: str | None = None
    channel: str = "web"
    language: str = "en"
    stage: ConversationStage = ConversationStage.DISCOVERY
    emotional_state: EmotionalState = field(default_factory=EmotionalState)
    profile: dict[str, Any] = field(default_factory=dict)
    goals: dict[str, Any] = field(default_factory=lambda: {"primary": "", "resolved": False})
    domain_slots: dict[str, DomainSlot] = field(default_factory=dict)
    visit_order: list[str] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_active: datetime = field(default_factory=lambda: datetime.now(UTC))


def state_from_dict(session_id: str, data: dict) -> ConversationState:
    slots_raw = data.get("domain_slots", {})
    domain_slots = {}
    for domain, slot in slots_raw.items():
        if isinstance(slot, dict):
            domain_slots[domain] = DomainSlot(**slot)
        elif isinstance(slot, DomainSlot):
            domain_slots[domain] = slot

    emo = data.get("emotional_state", {})
    if isinstance(emo, dict):
        emotional_state = EmotionalState(**emo)
    elif isinstance(emo, EmotionalState):
        emotional_state = emo
    else:
        emotional_state = EmotionalState()

    stage_raw = data.get("stage", "discovery")
    try:
        stage = ConversationStage(stage_raw)
    except ValueError:
        stage = ConversationStage.DISCOVERY

    return ConversationState(
        session_id=session_id,
        student_id=data.get("student_id"),
        channel=data.get("channel", "web"),
        language=data.get("language", "en"),
        stage=stage,
        emotional_state=emotional_state,
        profile=data.get("profile", {}),
        goals=data.get("goals", {"primary": "", "resolved": False}),
        domain_slots=domain_slots,
        visit_order=data.get("visit_order", []),
        history=data.get("history", []),
        metadata=data.get("metadata", {}),
        created_at=_parse_dt(data.get("created_at")),
        last_active=_parse_dt(data.get("last_active")),
    )


def state_to_dict(state: ConversationState) -> dict:
    return {
        "session_id": state.session_id,
        "student_id": state.student_id,
        "channel": state.channel,
        "language": state.language,
        "stage": state.stage.value,
        "emotional_state": {
            "primary": state.emotional_state.primary,
            "confidence": state.emotional_state.confidence,
        },
        "profile": state.profile,
        "goals": state.goals,
        "domain_slots": {
            k: {
                "domain": v.domain,
                "intent": v.intent,
                "department": v.department,
                "resolved": v.resolved,
                "last_updated": v.last_updated.isoformat(),
            }
            for k, v in state.domain_slots.items()
        },
        "visit_order": state.visit_order,
        "history": state.history[-20:] if len(state.history) > 20 else state.history,
        "metadata": state.metadata,
        "created_at": state.created_at.isoformat(),
        "last_active": state.last_active.isoformat(),
    }


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return datetime.now(UTC)
