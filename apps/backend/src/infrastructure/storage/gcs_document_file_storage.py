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

    async def get_preview_url(
        self, storage_path: str, expiry_seconds: int = 300
    ) -> str | None:
        from datetime import timedelta

        import google.auth
        from google.auth.transport import requests as auth_requests

        bucket = self._get_bucket()
        blob = bucket.blob(storage_path)

        credentials, _ = google.auth.default()
        if not credentials.valid:
            credentials.refresh(auth_requests.Request())

        sa_email = getattr(credentials, "service_account_email", "")

        url = await asyncio.to_thread(
            blob.generate_signed_url,
            version="v4",
            expiration=timedelta(seconds=expiry_seconds),
            service_account_email=sa_email,
            access_token=credentials.token,
        )
        return url

    async def generate_upload_signed_url(
        self,
        tenant_id: str,
        document_id: str,
        filename: str,
        content_type: str = "application/octet-stream",
        expiry_seconds: int = 600,
    ) -> str:
        from datetime import timedelta

        import google.auth
        from google.auth.transport import requests as auth_requests

        blob_path = f"{tenant_id}/{document_id}/{filename}"
        bucket = self._get_bucket()
        blob = bucket.blob(blob_path)

        credentials, _ = google.auth.default()
        if not credentials.valid:
            credentials.refresh(auth_requests.Request())

        sa_email = getattr(credentials, "service_account_email", "")

        url = await asyncio.to_thread(
            blob.generate_signed_url,
            version="v4",
            expiration=timedelta(seconds=expiry_seconds),
            method="PUT",
            content_type=content_type,
            service_account_email=sa_email,
            access_token=credentials.token,
        )
        return url
