from __future__ import annotations

import logging
from datetime import UTC, datetime

from src.conversation.interfaces import StateManager
from src.conversation.state import ConversationState, state_to_dict
from src.storage.interfaces import ConversationMessage, SessionData, SessionStore

logger = logging.getLogger(__name__)


class SessionManager(StateManager):
    def __init__(self, store: SessionStore):
        self._store = store

    async def load(self, session_id: str) -> ConversationState | None:
        data = await self._store.get(session_id)
        if data is None:
            return None
        return ConversationState(
            session_id=data.session_id,
            student_id=data.student_id,
            history=[{"role": m.role, "content": m.content} for m in data.messages],
            profile=data.profile,
            created_at=data.created_at,
            last_active=data.last_active,
        )

    async def save(self, state: ConversationState) -> None:
        raw = state_to_dict(state)
        messages = [
            ConversationMessage(role=m["role"], content=m["content"])
            for m in raw["history"]
        ]
        session = SessionData(
            session_id=state.session_id,
            student_id=state.student_id,
            messages=messages,
            profile=raw["profile"],
            state=raw,
            created_at=state.created_at,
            last_active=datetime.now(UTC),
        )
        await self._store.set(session)

    async def delete(self, session_id: str) -> None:
        await self._store.delete(session_id)

    async def touch(self, session_id: str) -> None:
        await self._store.touch(session_id)
