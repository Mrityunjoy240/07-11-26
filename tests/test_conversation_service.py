import pytest

from src.conversation.service import ConversationService
from src.conversation.session import SessionManager
from src.storage.interfaces import InMemorySessionStore


@pytest.fixture
def store():
    return InMemorySessionStore()


@pytest.fixture
def service(store: InMemorySessionStore):
    mgr = SessionManager(store)
    return ConversationService(state_manager=mgr)


@pytest.mark.asyncio
async def test_process_new_session(service: ConversationService):
    result = await service.process("hello", session_id="test-001")
    assert result["text"] is not None
    assert result["session_id"] == "test-001"
    assert result["intent"] == "unknown"
    assert "latency_ms" in result
    assert result["channel"] == "web"


@pytest.mark.asyncio
async def test_process_voice_channel(service: ConversationService):
    result = await service.process("hello", session_id="test-002", channel="voice")
    assert result["channel"] == "voice"


@pytest.mark.asyncio
async def test_process_updates_history(
    service: ConversationService, store: InMemorySessionStore
):
    await service.process("first", session_id="test-003")
    await service.process("second", session_id="test-003")
    mgr = SessionManager(store)
    state = await mgr.load("test-003")
    assert state is not None
    assert len(state.history) >= 2


@pytest.mark.asyncio
async def test_process_multiple_sessions(service: ConversationService):
    r1 = await service.process("hello", session_id="sess-a")
    r2 = await service.process("hello", session_id="sess-b")
    assert r1["session_id"] == "sess-a"
    assert r2["session_id"] == "sess-b"
