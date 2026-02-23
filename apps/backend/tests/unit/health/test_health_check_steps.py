import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.application.health.health_check_use_case import (
    HealthCheckUseCase,
    HealthStatus,
)

scenarios("unit/health/health_check.feature")


@pytest.fixture
def health_repository() -> MagicMock:
    repo = MagicMock()
    repo.ping = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def use_case(health_repository: MagicMock) -> HealthCheckUseCase:
    return HealthCheckUseCase(
        health_repository=health_repository,
        version="0.1.0",
    )


@pytest.fixture
def context() -> dict:
    return {}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@given("the database is reachable")
def db_reachable(health_repository: MagicMock):
    health_repository.ping = AsyncMock(return_value=True)


@given("the database is not reachable")
def db_not_reachable(health_repository: MagicMock):
    health_repository.ping = AsyncMock(return_value=False)


@when("I perform a health check")
def perform_health_check(use_case: HealthCheckUseCase, context: dict):
    context["result"] = _run(use_case.execute())


@then(parsers.parse('the status should be "{status}"'))
def check_status(context: dict, status: str):
    result: HealthStatus = context["result"]
    assert result.status == status


@then(parsers.parse('the database status should be "{db_status}"'))
def check_database_status(context: dict, db_status: str):
    result: HealthStatus = context["result"]
    assert result.database == db_status
