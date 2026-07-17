"""In-memory session store for demo."""

from __future__ import annotations

import time

from ..core.models import ConversationState


class MemorySessionStore:
    """In-memory session store. Good for demo, single process."""

    def __init__(self, max_age_seconds: int = 1800):
        self._sessions: dict[str, ConversationState] = {}
        self._max_age = max_age_seconds

    async def get(self, session_id: str) -> ConversationState | None:
        """Get a session by ID."""
        state = self._sessions.get(session_id)
        if state and (time.time() - state.last_active) < self._max_age:
            return state
        # Expired or not found
        if state:
            del self._sessions[session_id]
        return None

    async def set(self, session_id: str, state: ConversationState) -> None:
        """Save a session."""
        self._sessions[session_id] = state

    async def delete(self, session_id: str) -> None:
        """Delete a session."""
        self._sessions.pop(session_id, None)

    async def cleanup(self) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        now = time.time()
        expired = [
            sid for sid, state in self._sessions.items()
            if (now - state.last_active) > self._max_age
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)
