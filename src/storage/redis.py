import json
from datetime import UTC, datetime

import redis.asyncio as aioredis

from src.config.settings import settings
from src.storage.interfaces import ConversationMessage, SessionData, SessionStore


class RedisSessionStore(SessionStore):
    def __init__(self, redis_url: str | None = None):
        self._redis: aioredis.Redis | None = None
        self._redis_url = redis_url or settings.redis_url

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self._redis_url,
                decode_responses=True,
            )
        return self._redis

    async def get(self, session_id: str) -> SessionData | None:
        r = await self._get_redis()
        raw = await r.get(f"session:{session_id}")
        if raw is None:
            return None
        data = json.loads(raw)
        return SessionData(
            session_id=data["session_id"],
            student_id=data.get("student_id"),
            messages=[ConversationMessage(**m) for m in data.get("messages", [])],
            profile=data.get("profile", {}),
            state=data.get("state", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_active=datetime.fromisoformat(data["last_active"]),
        )

    async def set(self, session: SessionData, ttl: int | None = None) -> None:
        r = await self._get_redis()
        data = {
            "session_id": session.session_id,
            "student_id": session.student_id,
            "messages": [
                {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                for m in session.messages
            ],
            "profile": session.profile,
            "state": session.state,
            "created_at": session.created_at.isoformat(),
            "last_active": session.last_active.isoformat(),
        }
        await r.set(
            f"session:{session.session_id}",
            json.dumps(data),
            ex=ttl or settings.redis_session_ttl,
        )

    async def delete(self, session_id: str) -> None:
        r = await self._get_redis()
        await r.delete(f"session:{session_id}")

    async def touch(self, session_id: str) -> None:
        r = await self._get_redis()
        raw = await r.get(f"session:{session_id}")
        if raw is None:
            return
        data = json.loads(raw)
        data["last_active"] = datetime.now(UTC).isoformat()
        await r.set(f"session:{session_id}", json.dumps(data), ex=settings.redis_session_ttl)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            self._redis = None
