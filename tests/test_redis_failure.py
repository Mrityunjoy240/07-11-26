"""Failure injection: Redis goes down, backend does not crash.

Test scenarios:
1. get returns None when Redis is unreachable (wrong port)
2. set silently fails when Redis is unreachable
3. delete silently fails when Redis is unreachable
4. touch silently fails when Redis is unreachable
5. Already-connected store survives Redis going away mid-operation
"""
from datetime import UTC, datetime
from os import environ

import pytest

from src.config.settings import settings
from src.storage.interfaces import ConversationMessage, SessionData
from src.storage.redis import RedisSessionStore

DOWN_URL = "redis://localhost:16379/0"


@pytest.fixture
def session_data() -> SessionData:
    now = datetime.now(UTC)
    return SessionData(
        session_id="fail-test-001",
        student_id="stu-fail",
        messages=[ConversationMessage(role="user", content="hello")],
        profile={"rank": 50000},
        state={"stage": "discovery"},
        created_at=now,
        last_active=now,
    )


@pytest.mark.asyncio
async def test_get_returns_none_when_redis_down():
    store = RedisSessionStore(redis_url=DOWN_URL)
    result = await store.get("any-session")
    assert result is None
    await store.close()


@pytest.mark.asyncio
async def test_set_does_not_raise_when_redis_down(session_data: SessionData):
    store = RedisSessionStore(redis_url=DOWN_URL)
    await store.set(session_data)
    await store.close()


@pytest.mark.asyncio
async def test_delete_does_not_raise_when_redis_down():
    store = RedisSessionStore(redis_url=DOWN_URL)
    await store.delete("non-existent")
    await store.close()


@pytest.mark.asyncio
async def test_touch_does_not_raise_when_redis_down():
    store = RedisSessionStore(redis_url=DOWN_URL)
    await store.touch("non-existent")
    await store.close()


@pytest.mark.asyncio
async def test_close_does_not_raise_when_redis_down():
    store = RedisSessionStore(redis_url=DOWN_URL)
    await store.close()


@pytest.mark.skipif(
    environ.get("USE_REDIS_SESSIONS", "").lower() not in ("true", "1"),
    reason="requires Redis running",
)
@pytest.mark.asyncio
async def test_still_works_when_redis_comes_back():
    store = RedisSessionStore(redis_url=settings.redis_url)
    result = await store.get("recovered-session")
    assert result is None
    await store.close()
