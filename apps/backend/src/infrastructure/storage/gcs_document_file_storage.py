"""Google Cloud Storage implementation of DocumentFileStorageService."""

import asyncio

from src.domain.knowledge.services import DocumentFileStorageService


class GCSDocumentFileStorageService(DocumentFileStorageService):
    def __init__(self, bucket_name: str) -> None:
        self._bucket_name = bucket_name
        self._client = None

    def _get_bucket(self):
        if self._client is None:
            from google.cloud import storage

            self._client = storage.Client()
        return self._client.bucket(self._bucket_name)

    async def save(
        self, tenant_id: str, document_id: str, content: bytes, filename: str
    ) -> str:
        blob_path = f"{tenant_id}/{document_id}/{filename}"
        bucket = self._get_bucket()
        blob = bucket.blob(blob_path)
        await asyncio.to_thread(blob.upload_from_string, content)
        return blob_path

    async def load(self, storage_path: str) -> bytes:
        bucket = self._get_bucket()
        blob = bucket.blob(storage_path)
        return await asyncio.to_thread(blob.download_as_bytes)

    async def delete(self, storage_path: str) -> None:
        bucket = self._get_bucket()
        blob = bucket.blob(storage_path)
        exists = await asyncio.to_thread(blob.exists)
        if exists:
            await asyncio.to_thread(blob.delete)
