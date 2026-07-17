import logging
import time
from typing import Optional

from app.core.models import ConversationRequest, ConversationResponse
from app.core.feature_flags import feature_flags
from app.pipeline.runner import PipelineRunner

logger = logging.getLogger(__name__)


class ConversationEngine:
    """Single entry point for all channel adapters.

    Adapters call:
        response = await engine.handle(request)

    The engine decides whether to use the new pipeline or the legacy
    GroqService path based on the 'use_pipeline' feature flag.

    When migration is complete, _legacy_handle() is deleted and
    the feature flag check is removed.
    """

    def __init__(self, pipeline_runner: Optional[PipelineRunner] = None):
        self._runner = pipeline_runner

    async def handle(
        self, request: ConversationRequest
    ) -> ConversationResponse:
        start = time.monotonic()

        if feature_flags.use_pipeline and self._runner is not None:
            response = await self._runner.run(request)
        else:
            response = await self._legacy_handle(request)

        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        response.latency_ms = elapsed_ms

        # ── MIGRATION WARNING ──────────────────────────────────────────────
        if feature_flags.migration_deadline and not feature_flags.use_pipeline:
            logger.warning(
                "MIGRATION: use_pipeline flag is OFF but deadline %s has passed. "
                "This legacy path will be removed.",
                feature_flags.migration_deadline,
            )
        # ───────────────────────────────────────────────────────────────────

        return response

    async def _legacy_handle(
        self, request: ConversationRequest
    ) -> ConversationResponse:
        from app.services.llm.groq_service import get_groq_service

        service = get_groq_service()
        result = await service.generate_response(
            request.text, session_id=request.session_id
        )

        # ── DEMO_SAFEPOINT post-processing ──
        from app.config import settings

        if settings.demo_safepoint:
            from app.services.llm.safe_point import post_process_response

            result = post_process_response(None, request.text, result, "en")
        # ────────────────────────────────────

        return ConversationResponse(
            text=result.get("answer", ""),
            voice_text=result.get("voice_text"),
            intent=result.get("intent", "llm_generated"),
            source=result.get("source", "groq_rag"),
            session_id=request.session_id,
            conversation_id=request.conversation_id,
            channel=request.channel,
        )
