"""Restart test: session must survive a backend restart when using Redis.

Simulates: set session -> destroy store object -> create new store -> load session.
"""
import os

import pytest

from src.config.settings import settings
from src.storage.interfaces import ConversationMessage, SessionData
from src.storage.redis import RedisSessionStore


@pytest.mark.skipif(
    os.environ.get("USE_REDIS_SESSIONS", "").lower() not in ("true", "1"),
    reason="requires Redis",
)
@pytest.mark.asyncio
async def test_session_survives_restart():
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    session_id = "restart-test-001"

    store1 = RedisSessionStore(redis_url=settings.redis_url)
    await store1.set(
        SessionData(
            session_id=session_id,
            student_id="stu-restart",
            messages=[ConversationMessage(role="user", content="hello")],
            profile={"rank": 50000},
            state={"stage": "discovery"},
            created_at=now,
            last_active=now,
        )
    )
    await store1.close()

    store2 = RedisSessionStore(redis_url=settings.redis_url)
    loaded = await store2.get(session_id)
    assert loaded is not None
    assert loaded.student_id == "stu-restart"
    assert len(loaded.messages) == 1
    assert loaded.messages[0].content == "hello"
    assert loaded.profile == {"rank": 50000}
    assert loaded.state == {"stage": "discovery"}

    await store2.delete(session_id)
    await store2.close()
