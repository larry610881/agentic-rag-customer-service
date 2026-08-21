"""Regression: validate/replay 端點把 refresh_token 傳給背景任務（H3）。"""

from unittest.mock import AsyncMock

from dependency_injector import providers

from src.domain.prompt_gate.gate_run_entity import PromptGateRun


def _admin_hdr(app):
    token = app.container.jwt_service().create_user_token(
        user_id="ta", tenant_id="t-h3", role="tenant_admin"
    )
    return {"Authorization": f"Bearer {token}"}


def test_validate_forwards_refresh_token(client, app):
    spy = AsyncMock()
    spy.execute = AsyncMock(return_value=PromptGateRun())
    app.container.start_gate_run_use_case.override(providers.Object(spy))
    try:
        resp = client.post(
            "/api/v1/bots/bot-x/config-versions/ver-x/validate",
            json={"refresh_token": "rt-abc"},
            headers=_admin_hdr(app),
        )
        assert resp.status_code == 202, resp.text
    finally:
        app.container.start_gate_run_use_case.reset_override()
    assert spy.execute.await_args.kwargs["refresh_token"] == "rt-abc"


def test_replay_forwards_refresh_token(client, app):
    spy = AsyncMock()
    spy.execute = AsyncMock(return_value=PromptGateRun())
    app.container.start_replay_compare_use_case.override(providers.Object(spy))
    try:
        resp = client.post(
            "/api/v1/bots/bot-x/config-versions/ver-x/replay-compare",
            json={"sample_size": 5, "refresh_token": "rt-xyz"},
            headers=_admin_hdr(app),
        )
        assert resp.status_code == 202, resp.text
    finally:
        app.container.start_replay_compare_use_case.reset_override()
    assert spy.execute.await_args.kwargs["refresh_token"] == "rt-xyz"


def test_validate_without_refresh_token_defaults_empty(client, app):
    spy = AsyncMock()
    spy.execute = AsyncMock(return_value=PromptGateRun())
    app.container.start_gate_run_use_case.override(providers.Object(spy))
    try:
        resp = client.post(
            "/api/v1/bots/bot-x/config-versions/ver-x/validate",
            headers=_admin_hdr(app),
        )
        assert resp.status_code == 202, resp.text
    finally:
        app.container.start_gate_run_use_case.reset_override()
    assert spy.execute.await_args.kwargs["refresh_token"] == ""
