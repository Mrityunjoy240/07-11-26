import logging
from typing import Dict, Any

from app.core.models import ConversationResponse
from app.pipeline.base import PipelineStage

logger = logging.getLogger(__name__)


class ResponseFormatterStage(PipelineStage):
    stage_name = "response_formatter"

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        request = context.get("request")
        guarded = context.get("llm_guarded") or context.get("llm_raw", "")

        response = ConversationResponse(
            text=guarded,
            voice_text=context.get("voice_text"),
            intent=context.get("intent", "llm_generated"),
            source="groq_rag",
            session_id=request.session_id if request else "default",
            conversation_id=request.conversation_id if request else None,
            channel=request.channel if request else "web",
        )

        context["response"] = response
        return context
