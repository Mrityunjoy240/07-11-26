import logging
import time
from typing import Dict, Any, List, Optional

from app.core.interfaces import ConversationStage
from app.core.models import ConversationRequest, ConversationResponse

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Orchestrates a sequence of ConversationStages.

    Each stage receives the full context dict, processes one concern,
    and returns the mutated context. The runner handles:
      - Sequencing stages in order
      - Short-circuit (stage sets '_short_circuit' to stop early)
      - Per-stage latency tracking
      - Error containment (one stage failure does not crash the pipeline)
    """

    def __init__(self, stages: List[ConversationStage]):
        self._stages = stages

    async def run(self, request: ConversationRequest) -> ConversationResponse:
        context: Dict[str, Any] = {
            "request": request,
            "latencies": {},
        }

        for stage in self._stages:
            if context.get("_short_circuit"):
                logger.debug(f"Pipeline short-circuited after '{stage.stage_name}'")
                break

            stage_start = time.monotonic()
            stage_name = getattr(stage, "stage_name", stage.__class__.__name__)

            try:
                context = await stage.process(context)
            except Exception as e:
                logger.error(
                    f"Pipeline stage '{stage_name}' failed: {e}", exc_info=True
                )
                context["_error"] = str(e)
                context["_error_stage"] = stage_name
                break

            elapsed = (time.monotonic() - stage_start) * 1000
            context["latencies"][stage_name] = round(elapsed, 1)

        return self._build_response(context, request)

    @staticmethod
    def _build_response(
        context: Dict[str, Any], request: ConversationRequest
    ) -> ConversationResponse:
        response: Optional[ConversationResponse] = context.get("response")
        if response is not None:
            response.latency_ms = round(sum(context.get("latencies", {}).values()), 1)
            return response

        fallback_text = context.get("llm_raw") or context.get("llm_guarded") or ""
        return ConversationResponse(
            text=fallback_text,
            session_id=request.session_id,
            conversation_id=request.conversation_id,
            channel=request.channel,
            error=context.get("_error"),
            latency_ms=round(sum(context.get("latencies", {}).values()), 1),
        )
