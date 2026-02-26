"""Content-Aware 分塊路由 BDD Step Definitions"""

from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.knowledge.services import TextSplitterService
from src.infrastructure.text_splitter.content_aware_text_splitter_service import (
    ContentAwareTextSplitterService,
)

scenarios("unit/knowledge/content_aware_chunking.feature")


@pytest.fixture
def ctx():
    return {}


@given("一個 ContentAwareTextSplitterService 有 CSV 策略和 default 策略")
def setup_router(ctx):
    csv_strategy = MagicMock(spec=TextSplitterService)
    csv_strategy.split.return_value = []
    default_strategy = MagicMock(spec=TextSplitterService)
    default_strategy.split.return_value = []

    ctx["csv_strategy"] = csv_strategy
    ctx["default_strategy"] = default_strategy
    ctx["router"] = ContentAwareTextSplitterService(
        strategies={"text/csv": csv_strategy},
        default=default_strategy,
    )


@when(parsers.parse('以 content_type "{ct}" 執行分塊'))
def do_route(ctx, ct):
    ctx["router"].split("some text", "doc-1", "tenant-1", content_type=ct)


@then("CSV 策略被呼叫")
def csv_called(ctx):
    ctx["csv_strategy"].split.assert_called_once()


@then("CSV 策略未被呼叫")
def csv_not_called(ctx):
    ctx["csv_strategy"].split.assert_not_called()


@then("default 策略被呼叫")
def default_called(ctx):
    ctx["default_strategy"].split.assert_called_once()


@then("default 策略未被呼叫")
def default_not_called(ctx):
    ctx["default_strategy"].split.assert_not_called()
