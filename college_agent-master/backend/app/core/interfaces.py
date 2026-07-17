from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, AsyncIterator, List, Protocol


class ChannelAdapter(ABC):
    """Abstract base for all channel adapters (web, voice, telephony, WhatsApp, etc.)."""

    @property
    @abstractmethod
    def channel_type(self) -> str:
        """Unique identifier for this channel, e.g. 'web', 'voice', 'telephony'."""

    @abstractmethod
    async def handle_message(
        self, message: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process an incoming message. Returns a response dict."""

    @abstractmethod
    async def format_response(
        self, response: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert internal response format to channel-specific format."""


class ConversationStage(ABC):
    """A single deterministic processing stage in the conversation pipeline."""

    @abstractmethod
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process and mutate the conversation context. Returns updated context."""


class EventBus(ABC):
    """Publish-subscribe event bus for cross-cutting concerns."""

    @abstractmethod
    async def publish(self, event: str, data: Dict[str, Any]) -> None:
        """Publish an event with associated data."""

    @abstractmethod
    def subscribe(self, event: str, handler) -> None:
        """Register an async handler for an event."""


class LLMProvider(ABC):
    """Abstract interface for LLM providers (Groq, OpenAI, Gemini, etc.)."""

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> str:
        """Generate a complete response."""

    @abstractmethod
    async def stream_generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream a response token by token."""


class TTSProvider(ABC):
    """Abstract interface for Text-to-Speech providers."""

    @abstractmethod
    async def synthesize(self, text: str, language: str = "en") -> bytes:
        """Convert text to audio bytes."""


class STTProvider(ABC):
    """Abstract interface for Speech-to-Text providers."""

    @abstractmethod
    async def transcribe(self, audio: bytes, language: str = "en") -> str:
        """Convert audio bytes to text."""


class SessionStore(ABC):
    """Abstract interface for session storage (in-memory, Redis, DB, etc.)."""

    @abstractmethod
    async def get(self, session_id: str, key: str) -> Optional[Any]:
        """Retrieve a value from session store."""

    @abstractmethod
    async def set(self, session_id: str, key: str, value: Any) -> None:
        """Store a value in session store."""

    @abstractmethod
    async def delete(self, session_id: str, key: str) -> None:
        """Remove a value from session store."""

    @abstractmethod
    async def clear(self, session_id: str) -> None:
        """Clear all data for a session."""

    @abstractmethod
    async def get_all(self, session_id: str) -> Dict[str, Any]:
        """Retrieve all data for a session."""


class KnowledgeRetriever(ABC):
    """Abstract interface for knowledge base retrieval."""

    @abstractmethod
    async def retrieve(
        self, query: str, top_k: int = 4, **kwargs
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant context chunks for a query."""
