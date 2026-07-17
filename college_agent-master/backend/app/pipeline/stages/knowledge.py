import logging
from typing import Dict, Any

from app.pipeline.base import PipelineStage

logger = logging.getLogger(__name__)


class KnowledgeRetrievalStage(PipelineStage):
    stage_name = "knowledge_retrieval"

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        request = context.get("request")
        query = request.text if request else ""
        intent = context.get("intent", "")

        if not query.strip():
            return context

        from app.services.vector_store import get_vector_store

        store = get_vector_store()
        results = store.search(query, top_k=4)
        context["knowledge"] = results
        context["knowledge_text"] = "\n".join(
            r.get("content", "") for r in (results or [])
        )
        return context
