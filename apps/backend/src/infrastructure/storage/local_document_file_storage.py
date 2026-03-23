"""Local filesystem implementation of DocumentFileStorageService."""

import asyncio
import shutil
from pathlib import Path

from src.domain.knowledge.services import DocumentFileStorageService


class LocalDocumentFileStorageService(DocumentFileStorageService):
    def __init__(self, base_dir: str = "static/uploads/documents") -> None:
        self._base_dir = Path(base_dir)

    async def save(
        self, tenant_id: str, document_id: str, content: bytes, filename: str
    ) -> str:
        target_dir = self._base_dir / tenant_id / document_id
        await asyncio.to_thread(target_dir.mkdir, parents=True, exist_ok=True)
        target_path = target_dir / filename
        await asyncio.to_thread(target_path.write_bytes, content)
        return f"{tenant_id}/{document_id}/{filename}"

    async def load(self, storage_path: str) -> bytes:
        full_path = self._base_dir / storage_path
        return await asyncio.to_thread(full_path.read_bytes)

    async def delete(self, storage_path: str) -> None:
        # Delete the document directory (tenant_id/document_id/)
        doc_dir = self._base_dir / Path(storage_path).parent
        if doc_dir.exists():
            await asyncio.to_thread(shutil.rmtree, doc_dir)
