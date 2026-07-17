from src.conversation.context import build_context, format_context_for_prompt
from src.conversation.state import ConversationState


def test_build_context_empty():
    state = ConversationState(session_id="test-001")
    ctx = build_context(state, "hello")
    assert ctx["current_query"] == "hello"
    assert ctx["student_profile"] == {}
    assert ctx["conversation_stage"] == "discovery"
    assert ctx["language"] == "en"
    assert ctx["recent_history"] == []


def test_build_context_with_history():
    state = ConversationState(
        session_id="test-002",
        profile={"rank": 50000},
        history=[
            {"role": "user", "content": "what are the fees"},
            {"role": "assistant", "content": "fees are 50000"},
            {"role": "user", "content": "any scholarships"},
            {"role": "assistant", "content": "yes there are"},
        ],
    )
    ctx = build_context(state, "tell me more")
    assert len(ctx["recent_history"]) == 4
    assert ctx["recent_history"][0]["role"] == "user"


def test_build_context_history_truncated():
    state = ConversationState(
        session_id="test-003",
        history=[{"role": "user", "content": f"msg-{i}"} for i in range(10)],
    )
    ctx = build_context(state, "hello")
    assert len(ctx["recent_history"]) == 6


def test_format_context_for_prompt():
    state = ConversationState(
        session_id="test-004",
        profile={"rank": 50000},
        history=[{"role": "user", "content": "hello"}],
    )
    ctx = build_context(state, "what are fees")
    formatted = format_context_for_prompt(ctx)
    assert "### Conversation Context" in formatted
    assert "Student Profile" in formatted
    assert "rank" in formatted
    assert "Current Query" in formatted
    assert "what are fees" in formatted
