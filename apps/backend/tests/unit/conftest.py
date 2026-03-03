"""Unit test conftest — safety net to prevent accidental DB usage."""

import pytest


@pytest.fixture
def db_session():
    raise RuntimeError(
        "Unit tests must NOT use db_session. "
        "Use AsyncMock to mock the repository layer."
    )
