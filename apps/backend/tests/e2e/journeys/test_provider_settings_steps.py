"""E2E Journey: Provider Settings 管理流程"""

import pytest
from pytest_bdd import parsers, scenarios, then, when

scenarios("e2e/provider_settings.feature")


@pytest.fixture
def ctx():
    return {}


@when(
    parsers.parse(
        '我建立 Provider 類型 "{ptype}" 名稱 "{pname}" 顯示名稱 "{display}"'
    )
)
def create_provider(ctx, client, ptype, pname, display):
    ctx["response"] = client.post(
        "/api/v1/settings/providers",
        json={
            "provider_type": ptype,
            "provider_name": pname,
            "display_name": display,
            "api_key": "sk-e2e-test",
        },
    )
    if ctx["response"].status_code == 201:
        ctx.setdefault("provider_ids", []).append(ctx["response"].json()["id"])


@when("我查詢所有 Provider")
def list_all(ctx, client):
    ctx["response"] = client.get("/api/v1/settings/providers")


@when(parsers.parse('我篩選類型 "{ptype}" 的 Provider'))
def filter_by_type(ctx, client, ptype):
    ctx["response"] = client.get(f"/api/v1/settings/providers?type={ptype}")


@when(parsers.parse('我更新第一個 Provider 顯示名稱為 "{display}"'))
def update_first(ctx, client, display):
    ctx["response"] = client.put(
        f"/api/v1/settings/providers/{ctx['provider_ids'][0]}",
        json={"display_name": display},
    )


@when("我刪除第一個 Provider")
def delete_first(ctx, client):
    ctx["response"] = client.delete(
        f"/api/v1/settings/providers/{ctx['provider_ids'][0]}"
    )


@then(parsers.parse("回應狀態碼為 {code:d}"))
def check_status(ctx, code):
    assert ctx["response"].status_code == code, (
        f"Expected {code}, got {ctx['response'].status_code}: "
        f"{ctx['response'].text}"
    )


@then(parsers.parse('Provider 名稱為 "{name}"'))
def check_name(ctx, name):
    assert ctx["response"].json()["provider_name"] == name


@then(parsers.parse("Provider 列表有 {count:d} 個"))
def check_count(ctx, count):
    assert len(ctx["response"].json()) == count


@then(parsers.parse('顯示名稱為 "{display}"'))
def check_display(ctx, display):
    assert ctx["response"].json()["display_name"] == display
