"""MCP Server Registry CRUD BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.platform.mcp.create_mcp_server_use_case import (
    CreateMcpServerCommand,
    CreateMcpServerUseCase,
)
from src.application.platform.mcp.delete_mcp_server_use_case import (
    DeleteMcpServerUseCase,
)
from src.application.platform.mcp.update_mcp_server_use_case import (
    UpdateMcpServerCommand,
    UpdateMcpServerUseCase,
)
from src.domain.platform.entity import McpServerRegistration
from src.domain.platform.value_objects import McpRegistryId
from src.domain.shared.exceptions import DomainException, DuplicateEntityError

scenarios("unit/platform/mcp_server_registry.feature")


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
def mock_mcp_repo():
    repo = AsyncMock()
    repo.find_by_url = AsyncMock(return_value=None)
    repo.find_by_id = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    repo.delete = AsyncMock()
    return repo


# --- Given ---


@given("一個空的 MCP Server 註冊庫")
def empty_registry(context, mock_mcp_repo):
    context["repo"] = mock_mcp_repo
    mock_mcp_repo.find_by_url.return_value = None


@given(
    parsers.parse('一個已有 URL "{url}" 的 MCP Server 註冊庫')
)
def registry_with_existing_url(context, mock_mcp_repo, url):
    context["repo"] = mock_mcp_repo
    existing = McpServerRegistration(
        id=McpRegistryId(),
        name="existing",
        url=url,
        transport="http",
    )
    mock_mcp_repo.find_by_url.return_value = existing


@given(parsers.parse('一個已有名為 "{name}" 的 MCP Server'))
def registry_with_named_server(context, mock_mcp_repo, name):
    context["repo"] = mock_mcp_repo
    server = McpServerRegistration(
        id=McpRegistryId(value="server-1"),
        name=name,
        transport="http",
        url="http://localhost:3000/mcp",
    )
    context["server"] = server
    mock_mcp_repo.find_by_id.return_value = server


# --- When ---


@when(
    parsers.parse(
        '我建立一個 HTTP 類型的 MCP Server "{name}" 使用 URL "{url}"'
    )
)
def create_http_server(context, mock_mcp_repo, name, url):
    use_case = CreateMcpServerUseCase(mcp_server_repository=mock_mcp_repo)
    command = CreateMcpServerCommand(
        name=name, transport="http", url=url,
    )
    try:
        context["result"] = _run(use_case.execute(command))
        context["error"] = None
    except (DomainException, DuplicateEntityError) as e:
        context["result"] = None
        context["error"] = e


@when(
    parsers.parse(
        '我建立一個 stdio 類型的 MCP Server "{name}" 使用 command "{cmd}"'
    )
)
def create_stdio_server(context, mock_mcp_repo, name, cmd):
    use_case = CreateMcpServerUseCase(mcp_server_repository=mock_mcp_repo)
    command = CreateMcpServerCommand(
        name=name, transport="stdio", command=cmd, args=["-m", "server"],
    )
    try:
        context["result"] = _run(use_case.execute(command))
        context["error"] = None
    except (DomainException, DuplicateEntityError) as e:
        context["result"] = None
        context["error"] = e


@when("我建立一個 HTTP 類型的 MCP Server 但不提供 URL")
def create_http_no_url(context, mock_mcp_repo):
    use_case = CreateMcpServerUseCase(mcp_server_repository=mock_mcp_repo)
    command = CreateMcpServerCommand(
        name="no-url", transport="http", url="",
    )
    try:
        context["result"] = _run(use_case.execute(command))
        context["error"] = None
    except DomainException as e:
        context["result"] = None
        context["error"] = e


@when("我建立一個 stdio 類型的 MCP Server 但不提供 command")
def create_stdio_no_command(context, mock_mcp_repo):
    use_case = CreateMcpServerUseCase(mcp_server_repository=mock_mcp_repo)
    command = CreateMcpServerCommand(
        name="no-cmd", transport="stdio", command="",
    )
    try:
        context["result"] = _run(use_case.execute(command))
        context["error"] = None
    except DomainException as e:
        context["result"] = None
        context["error"] = e


@when(
    parsers.parse(
        '我建立一個 HTTP 類型的 MCP Server 使用相同 URL "{url}"'
    )
)
def create_duplicate_url(context, mock_mcp_repo, url):
    use_case = CreateMcpServerUseCase(mcp_server_repository=mock_mcp_repo)
    command = CreateMcpServerCommand(
        name="dup", transport="http", url=url,
    )
    try:
        context["result"] = _run(use_case.execute(command))
        context["error"] = None
    except DuplicateEntityError as e:
        context["result"] = None
        context["error"] = e


@when(parsers.parse('我更新該 Server 名稱為 "{name}"'))
def update_server_name(context, mock_mcp_repo, name):
    use_case = UpdateMcpServerUseCase(mcp_server_repository=mock_mcp_repo)
    command = UpdateMcpServerCommand(
        server_id="server-1",
        name=name,
    )
    context["result"] = _run(use_case.execute(command))


@when("我刪除該 Server")
def delete_server(context, mock_mcp_repo):
    use_case = DeleteMcpServerUseCase(mcp_server_repository=mock_mcp_repo)
    _run(use_case.execute("server-1"))
    context["deleted"] = True


# --- Then ---


@then(parsers.parse('應成功建立且 transport 為 "{transport}"'))
def created_with_transport(context, transport):
    assert context["result"] is not None
    assert context["result"].transport == transport


@then(parsers.parse('應拋出錯誤 "{message}"'))
def error_with_message(context, message):
    assert context["error"] is not None
    assert message in str(context["error"])


@then("應拋出重複錯誤")
def duplicate_error(context):
    assert context["error"] is not None
    assert isinstance(context["error"], DuplicateEntityError)


@then(parsers.parse('更新後的 Server 名稱應為 "{name}"'))
def updated_name(context, name):
    assert context["result"].name == name


@then("刪除方法應被呼叫")
def delete_called(context, mock_mcp_repo):
    mock_mcp_repo.delete.assert_called_once_with("server-1")
