from abc import ABC, abstractmethod

from src.domain.knowledge.entity import Chunk


class FileParserService(ABC):
    @abstractmethod
    def parse(self, raw_bytes: bytes, content_type: str) -> str: ...

    @abstractmethod
    def supported_types(self) -> set[str]: ...


class TextSplitterService(ABC):
    @abstractmethod
    def split(
        self,
        text: str,
        document_id: str,
        tenant_id: str,
        content_type: str = "",
    ) -> list[Chunk]: ...
