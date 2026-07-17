"""ConversationPipeline — the single orchestrator for all queries."""

from __future__ import annotations

import logging
import time
from typing import Protocol

from .models import (
    ChannelMessage,
    ChannelResponse,
    ConversationState,
    Intent,
    Language,
    LLMResponse,
    PipelineResult,
    Source,
    SearchResult,
)

logger = logging.getLogger(__name__)


class SessionStore(Protocol):
    async def get(self, session_id: str) -> ConversationState | None: ...
    async def set(self, session_id: str, state: ConversationState) -> None: ...


class IntentRouter(Protocol):
    async def route(self, query: str, lang: Language, state: ConversationState | None) -> Intent: ...


class StructuredHandler(Protocol):
    def can_handle(self, intent: Intent) -> bool: ...
    async def handle(self, query: str, lang: Language, state: ConversationState | None) -> str | None: ...


class RAGEngine(Protocol):
    async def retrieve(self, query: str, lang: Language) -> list[SearchResult]: ...
    async def generate(self, query: str, context: list[SearchResult], history: list[dict], lang: Language) -> LLMResponse: ...


class PostProcessor(Protocol):
    async def validate(self, answer: str, context: str, query: str) -> tuple[bool, str]: ...
    async def format(self, text: str, lang: Language) -> str: ...


class ConversationPipeline:
    """Single pipeline for all queries — generate and stream use the same logic."""

    def __init__(
        self,
        session_store: SessionStore,
        intent_router: IntentRouter,
        structured_handlers: list[StructuredHandler],
        rag_engine: RAGEngine,
        post_processor: PostProcessor,
    ):
        self.session_store = session_store
        self.intent_router = intent_router
        self.structured_handlers = structured_handlers
        self.rag_engine = rag_engine
        self.post_processor = post_processor

    async def process(self, message: ChannelMessage) -> PipelineResult:
        """Process a single query through the entire pipeline."""
        start = time.time()

        # 1. Load session
        state = await self.session_store.get(message.session_id)
        if state is None:
            state = ConversationState(session_id=message.session_id)
            state.created_at = time.time()

        # 2. Detect language
        lang = message.language or self._detect_language(message.text, state)
        state.language = lang

        # 3. Route intent
        intent = await self.intent_router.route(message.text, lang, state)

        # 4. Check structured handlers first
        answer = None
        source = Source.STRUCTURED
        for handler in self.structured_handlers:
            if handler.can_handle(intent):
                answer = await handler.handle(message.text, lang, state)
                if answer:
                    break

        # 5. If no structured answer, use RAG + LLM
        if not answer:
            source = Source.RAG_LLM
            results = await self.rag_engine.retrieve(message.text, lang)
            llm_response = await self.rag_engine.generate(
                message.text, results, state.history, lang
            )
            answer = llm_response.content

        # 6. Validate
        is_valid, reason = await self.post_processor.validate(answer, "", message.text)
        if not is_valid:
            answer = await self.post_processor.format(
                "I don't have that information. Please call 0343-2501353.", lang
            )
            source = Source.FALLBACK

        # 7. Format for TTS
        answer = await self.post_processor.format(answer, lang)

        # 8. Update session
        state.history.append({"role": "user", "content": message.text})
        state.history.append({"role": "assistant", "content": answer})
        if len(state.history) > 20:
            state.history = state.history[-20:]
        state.last_active = time.time()
        await self.session_store.set(message.session_id, state)

        latency_ms = int((time.time() - start) * 1000)

        return PipelineResult(
            response=ChannelResponse(
                text=answer,
                source=source,
                language=lang,
                latency_ms=latency_ms,
            ),
            intent=intent,
            source=source,
            latency_ms=latency_ms,
        )

    def _detect_language(self, text: str, state: ConversationState) -> Language:
        """Simple language detection based on script and keywords."""
        # Bengali script
        if any("\u0980" <= c <= "\u09ff" for c in text):
            return Language.BN
        # Devanagari script
        if any("\u0900" <= c <= "\u097f" for c in text):
            return Language.HI
        # Roman Hindi/Bengali keywords
        text_lower = text.lower()
        bn_words = {"ami", "amar", "koto", "ache", "hobe", "bhalo", "keno", "kivabe"}
        hi_words = {"hai", "hain", "kya", "kaise", "kitna", "kaun", "kab", "kyu"}
        bn_count = sum(1 for w in bn_words if w in text_lower)
        hi_count = sum(1 for w in hi_words if w in text_lower)
        if bn_count > hi_count:
            return Language.BN
        if hi_count > bn_count:
            return Language.HI
        return state.language
