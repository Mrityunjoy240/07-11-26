import logging
from typing import Dict, Any

from app.core.models import ConversationRequest, ConversationResponse
from app.core.conversation_engine import ConversationEngine
from .base import BaseChannelAdapter

logger = logging.getLogger(__name__)


class WebChannelAdapter(BaseChannelAdapter):
    """Adapter for the web (REST/JSON) chat channel.

    The adapter ONLY knows about ConversationEngine.
    It does NOT know about GroqService, Gemini, or any provider.
    """

    def __init__(self, engine: ConversationEngine):
        self._engine = engine

    @property
    def channel_type(self) -> str:
        return "web"

    async def handle_message(
        self, message: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        request = ConversationRequest(
            text=message.get("text", ""),
            session_id=context.get("session_id", "default"),
            conversation_id=context.get("conversation_id"),
            channel="web",
        )

        response: ConversationResponse = await self._engine.handle(request)

        return {
            "answer": response.text,
            "voice_text": response.voice_text,
            "sources": [],
            "session_id": response.session_id,
            "conversation_id": response.conversation_id,
            "source": response.source,
            "intent": response.intent,
            "confidence": response.confidence,
        }

    async def format_response(
        self, response: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "answer": response.get("answer", ""),
            "voice_text": response.get("voice_text"),
            "session_id": context.get("session_id", ""),
            "conversation_id": context.get("conversation_id"),
            "source": response.get("source", "groq_rag"),
            "intent": response.get(
                "intent",
                "faq_deterministic"
                if response.get("source") == "faq_deterministic"
                else "llm_generated",
            ),
            "confidence": response.get("confidence", 0.95),
        }
