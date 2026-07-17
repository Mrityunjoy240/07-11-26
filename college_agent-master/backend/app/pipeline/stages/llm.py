import logging
from typing import Dict, Any

from app.pipeline.base import PipelineStage

logger = logging.getLogger(__name__)


class LLMGenerationStage(PipelineStage):
    stage_name = "llm_generation"

    def __init__(self, llm_provider=None):
        self._llm = llm_provider

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        request = context.get("request")
        query = request.text if request else ""
        language = context.get("language", "en")
        knowledge = context.get("knowledge_text", "")
        intent = context.get("intent", "")

        if self._llm is not None:
            system_prompt = self._build_prompt(language, intent, knowledge)
            response = await self._llm.generate(
                messages=[{"role": "user", "content": query}],
                system_prompt=system_prompt,
            )
            context["llm_raw"] = response
        else:
            from app.services.llm.groq_service import get_groq_service

            service = get_groq_service()
            result = await service.generate_response(
                query, session_id=request.session_id
            )
            context["llm_raw"] = result.get("answer", "")
            context["voice_text"] = result.get("voice_text")

        return context

    @staticmethod
    def _build_prompt(
        language: str, intent: str, knowledge: str
    ) -> str:
        parts = []
        if language and language != "en":
            parts.append(f"Respond in {language}.")
        if intent:
            parts.append(f"User intent: {intent}.")
        if knowledge:
            parts.append(f"Context:\n{knowledge[:2000]}")
        return "\n".join(parts)
