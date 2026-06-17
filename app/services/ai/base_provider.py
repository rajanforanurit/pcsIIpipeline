from abc import ABC, abstractmethod
from typing import Any, Dict, List
class BaseAIProvider(ABC):
    @abstractmethod
    async def generate_questions(self, chunk: str, chunk_index: int, book_title: str, subject: str) -> List[Dict[str, Any]]:
        pass
    @abstractmethod
    async def health_check(self) -> bool:
        pass
