"""Swap test: InMemorySessionStore and RedisSessionStore must behave identically.

Run with:  python -m pytest tests/test_session_store_swap.py -v
Redis:     USE_REDIS_SESSIONS=true python -m pytest tests/test_session_store_swap.py -v
"""

import os

import pytest

from src.config.settings import Settings
from src.storage.factory import create_session_store
from src.storage.interfaces import (
    ConversationMessage,
    InMemorySessionStore,
    SessionData,
    SessionStore,
)


@pytest.fixture
def store() -> SessionStore:
    if os.environ.get("USE_REDIS_SESSIONS", "").lower() in ("true", "1"):
        s = Settings(use_redis_sessions=True)
        return create_session_store()
    return InMemorySessionStore()


@pytest.fixture
def sample_session() -> SessionData:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    return SessionData(
        session_id="swap-test-001",
        student_id="stu-999",
        messages=[ConversationMessage(role="user", content="hello")],
        profile={"rank": 50000, "board": "WBCHSE"},
        state={"stage": "discovery", "intent": "eligibility"},
        created_at=now,
        last_active=now,
    )


@pytest.mark.asyncio
async def test_set_and_get(store: SessionStore, sample_session: SessionData):
    await store.set(sample_session)
    loaded = await store.get(sample_session.session_id)
    assert loaded is not None
    assert loaded.session_id == "swap-test-001"
    assert loaded.student_id == "stu-999"
    assert len(loaded.messages) == 1
    assert loaded.messages[0].content == "hello"
    assert loaded.profile == {"rank": 50000, "board": "WBCHSE"}
    assert loaded.state == {"stage": "discovery", "intent": "eligibility"}
    await store.close()


@pytest.mark.asyncio
async def test_get_nonexistent(store: SessionStore):
    loaded = await store.get("nonexistent-session")
    assert loaded is None
    await store.close()


@pytest.mark.asyncio
async def test_delete(store: SessionStore, sample_session: SessionData):
    await store.set(sample_session)
    loaded = await store.get(sample_session.session_id)
    assert loaded is not None
    await store.delete(sample_session.session_id)
    loaded_after = await store.get(sample_session.session_id)
    assert loaded_after is None
    await store.close()


@pytest.mark.asyncio
async def test_touch_updates_last_active(store: SessionStore, sample_session: SessionData):
    from datetime import UTC, datetime

    await store.set(sample_session)
    original = await store.get(sample_session.session_id)
    assert original is not None
    original_last_active = original.last_active

    await store.touch(sample_session.session_id)
    touched = await store.get(sample_session.session_id)
    assert touched is not None
    assert touched.last_active > original_last_active
    await store.close()


@pytest.mark.asyncio
async def test_overwrite_session(store: SessionStore, sample_session: SessionData):
    await store.set(sample_session)
    updated = SessionData(
        session_id=sample_session.session_id,
        student_id=sample_session.student_id,
        messages=[ConversationMessage(role="assistant", content="updated")],
        profile={},
        state={},
        created_at=sample_session.created_at,
        last_active=sample_session.last_active,
    )
    await store.set(updated)
    loaded = await store.get(sample_session.session_id)
    assert loaded is not None
    assert loaded.messages[0].content == "updated"
    assert loaded.profile == {}
    await store.close()


@pytest.mark.asyncio
async def test_multiple_sessions(store: SessionStore):
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    sessions = []
    for i in range(5):
        s = SessionData(
            session_id=f"multi-{i}",
            student_id=f"stu-{i}",
            messages=[],
            profile={"id": i},
            state={},
            created_at=now,
            last_active=now,
        )
        sessions.append(s)
        await store.set(s)

    for s in sessions:
        loaded = await store.get(s.session_id)
        assert loaded is not None
        assert loaded.profile["id"] == int(s.session_id.split("-")[1])

    await store.close()
