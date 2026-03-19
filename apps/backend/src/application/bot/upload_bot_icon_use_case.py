"""Upload Bot FAB Icon Use Case."""

from dataclasses import dataclass

from src.domain.bot.file_storage_service import FileStorageService
from src.domain.bot.repository import BotRepository
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE = 256 * 1024  # 256 KB


@dataclass
class UploadBotIconCommand:
    tenant_id: str
    bot_id: str
    filename: str
    content: bytes


class UploadBotIconUseCase:
    def __init__(
        self,
        bot_repository: BotRepository,
        file_storage_service: FileStorageService,
    ) -> None:
        self._bot_repo = bot_repository
        self._file_storage = file_storage_service

    async def execute(self, command: UploadBotIconCommand) -> str:
        """Upload icon and return the URL."""
        # Validate file extension
        ext = self._extract_ext(command.filename)
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"Unsupported file type: '{ext}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )

        # Validate file size
        if len(command.content) > MAX_FILE_SIZE:
            raise ValidationError(
                f"File too large: {len(command.content)} bytes. "
                f"Maximum allowed: {MAX_FILE_SIZE} bytes"
            )

        # Find bot and verify tenant ownership
        bot = await self._bot_repo.find_by_id(command.bot_id)
        if bot is None or bot.tenant_id != command.tenant_id:
            raise EntityNotFoundError("Bot", command.bot_id)

        # Save file
        url = await self._file_storage.save_bot_icon(
            command.bot_id, command.content, ext
        )

        # Update bot entity
        bot.fab_icon_url = url
        await self._bot_repo.save(bot)

        return url

    async def delete(self, tenant_id: str, bot_id: str) -> None:
        """Delete bot icon."""
        bot = await self._bot_repo.find_by_id(bot_id)
        if bot is None or bot.tenant_id != tenant_id:
            raise EntityNotFoundError("Bot", bot_id)

        await self._file_storage.delete_bot_icon(bot_id)
        bot.fab_icon_url = ""
        await self._bot_repo.save(bot)

    @staticmethod
    def _extract_ext(filename: str) -> str:
        if "." not in filename:
            return ""
        return filename.rsplit(".", 1)[-1].lower()
