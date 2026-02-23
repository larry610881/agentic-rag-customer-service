from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import Settings


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        postgres_host="localhost",
        postgres_port=5432,
        postgres_user="test",
        postgres_password="test",
        postgres_db="test_db",
        app_version="0.1.0",
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_health_repository() -> MagicMock:
    repo = MagicMock()
    repo.ping = AsyncMock(return_value=True)
    return repo
