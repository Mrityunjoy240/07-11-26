import asyncio
import logging
from typing import Dict, Any, Callable, Awaitable, List
from .interfaces import EventBus

logger = logging.getLogger(__name__)

Handler = Callable[..., Awaitable[None]]


class InMemoryEventBus(EventBus):
    """Lightweight in-memory event bus for async pub-sub within the process."""

    def __init__(self):
        self._subscribers: Dict[str, List[Handler]] = {}

    async def publish(self, event: str, data: Dict[str, Any]) -> None:
        handlers = self._subscribers.get(event, [])
        if not handlers:
            return
        logger.debug(f"Event bus: publishing '{event}' to {len(handlers)} handler(s)")
        results = await asyncio.gather(
            *[handler(event=event, data=data) for handler in handlers],
            return_exceptions=True,
        )
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(
                    f"Event bus handler #{i} for '{event}' failed: {r}",
                    exc_info=r,
                )

    def subscribe(self, event: str, handler: Handler) -> None:
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append(handler)
        logger.debug(f"Event bus: subscribed handler for '{event}'")

    def unsubscribe(self, event: str, handler: Handler) -> None:
        handlers = self._subscribers.get(event, [])
        if handler in handlers:
            handlers.remove(handler)
