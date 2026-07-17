import logging
from typing import Dict, Any

from app.core.interfaces import ConversationStage

logger = logging.getLogger(__name__)


class PipelineStage(ConversationStage):
    """Base class for all processing stages in the conversation pipeline.

    Each stage receives the full context dict, processes one concern,
    and returns the mutated context. Stages are composed in a sequence
    by the ConversationRouter.
    """

    stage_name: str = "unnamed_stage"

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError
