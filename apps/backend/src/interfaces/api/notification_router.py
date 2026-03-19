"""Notification Channel API — admin CRUD + test."""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.application.observability.notification_use_cases import (
    CreateChannelCommand,
    CreateChannelUseCase,
    DeleteChannelUseCase,
    ListChannelsUseCase,
    SendTestNotificationUseCase,
    UpdateChannelCommand,
    UpdateChannelUseCase,
)
from src.container import Container
from src.interfaces.api.deps import require_role

router = APIRouter(
    prefix="/api/v1/admin/notification-channels",
    tags=["notification-channels"],
)


class _CreateChannelBody(BaseModel):
    channel_type: str
    name: str
    enabled: bool = False
    config: dict | None = None
    throttle_minutes: int = 15
    min_severity: str = "all"
    notify_diagnostics: bool = False
    diagnostic_severity: str = "critical"


class _UpdateChannelBody(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    config: dict | None = None
    throttle_minutes: int | None = None
    min_severity: str | None = None
    notify_diagnostics: bool | None = None
    diagnostic_severity: str | None = None


def _channel_to_dict(ch):
    return {
        "id": ch.id,
        "channel_type": ch.channel_type,
        "name": ch.name,
        "enabled": ch.enabled,
        "throttle_minutes": ch.throttle_minutes,
        "min_severity": ch.min_severity,
        "notify_diagnostics": ch.notify_diagnostics,
        "diagnostic_severity": ch.diagnostic_severity,
        "updated_at": ch.updated_at.isoformat() if ch.updated_at else None,
        "created_at": ch.created_at.isoformat() if ch.created_at else None,
    }


@router.get("")
@inject
async def list_channels(
    _: object = Depends(require_role("system_admin")),
    use_case: ListChannelsUseCase = Depends(
        Provide[Container.list_channels_use_case]
    ),
):
    channels = await use_case.execute()
    return {"items": [_channel_to_dict(ch) for ch in channels]}


@router.post("", status_code=201)
@inject
async def create_channel(
    body: _CreateChannelBody,
    _: object = Depends(require_role("system_admin")),
    use_case: CreateChannelUseCase = Depends(
        Provide[Container.create_channel_use_case]
    ),
):
    ch = await use_case.execute(
        CreateChannelCommand(
            channel_type=body.channel_type,
            name=body.name,
            enabled=body.enabled,
            config=body.config,
            throttle_minutes=body.throttle_minutes,
            min_severity=body.min_severity,
            notify_diagnostics=body.notify_diagnostics,
            diagnostic_severity=body.diagnostic_severity,
        )
    )
    return _channel_to_dict(ch)


@router.put("/{channel_id}")
@inject
async def update_channel(
    channel_id: str,
    body: _UpdateChannelBody,
    _: object = Depends(require_role("system_admin")),
    use_case: UpdateChannelUseCase = Depends(
        Provide[Container.update_channel_use_case]
    ),
):
    ch = await use_case.execute(
        UpdateChannelCommand(
            channel_id=channel_id,
            name=body.name,
            enabled=body.enabled,
            config=body.config,
            throttle_minutes=body.throttle_minutes,
            min_severity=body.min_severity,
            notify_diagnostics=body.notify_diagnostics,
            diagnostic_severity=body.diagnostic_severity,
        )
    )
    return _channel_to_dict(ch)


@router.delete("/{channel_id}", status_code=204)
@inject
async def delete_channel(
    channel_id: str,
    _: object = Depends(require_role("system_admin")),
    use_case: DeleteChannelUseCase = Depends(
        Provide[Container.delete_channel_use_case]
    ),
):
    await use_case.execute(channel_id)


@router.post("/{channel_id}/test")
@inject
async def test_channel(
    channel_id: str,
    _: object = Depends(require_role("system_admin")),
    use_case: SendTestNotificationUseCase = Depends(
        Provide[Container.test_channel_use_case]
    ),
):
    await use_case.execute(channel_id)
    return {"status": "sent"}
