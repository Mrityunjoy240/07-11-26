import logging
from typing import Dict, Any

from app.pipeline.base import PipelineStage

logger = logging.getLogger(__name__)


class SafetyGuardStage(PipelineStage):
    stage_name = "safety_guard"

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        request = context.get("request")
        raw_response = context.get("llm_raw", "")
        query = request.text if request else ""
        language = context.get("language", "en")

        if not raw_response:
            return context

        from app.config import settings

        if settings.demo_safepoint:
            from app.services.llm.safe_point import post_process_response

            dummy_result = {
                "answer": raw_response,
                "voice_text": context.get("voice_text"),
            }
            processed = post_process_response(
                None, query, dummy_result, language
            )
            context["llm_guarded"] = processed.get("answer", raw_response)
        else:
            context["llm_guarded"] = raw_response

        return context
