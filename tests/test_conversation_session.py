import pytest

from src.conversation.session import SessionManager
from src.conversation.state import ConversationState
from src.storage.interfaces import InMemorySessionStore


@pytest.fixture
def manager():
    store = InMemorySessionStore()
    return SessionManager(store)


@pytest.mark.asyncio
async def test_load_nonexistent(manager: SessionManager):
    state = await manager.load("nonexistent")
    assert state is None


@pytest.mark.asyncio
async def test_save_and_load(manager: SessionManager):
    state = ConversationState(
        session_id="test-001",
        student_id="stu-001",
        profile={"rank": 50000},
        history=[{"role": "user", "content": "hello"}],
    )
    await manager.save(state)
    loaded = await manager.load("test-001")
    assert loaded is not None
    assert loaded.session_id == "test-001"
    assert loaded.student_id == "stu-001"
    assert loaded.profile == {"rank": 50000}
    assert len(loaded.history) == 1
    assert loaded.history[0]["content"] == "hello"


@pytest.mark.asyncio
async def test_delete(manager: SessionManager):
    state = ConversationState(session_id="test-002")
    await manager.save(state)
    await manager.delete("test-002")
    loaded = await manager.load("test-002")
    assert loaded is None


@pytest.mark.asyncio
async def test_touch(manager: SessionManager):
    state = ConversationState(session_id="test-003")
    await manager.save(state)
    original = await manager.load("test-003")
    assert original is not None
    await manager.touch("test-003")
