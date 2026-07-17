from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


@dataclass
class ConversationRequest:
    """Universal request object for every channel.

    Web, voice, telephony, WhatsApp, Telegram — all produce this.
    The ConversationEngine consumes this.
    """
    text: str
    session_id: str = "default"
    channel: str = "web"
    conversation_id: Optional[str] = None
    tenant_id: Optional[str] = None
    language: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationResponse:
    """Universal response object for every channel.

    The ConversationEngine returns this.
    Channel adapters format it for their specific output.
    """
    text: str
    voice_text: Optional[str] = None
    sources: List[str] = field(default_factory=list)
    intent: str = "llm_generated"
    confidence: float = 0.95
    source: str = "groq_rag"
    session_id: str = "default"
    conversation_id: Optional[str] = None
    latency_ms: float = 0.0
    channel: str = "web"
    error: Optional[str] = None
