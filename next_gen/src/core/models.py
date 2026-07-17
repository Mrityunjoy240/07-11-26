"""Core data models for the conversation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Language(str, Enum):
    EN = "en"
    HI = "hi"
    BN = "bn"


class Intent(str, Enum):
    GREETING = "greeting"
    OUT_OF_DOMAIN = "out_of_domain"
    REPEAT = "repeat"
    FEE = "fee"
    ADMISSION = "admission"
    CONTACT = "contact"
    DEPARTMENT = "department"
    PLACEMENT = "placement"
    HOSTEL = "hostel"
    SCHOLARSHIP = "scholarship"
    FACULTY = "faculty"
    HOD = "hod"
    PRINCIPAL = "principal"
    CUTOFF = "cutoff"
    SEATS = "seats"
    SAFETY = "safety"
    TIMINGS = "timings"
    UNKNOWN = "unknown"


class Source(str, Enum):
    STRUCTURED = "structured"
    RAG_LLM = "rag_llm"
    LLM_TOOLS = "llm_tools"
    CACHED = "cached"
    GREETING = "greeting"
    OUT_OF_DOMAIN = "out_of_domain"
    FALLBACK = "fallback"


@dataclass
class ChannelMessage:
    """Normalized input from any channel."""
    text: str
    session_id: str
    channel: str  # "rest", "websocket", "twilio", "livekit"
    audio: bytes | None = None
    language: Language | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelResponse:
    """Normalized output to any channel."""
    text: str
    audio: bytes | None = None
    source: Source = Source.STRUCTURED
    language: Language = Language.EN
    latency_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DomainSlot:
    """Tracks the last resolved intent and department for a domain."""
    domain: str
    intent: str | None = None
    department: str | None = None
    last_updated: float = 0.0


@dataclass
class ConversationState:
    """Per-session conversation state."""
    session_id: str
    history: list[dict[str, str]] = field(default_factory=list)
    language: Language = Language.EN
    domain_slots: dict[str, DomainSlot] = field(default_factory=dict)
    visit_order: list[str] = field(default_factory=list)
    created_at: float = 0.0
    last_active: float = 0.0


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str = ""
    tokens_used: int = 0
    latency_ms: int = 0
    finish_reason: str = ""


@dataclass
class SearchResult:
    """Result from vector search."""
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Result from the conversation pipeline."""
    response: ChannelResponse
    intent: Intent = Intent.UNKNOWN
    source: Source = Source.STRUCTURED
    latency_ms: int = 0
    tokens_used: int = 0
    cache_hit: bool = False
