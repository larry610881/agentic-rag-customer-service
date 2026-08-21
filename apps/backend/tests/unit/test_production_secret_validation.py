"""Regression: 非 development 環境拒絕預設密鑰（M24）。"""

from src.config import Settings

_DEV_JWT = "dev-secret-key-change-in-production"


def test_development_skips_check():
    s = Settings(app_env="development", jwt_secret_key=_DEV_JWT,
                 encryption_master_key="")
    assert s.validate_production_secrets() == []


def test_production_default_jwt_flagged():
    s = Settings(app_env="production", jwt_secret_key=_DEV_JWT,
                 encryption_master_key="realkey")
    problems = s.validate_production_secrets()
    assert any("JWT_SECRET_KEY" in p for p in problems)


def test_production_missing_encryption_key_flagged():
    s = Settings(app_env="production", jwt_secret_key="a-real-secret",
                 encryption_master_key="")
    problems = s.validate_production_secrets()
    assert any("ENCRYPTION_MASTER_KEY" in p for p in problems)


def test_production_with_real_secrets_ok():
    s = Settings(app_env="production", jwt_secret_key="a-real-secret",
                 encryption_master_key="a-real-master-key")
    assert s.validate_production_secrets() == []
