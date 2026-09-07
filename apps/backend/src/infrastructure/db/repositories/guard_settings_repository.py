from src.domain.security.guard_stages import GuardSettings, GuardSettingsRepository
from src.infrastructure.db.models.guard_settings_model import GuardSettingsModel
from src.infrastructure.db.repositories._layered_settings_repository import (
    SQLAlchemyLayeredSettingsRepository,
)


class SQLAlchemyGuardSettingsRepository(
    SQLAlchemyLayeredSettingsRepository, GuardSettingsRepository
):
    """Issue #75：guard_settings 表（欄位與 abuse_settings 相同，共用實作）。"""

    model_cls = GuardSettingsModel
    entity_cls = GuardSettings

    async def get(self, scope_kind: str, scope_id: str) -> GuardSettings | None:
        return await super().get(scope_kind, scope_id)

    async def save(self, settings: GuardSettings) -> None:
        await super().save(settings)

    async def list_profiles(self) -> list[GuardSettings]:
        return await super().list_profiles()
