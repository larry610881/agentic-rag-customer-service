from src.domain.abuse.settings import AbuseSettings, AbuseSettingsRepository
from src.infrastructure.db.models.abuse_settings_model import AbuseSettingsModel
from src.infrastructure.db.repositories._layered_settings_repository import (
    SQLAlchemyLayeredSettingsRepository,
)


class SQLAlchemyAbuseSettingsRepository(
    SQLAlchemyLayeredSettingsRepository, AbuseSettingsRepository
):
    """Issue #68 P7c：abuse_settings 表；Issue #75 起與 guard_settings 共用實作。"""

    model_cls = AbuseSettingsModel
    entity_cls = AbuseSettings

    async def get(self, scope_kind: str, scope_id: str) -> AbuseSettings | None:
        return await super().get(scope_kind, scope_id)

    async def save(self, settings: AbuseSettings) -> None:
        await super().save(settings)

    async def list_profiles(self) -> list[AbuseSettings]:
        return await super().list_profiles()
