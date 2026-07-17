from datetime import UTC, datetime

from src.conversation.state import (
    ConversationStage,
    ConversationState,
    DomainSlot,
    EmotionalState,
    state_from_dict,
    state_to_dict,
)


def test_conversation_state_defaults():
    state = ConversationState(session_id="test-001")
    assert state.session_id == "test-001"
    assert state.stage == ConversationStage.DISCOVERY
    assert state.language == "en"
    assert state.emotional_state.primary == "neutral"
    assert state.emotional_state.confidence == 0.0
    assert state.profile == {}
    assert state.history == []
    assert state.visit_order == []


def test_conversation_state_with_values():
    now = datetime.now(UTC)
    state = ConversationState(
        session_id="test-002",
        student_id="stu-001",
        channel="voice",
        language="bn",
        stage=ConversationStage.EVALUATION,
        emotional_state=EmotionalState(primary="anxious", confidence=0.8),
        profile={"rank": 50000, "board": "WBCHSE"},
        goals={"primary": "get_CSE", "resolved": False},
        domain_slots={
            "fees": DomainSlot(domain="fees", intent="total_fee", resolved=True),
        },
        visit_order=["fees", "admission"],
        history=[{"role": "user", "content": "hello"}],
        created_at=now,
        last_active=now,
    )
    assert state.student_id == "stu-001"
    assert state.emotional_state.primary == "anxious"
    assert state.domain_slots["fees"].resolved is True
    assert state.visit_order == ["fees", "admission"]


def test_state_roundtrip():
    now = datetime.now(UTC)
    original = ConversationState(
        session_id="test-003",
        student_id="stu-002",
        stage=ConversationStage.EVALUATION,
        emotional_state=EmotionalState(primary="curious", confidence=0.6),
        profile={"rank": 25000},
        history=[{"role": "user", "content": "tell me about fees"}],
        created_at=now,
        last_active=now,
    )
    raw = state_to_dict(original)
    restored = state_from_dict("test-003", raw)
    assert restored.session_id == original.session_id
    assert restored.student_id == original.student_id
    assert restored.stage == original.stage
    assert restored.emotional_state.primary == original.emotional_state.primary
    assert restored.profile == original.profile
    assert restored.history == original.history


def test_history_truncated_on_export():
    state = ConversationState(
        session_id="test-004",
        history=[{"role": "user", "content": f"msg-{i}"} for i in range(25)],
    )
    raw = state_to_dict(state)
    assert len(raw["history"]) == 20


def test_domain_slot_defaults():
    slot = DomainSlot(domain="fees")
    assert slot.resolved is False
    assert slot.intent is None
    assert slot.department is None
