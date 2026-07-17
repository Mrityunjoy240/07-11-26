import logging

from src.config.settings import settings
from src.storage.interfaces import InMemorySessionStore, SessionStore
from src.storage.redis import RedisSessionStore

logger = logging.getLogger(__name__)


def create_session_store() -> SessionStore:
    if settings.use_redis_sessions:
        logger.info("SessionStore: using Redis backend")
        return RedisSessionStore(redis_url=settings.redis_url)
    logger.info("SessionStore: using in-memory backend")
    return InMemorySessionStore()
