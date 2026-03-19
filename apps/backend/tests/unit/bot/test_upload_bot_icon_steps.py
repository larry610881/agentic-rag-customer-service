"""上傳機器人 FAB 圖示 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.bot.upload_bot_icon_use_case import (
    UploadBotIconCommand,
    UploadBotIconUseCase,
)
from src.domain.bot.entity import Bot, BotLLMParams
from src.domain.bot.file_storage_service import FileStorageService
from src.domain.bot.repository import BotRepository
from src.domain.bot.value_objects import BotId
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError

scenarios("unit/bot/upload_bot_icon.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@pytest.fixture
def mock_bot_repo():
    return AsyncMock(spec=BotRepository)


@pytest.fixture
def mock_file_storage():
    storage = AsyncMock(spec=FileStorageService)
    storage.save_bot_icon = AsyncMock(
        side_effect=lambda bot_id, content, ext: f"/static/uploads/bots/{bot_id}/fab-icon.{ext}"
    )
    storage.delete_bot_icon = AsyncMock()
    return storage


@pytest.fixture
def use_case(mock_bot_repo, mock_file_storage):
    return UploadBotIconUseCase(
        bot_repository=mock_bot_repo,
        file_storage_service=mock_file_storage,
    )


# --- Given ---


@given(parsers.parse('租戶 "{tenant_id}" 的機器人 "{bot_id}" 存在'))
def bot_exists(context, mock_bot_repo, tenant_id, bot_id):
    bot = Bot(
        id=BotId(bot_id),
        tenant_id=tenant_id,
        name="Test Bot",
        llm_params=BotLLMParams(),
    )
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)
    context["tenant_id"] = tenant_id
    context["bot_id"] = bot_id


@given(parsers.parse('租戶 "{tenant_id}" 已登入'))
def tenant_logged_in(context, tenant_id):
    context["tenant_id"] = tenant_id


@given(parsers.parse('機器人 "{bot_id}" 屬於租戶 "{owner_tenant_id}"'))
def bot_belongs_to_tenant(context, mock_bot_repo, bot_id, owner_tenant_id):
    bot = Bot(
        id=BotId(bot_id),
        tenant_id=owner_tenant_id,
        name="Test Bot",
        llm_params=BotLLMParams(),
    )
    mock_bot_repo.find_by_id = AsyncMock(return_value=bot)
    context["bot_id"] = bot_id


# --- When ---


@when(parsers.parse('上傳 PNG 圖片 "{filename}" 大小 {size_kb:d}KB'))
def upload_png(context, use_case, filename, size_kb):
    content = b"\x89PNG" + b"\x00" * (size_kb * 1024 - 4)
    command = UploadBotIconCommand(
        tenant_id=context["tenant_id"],
        bot_id=context["bot_id"],
        filename=filename,
        content=content,
    )
    try:
        context["result_url"] = _run(use_case.execute(command))
    except (ValidationError, EntityNotFoundError) as e:
        context["error"] = e


@when(parsers.parse('上傳 GIF 圖片 "{filename}"'))
def upload_gif(context, use_case, filename):
    content = b"GIF89a" + b"\x00" * 100
    command = UploadBotIconCommand(
        tenant_id=context["tenant_id"],
        bot_id=context["bot_id"],
        filename=filename,
        content=content,
    )
    try:
        _run(use_case.execute(command))
    except (ValidationError, EntityNotFoundError) as e:
        context["error"] = e


@when(parsers.parse('上傳 PNG 圖片至機器人 "{bot_id}"'))
def upload_png_to_other_bot(context, use_case, bot_id):
    content = b"\x89PNG" + b"\x00" * 100
    command = UploadBotIconCommand(
        tenant_id=context["tenant_id"],
        bot_id=bot_id,
        filename="icon.png",
        content=content,
    )
    try:
        _run(use_case.execute(command))
    except (ValidationError, EntityNotFoundError) as e:
        context["error"] = e


# --- Then ---


@then("上傳應成功")
def upload_should_succeed(context):
    assert "error" not in context
    assert context.get("result_url") is not None


@then(parsers.parse('機器人 fab_icon_url 應包含 "{expected}"'))
def fab_icon_url_contains(context, expected):
    assert expected in context["result_url"]


@then("應拋出檔案過大錯誤")
def file_too_large_error(context):
    assert isinstance(context.get("error"), ValidationError)
    assert "too large" in context["error"].message.lower()


@then("應拋出格式不支援錯誤")
def unsupported_format_error(context):
    assert isinstance(context.get("error"), ValidationError)
    assert "unsupported" in context["error"].message.lower()


@then("應拋出 EntityNotFoundError")
def entity_not_found_error(context):
    assert isinstance(context.get("error"), EntityNotFoundError)
