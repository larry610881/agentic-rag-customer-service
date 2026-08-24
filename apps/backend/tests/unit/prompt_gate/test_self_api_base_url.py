"""Regression: 影子自呼叫 base URL 不再寫死 localhost:8001（H2）。"""

import importlib
from unittest.mock import AsyncMock

import pytest


def _reload_config():
    import src.config as cfg
    return importlib.reload(cfg)


def test_default_self_api_base_url_follows_port(monkeypatch):
    monkeypatch.setenv("PORT", "8000")
    monkeypatch.delenv("SELF_API_BASE_URL", raising=False)
    cfg = _reload_config()
    assert cfg._default_self_api_base_url() == "http://localhost:8000"


def test_default_self_api_base_url_defaults_to_8000(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("SELF_API_BASE_URL", raising=False)
    cfg = _reload_config()
    # 部署（Dockerfile PORT=8000）預設，不再是本機 dev 的 8001
    assert cfg._default_self_api_base_url() == "http://localhost:8000"
    assert "8001" not in cfg._default_self_api_base_url()


def test_explicit_override_wins(monkeypatch):
    monkeypatch.setenv("SELF_API_BASE_URL", "https://api.internal:443")
    cfg = _reload_config()
    assert cfg._default_self_api_base_url() == "https://api.internal:443"


@pytest.mark.parametrize("port", ["8000", "8001", "9999"])
def test_settings_field_resolves_port(monkeypatch, port):
    monkeypatch.setenv("PORT", port)
    monkeypatch.delenv("SELF_API_BASE_URL", raising=False)
    cfg = _reload_config()
    assert cfg.Settings().self_api_base_url == f"http://localhost:{port}"


def test_use_cases_store_injected_base_url():
    """container 注入的 api_base_url 應被各 use case 採用（而非寫死預設）。"""
    from src.application.eval_dataset.eval_use_cases import (
        RunSingleEvalUseCase,
        RunValidationEvalUseCase,
    )
    from src.application.eval_dataset.run_use_cases import StartRunUseCase
    from src.application.prompt_gate.gate_run_use_cases import StartGateRunUseCase
    from src.application.prompt_gate.replay_use_cases import (
        StartReplayCompareUseCase,
    )

    url = "http://localhost:8000"
    m = AsyncMock()
    cases = [
        RunSingleEvalUseCase(eval_dataset_repository=m, api_base_url=url),
        RunValidationEvalUseCase(
            eval_dataset_repository=m, optimization_run_repository=m,
            api_base_url=url,
        ),
        StartGateRunUseCase(
            bot_repository=m, tenant_repository=m, version_repository=m,
            gate_run_repository=m, eval_dataset_repository=m, api_base_url=url,
        ),
        StartReplayCompareUseCase(
            bot_repository=m, version_repository=m, gate_run_repository=m,
            conversation_repository=m, provider_setting_repository=m,
            encryption_service=m, api_base_url=url,
        ),
        StartRunUseCase(
            eval_dataset_repository=m, run_manager=m, db_url="x",
            provider_setting_repository=m, encryption_service=m,
            api_base_url=url,
        ),
    ]
    for uc in cases:
        assert uc._api_base_url == url, type(uc).__name__
