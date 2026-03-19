"""Local file system implementation of FileStorageService."""

import shutil
from pathlib import Path

from src.domain.bot.file_storage_service import FileStorageService


class LocalFileStorageService(FileStorageService):
    def __init__(self, base_dir: str = "static/uploads") -> None:
        self._base_dir = Path(base_dir)

    async def save_bot_icon(self, bot_id: str, content: bytes, ext: str) -> str:
        target_dir = self._base_dir / "bots" / bot_id
        target_dir.mkdir(parents=True, exist_ok=True)

        filename = f"fab-icon.{ext}"
        target_path = target_dir / filename
        target_path.write_bytes(content)

        return f"/static/uploads/bots/{bot_id}/{filename}"

    async def delete_bot_icon(self, bot_id: str) -> None:
        target_dir = self._base_dir / "bots" / bot_id
        if target_dir.exists():
            shutil.rmtree(target_dir)
