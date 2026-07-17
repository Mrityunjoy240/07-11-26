from typing import Protocol

from src.conversation.state import ConversationState


class StateManager(Protocol):
    async def load(self, session_id: str) -> ConversationState | None: ...
    async def save(self, state: ConversationState) -> None: ...
    async def delete(self, session_id: str) -> None: ...
    async def touch(self, session_id: str) -> None: ...


class IntentRouter(Protocol):
    async def route(self, query: str, state: ConversationState) -> str: ...


class StructuredHandler(Protocol):
    def can_handle(self, intent: str) -> bool: ...
    async def handle(self, query: str, state: ConversationState) -> str | None: ...


class RAGEngine(Protocol):
    async def retrieve(self, query: str, state: ConversationState) -> list[dict]: ...
    async def generate(
        self, query: str, context: list[dict], state: ConversationState
    ) -> str: ...


class SafetyGuard(Protocol):
    async def validate(
        self, answer: str, query: str, state: ConversationState
    ) -> tuple[bool, str]: ...


class ConversationProcessor(Protocol):
    async def process(
        self, text: str, session_id: str, channel: str = "web"
    ) -> dict: ...
