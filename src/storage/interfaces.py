from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class ConversationMessage:
    role: str
    content: str
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class StudentProfile:
    student_id: str
    data: dict[str, Any]
    updated_at: datetime = field(default_factory=_utcnow)


@dataclass
class SessionData:
    session_id: str
    student_id: str | None
    messages: list[ConversationMessage]
    profile: dict[str, Any]
    state: dict[str, Any]
    created_at: datetime
    last_active: datetime


class SessionStore(ABC):
    @abstractmethod
    async def get(self, session_id: str) -> SessionData | None: ...

    @abstractmethod
    async def set(self, session: SessionData, ttl: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, session_id: str) -> None: ...

    @abstractmethod
    async def touch(self, session_id: str) -> None: ...


class ConversationStore(ABC):
    @abstractmethod
    async def save_message(self, conversation_id: str, message: ConversationMessage) -> None: ...

    @abstractmethod
    async def get_messages(self, conversation_id: str) -> list[ConversationMessage]: ...

    @abstractmethod
    async def create_conversation(
        self, conversation_id: str, student_id: str | None = None
    ) -> None: ...
