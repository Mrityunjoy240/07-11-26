import logging
from typing import Dict, Any

from app.pipeline.base import PipelineStage

logger = logging.getLogger(__name__)


class IntentClassificationStage(PipelineStage):
    stage_name = "intent_classification"

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        request = context.get("request")
        query = request.text if request else ""

        if not query.strip():
            context["intent"] = "unknown"
            return context

        from app.services.llm.intent_classifier import get_intent_classifier

        classifier = get_intent_classifier()
        intent = classifier.classify(query)
        context["intent"] = intent
        return context
