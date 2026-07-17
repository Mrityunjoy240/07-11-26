from datetime import UTC, datetime

from src.storage.interfaces import ConversationMessage, SessionData


def test_conversation_message_defaults():
    msg = ConversationMessage(role="user", content="hello")
    assert msg.role == "user"
    assert msg.content == "hello"
    assert isinstance(msg.created_at, datetime)


def test_session_data_creation():
    now = datetime.now(UTC)
    session = SessionData(
        session_id="test-123",
        student_id="stu-456",
        messages=[],
        profile={"rank": 35000},
        state={"stage": "discovery"},
        created_at=now,
        last_active=now,
    )
    assert session.session_id == "test-123"
    assert session.profile["rank"] == 35000
    assert session.state["stage"] == "discovery"
