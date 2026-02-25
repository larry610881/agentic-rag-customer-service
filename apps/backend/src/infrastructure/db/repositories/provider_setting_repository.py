from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.platform.entity import ProviderSetting
from src.domain.platform.repository import ProviderSettingRepository
from src.domain.platform.value_objects import (
    ModelConfig,
    ProviderName,
    ProviderSettingId,
    ProviderType,
)
from src.infrastructure.db.models.provider_setting_model import (
    ProviderSettingModel,
)


class SQLAlchemyProviderSettingRepository(ProviderSettingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: ProviderSettingModel) -> ProviderSetting:
        models = [
            ModelConfig(
                model_id=m["model_id"],
                display_name=m["display_name"],
                is_default=m.get("is_default", False),
            )
            for m in (model.models or [])
        ]
        return ProviderSetting(
            id=ProviderSettingId(value=model.id),
            provider_type=ProviderType(model.provider_type),
            provider_name=ProviderName(model.provider_name),
            display_name=model.display_name,
            is_enabled=model.is_enabled,
            api_key_encrypted=model.api_key_encrypted,
            base_url=model.base_url,
            models=models,
            extra_config=model.extra_config or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, setting: ProviderSetting) -> None:
        models_data = [
            {
                "model_id": m.model_id,
                "display_name": m.display_name,
                "is_default": m.is_default,
            }
            for m in setting.models
        ]

        existing = await self._session.get(ProviderSettingModel, setting.id.value)
        if existing:
            existing.provider_type = setting.provider_type.value
            existing.provider_name = setting.provider_name.value
            existing.display_name = setting.display_name
            existing.is_enabled = setting.is_enabled
            existing.api_key_encrypted = setting.api_key_encrypted
            existing.base_url = setting.base_url
            existing.models = models_data
            existing.extra_config = setting.extra_config
            existing.updated_at = setting.updated_at
        else:
            model = ProviderSettingModel(
                id=setting.id.value,
                provider_type=setting.provider_type.value,
                provider_name=setting.provider_name.value,
                display_name=setting.display_name,
                is_enabled=setting.is_enabled,
                api_key_encrypted=setting.api_key_encrypted,
                base_url=setting.base_url,
                models=models_data,
                extra_config=setting.extra_config,
                created_at=setting.created_at,
                updated_at=setting.updated_at,
            )
            self._session.add(model)
        await self._session.commit()

    async def find_by_id(self, setting_id: str) -> ProviderSetting | None:
        stmt = select(ProviderSettingModel).where(
            ProviderSettingModel.id == setting_id
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_type_and_name(
        self, provider_type: ProviderType, provider_name: ProviderName
    ) -> ProviderSetting | None:
        stmt = select(ProviderSettingModel).where(
            ProviderSettingModel.provider_type == provider_type.value,
            ProviderSettingModel.provider_name == provider_name.value,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_all_by_type(
        self, provider_type: ProviderType
    ) -> list[ProviderSetting]:
        stmt = (
            select(ProviderSettingModel)
            .where(ProviderSettingModel.provider_type == provider_type.value)
            .order_by(ProviderSettingModel.created_at)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_all(self) -> list[ProviderSetting]:
        stmt = select(ProviderSettingModel).order_by(
            ProviderSettingModel.provider_type,
            ProviderSettingModel.created_at,
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def delete(self, setting_id: str) -> None:
        existing = await self._session.get(ProviderSettingModel, setting_id)
        if existing:
            await self._session.delete(existing)
            await self._session.commit()
