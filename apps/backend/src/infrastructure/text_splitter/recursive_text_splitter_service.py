from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.domain.knowledge.entity import Chunk
from src.domain.knowledge.services import TextSplitterService
from src.domain.knowledge.value_objects import ChunkId

_CHINESE_FRIENDLY_SEPARATORS = [
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    "；",
    ".",
    " ",
    "",
]


class RecursiveTextSplitterService(TextSplitterService):
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=_CHINESE_FRIENDLY_SEPARATORS,
        )

    def split(
        self,
        text: str,
        document_id: str,
        tenant_id: str,
        content_type: str = "",
    ) -> list[Chunk]:
        texts = self._splitter.split_text(text)
        return [
            Chunk(
                id=ChunkId(),
                document_id=document_id,
                tenant_id=tenant_id,
                content=t,
                chunk_index=i,
                metadata={
                    "document_id": document_id,
                    "tenant_id": tenant_id,
                    "content_type": content_type,
                },
            )
            for i, t in enumerate(texts)
        ]
