from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class BaseLLMService(ABC):
    @abstractmethod
    async def generate_response(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def stream_response(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ):
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass
