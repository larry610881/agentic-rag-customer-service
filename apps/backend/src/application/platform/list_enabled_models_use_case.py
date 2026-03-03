"""List all enabled models across enabled LLM providers."""

from dataclasses import dataclass

from src.domain.platform.repository import ProviderSettingRepository
from src.domain.platform.value_objects import ProviderType


@dataclass(frozen=True)
class EnabledModelDTO:
    provider_name: str
    model_id: str
    display_name: str
    price: str


class ListEnabledModelsUseCase:
    def __init__(
        self,
        provider_setting_repository: ProviderSettingRepository,
    ) -> None:
        self._repository = provider_setting_repository

    async def execute(self) -> list[EnabledModelDTO]:
        settings = await self._repository.find_all_by_type(ProviderType.LLM)
        result: list[EnabledModelDTO] = []
        for setting in settings:
            if not setting.is_enabled:
                continue
            for model in setting.models:
                if not model.is_enabled:
                    continue
                result.append(
                    EnabledModelDTO(
                        provider_name=setting.provider_name.value,
                        model_id=model.model_id,
                        display_name=model.display_name,
                        price=model.price,
                    )
                )
        return result
