import logging
from typing import Dict, Any

from app.pipeline.base import PipelineStage

logger = logging.getLogger(__name__)


class LanguageDetectionStage(PipelineStage):
    stage_name = "language_detection"

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        request = context.get("request")
        query = request.text if request else ""

        if not query.strip():
            context["language"] = "en"
            return context

        from app.utils.language_detect import detect_language
        lang = detect_language(query)
        context["language"] = lang
        return context
