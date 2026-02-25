"""Provider Settings API 端點"""

from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.application.platform.create_provider_setting_use_case import (
    CreateProviderSettingCommand,
    CreateProviderSettingUseCase,
)
from src.application.platform.delete_provider_setting_use_case import (
    DeleteProviderSettingUseCase,
)
from src.application.platform.get_provider_setting_use_case import (
    GetProviderSettingUseCase,
)
from src.application.platform.list_provider_settings_use_case import (
    ListProviderSettingsUseCase,
)
from src.application.platform.test_provider_connection_use_case import (
    CheckProviderConnectionUseCase,
)
from src.application.platform.update_provider_setting_use_case import (
    UpdateProviderSettingCommand,
    UpdateProviderSettingUseCase,
)
from src.container import Container
from src.domain.shared.exceptions import DuplicateEntityError, EntityNotFoundError

router = APIRouter(prefix="/api/v1/settings/providers", tags=["settings"])


class ModelConfigSchema(BaseModel):
    model_id: str
    display_name: str
    is_default: bool = False


class CreateProviderSettingRequest(BaseModel):
    provider_type: str
    provider_name: str
    display_name: str
    api_key: str
    base_url: str = ""
    models: list[ModelConfigSchema] = []
    extra_config: dict[str, Any] = {}


class UpdateProviderSettingRequest(BaseModel):
    display_name: str | None = None
    is_enabled: bool | None = None
    api_key: str | None = None
    base_url: str | None = None
    models: list[ModelConfigSchema] | None = None
    extra_config: dict[str, Any] | None = None


class ProviderSettingResponse(BaseModel):
    id: str
    provider_type: str
    provider_name: str
    display_name: str
    is_enabled: bool
    has_api_key: bool
    base_url: str
    models: list[ModelConfigSchema]
    extra_config: dict[str, Any]
    created_at: str
    updated_at: str


class ConnectionResultResponse(BaseModel):
    success: bool
    latency_ms: int
    error: str = ""


def _to_response(setting) -> ProviderSettingResponse:
    return ProviderSettingResponse(
        id=setting.id.value,
        provider_type=setting.provider_type.value,
        provider_name=setting.provider_name.value,
        display_name=setting.display_name,
        is_enabled=setting.is_enabled,
        has_api_key=bool(setting.api_key_encrypted),
        base_url=setting.base_url,
        models=[
            ModelConfigSchema(
                model_id=m.model_id,
                display_name=m.display_name,
                is_default=m.is_default,
            )
            for m in setting.models
        ],
        extra_config=setting.extra_config,
        created_at=setting.created_at.isoformat(),
        updated_at=setting.updated_at.isoformat(),
    )


@router.post(
    "",
    response_model=ProviderSettingResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_provider_setting(
    body: CreateProviderSettingRequest,
    use_case: CreateProviderSettingUseCase = Depends(
        Provide[Container.create_provider_setting_use_case]
    ),
) -> ProviderSettingResponse:
    try:
        setting = await use_case.execute(
            CreateProviderSettingCommand(
                provider_type=body.provider_type,
                provider_name=body.provider_name,
                display_name=body.display_name,
                api_key=body.api_key,
                base_url=body.base_url,
                models=[m.model_dump() for m in body.models],
                extra_config=body.extra_config,
            )
        )
    except DuplicateEntityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.message,
        ) from None
    return _to_response(setting)


@router.get("", response_model=list[ProviderSettingResponse])
@inject
async def list_provider_settings(
    type: str | None = None,
    use_case: ListProviderSettingsUseCase = Depends(
        Provide[Container.list_provider_settings_use_case]
    ),
) -> list[ProviderSettingResponse]:
    settings = await use_case.execute(provider_type=type)
    return [_to_response(s) for s in settings]


@router.get("/{setting_id}", response_model=ProviderSettingResponse)
@inject
async def get_provider_setting(
    setting_id: str,
    use_case: GetProviderSettingUseCase = Depends(
        Provide[Container.get_provider_setting_use_case]
    ),
) -> ProviderSettingResponse:
    try:
        setting = await use_case.execute(setting_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from None
    return _to_response(setting)


@router.put("/{setting_id}", response_model=ProviderSettingResponse)
@inject
async def update_provider_setting(
    setting_id: str,
    body: UpdateProviderSettingRequest,
    use_case: UpdateProviderSettingUseCase = Depends(
        Provide[Container.update_provider_setting_use_case]
    ),
) -> ProviderSettingResponse:
    try:
        setting = await use_case.execute(
            UpdateProviderSettingCommand(
                setting_id=setting_id,
                display_name=body.display_name,
                is_enabled=body.is_enabled,
                api_key=body.api_key,
                base_url=body.base_url,
                models=(
                    [m.model_dump() for m in body.models]
                    if body.models is not None
                    else None
                ),
                extra_config=body.extra_config,
            )
        )
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from None
    return _to_response(setting)


@router.delete("/{setting_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_provider_setting(
    setting_id: str,
    use_case: DeleteProviderSettingUseCase = Depends(
        Provide[Container.delete_provider_setting_use_case]
    ),
) -> None:
    try:
        await use_case.execute(setting_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from None


@router.post(
    "/{setting_id}/test-connection",
    response_model=ConnectionResultResponse,
)
@inject
async def test_provider_connection(
    setting_id: str,
    use_case: CheckProviderConnectionUseCase = Depends(
        Provide[Container.check_provider_connection_use_case]
    ),
) -> ConnectionResultResponse:
    try:
        result = await use_case.execute(setting_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        ) from None
    return ConnectionResultResponse(
        success=result.success,
        latency_ms=result.latency_ms,
        error=result.error,
    )
