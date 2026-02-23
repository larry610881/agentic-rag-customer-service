"""商品搜尋 BDD Step Definitions"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_bdd import given, scenarios, then, when

from src.application.agent.product_search_use_case import ProductSearchUseCase
from src.domain.agent.value_objects import ToolResult

scenarios("unit/agent/product_search.feature")


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def context():
    return {}


@given("資料庫中有商品資料")
def products_exist(context):
    mock_service = AsyncMock()
    mock_service.search_products = AsyncMock(
        return_value=ToolResult(
            tool_name="product_search",
            success=True,
            data={
                "products": [
                    {
                        "product_id": "prod-003",
                        "category": "eletronicos",
                        "category_english": "electronics",
                        "weight_g": 500,
                    },
                ],
                "count": 1,
            },
        )
    )
    context["use_case"] = ProductSearchUseCase(product_search_service=mock_service)


@given("資料庫中無匹配商品")
def no_products(context):
    mock_service = AsyncMock()
    mock_service.search_products = AsyncMock(
        return_value=ToolResult(
            tool_name="product_search",
            success=True,
            data={"products": [], "count": 0},
        )
    )
    context["use_case"] = ProductSearchUseCase(product_search_service=mock_service)


@when('搜尋關鍵字 "electronics"')
def search_electronics(context):
    context["result"] = _run(context["use_case"].execute("electronics"))


@when('搜尋關鍵字 "nonexistent_xyz"')
def search_nonexistent(context):
    context["result"] = _run(context["use_case"].execute("nonexistent_xyz"))


@then("應回傳成功的商品搜尋結果")
def verify_success(context):
    assert context["result"].success is True


@then("結果應包含商品列表")
def verify_has_products(context):
    assert len(context["result"].data["products"]) > 0


@then("商品列表應為空")
def verify_empty_products(context):
    assert len(context["result"].data["products"]) == 0
