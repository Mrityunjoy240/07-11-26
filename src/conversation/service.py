from __future__ import annotations

import logging
import time
from typing import Any

from src.conversation.context import build_context
from src.conversation.interfaces import (
    IntentRouter,
    RAGEngine,
    SafetyGuard,
    StateManager,
    StructuredHandler,
)
from src.conversation.state import ConversationState

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(
        self,
        state_manager: StateManager,
        intent_router: IntentRouter | None = None,
        structured_handlers: list[StructuredHandler] | None = None,
        rag_engine: RAGEngine | None = None,
        safety_guard: SafetyGuard | None = None,
    ):
        self._state_manager = state_manager
        self._intent_router = intent_router
        self._structured_handlers = structured_handlers or []
        self._rag_engine = rag_engine
        self._safety_guard = safety_guard

    async def process(
        self, text: str, session_id: str, channel: str = "web"
    ) -> dict[str, Any]:
        start = time.time()

        # 1. OBSERVE — load state and build context
        state = await self._load_or_create(session_id, channel)
        context = build_context(state, text)

        # 2. PLAN — route intent, find handler
        intent = await self._route_intent(text, state)
        answer = await self._execute_plan(text, intent, state)

        # 3. ACT — validate answer
        if answer is None:
            answer = "I couldn't find an answer. Please contact the admission office."
        answer = await self._validate(text, answer, state)

        # 4. REMEMBER — update state and persist
        self._update_state(state, text, answer, intent, context)
        await self._state_manager.save(state)

        latency_ms = int((time.time() - start) * 1000)

        return {
            "text": answer,
            "intent": intent,
            "session_id": session_id,
            "latency_ms": latency_ms,
            "channel": channel,
        }

    async def _load_or_create(
        self, session_id: str, channel: str
    ) -> ConversationState:
        state = await self._state_manager.load(session_id)
        if state is None:
            state = ConversationState(
                session_id=session_id,
                channel=channel,
            )
        else:
            state.channel = channel
        return state

    async def _route_intent(self, text: str, state: ConversationState) -> str:
        if self._intent_router is None:
            return "unknown"
        return await self._intent_router.route(text, state)

    async def _execute_plan(
        self, text: str, intent: str, state: ConversationState
    ) -> str | None:
        for handler in self._structured_handlers:
            if handler.can_handle(intent):
                result = await handler.handle(text, state)
                if result:
                    return result

        if self._rag_engine is not None:
            results = await self._rag_engine.retrieve(text, state)
            return await self._rag_engine.generate(text, results, state)

        return None

    async def _validate(
        self, text: str, answer: str, state: ConversationState
    ) -> str:
        if self._safety_guard is None:
            return answer
        is_valid, reason = await self._safety_guard.validate(answer, text, state)
        if not is_valid:
            logger.warning("Safety guard rejected answer: %s", reason)
            return "I don't have that information. Please call 0343-2501353."
        return answer

    def _update_state(
        self,
        state: ConversationState,
        text: str,
        answer: str,
        intent: str,
        context: dict,
    ) -> None:
        state.history.append({"role": "user", "content": text})
        state.history.append({"role": "assistant", "content": answer})
        if len(state.history) > 20:
            state.history = state.history[-20:]
