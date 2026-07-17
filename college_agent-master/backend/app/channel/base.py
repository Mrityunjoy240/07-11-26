import logging
from typing import Dict, Any

from app.core.interfaces import ChannelAdapter

logger = logging.getLogger(__name__)


class BaseChannelAdapter(ChannelAdapter):
    """Shared base for all channel adapters with common helper methods."""

    @property
    def channel_type(self) -> str:
        raise NotImplementedError

    async def handle_message(
        self, message: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        raise NotImplementedError

    async def format_response(
        self, response: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        raise NotImplementedError

    async def enrich_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Add channel-agnostic metadata to the context."""
        context.setdefault("channel", self.channel_type)
        return context
