import logging
from typing import Dict, Any, Type, Optional

logger = logging.getLogger(__name__)


class Container:
    """Simple dependency injection container.

    Services are registered lazily or eagerly. The container supports
    both singletons (single instance) and factories (callable returning instance).
    """

    def __init__(self):
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Type] = {}

    def register_singleton(self, key: str, instance: Any) -> None:
        """Register an existing instance as a singleton."""
        self._singletons[key] = instance
        logger.debug(f"DI: registered singleton '{key}'")

    def register_factory(self, key: str, factory: Type) -> None:
        """Register a factory class (instantiated lazily on first get)."""
        self._factories[key] = factory

    def get(self, key: str, **kwargs) -> Optional[Any]:
        """Retrieve a service by key. Factories are instantiated once."""
        if key in self._singletons:
            return self._singletons[key]
        if key in self._factories:
            instance = self._factories[key](**kwargs)
            self._singletons[key] = instance
            logger.debug(f"DI: instantiated factory '{key}'")
            return instance
        return None

    def has(self, key: str) -> bool:
        return key in self._singletons or key in self._factories


# Global container instance
container = Container()
