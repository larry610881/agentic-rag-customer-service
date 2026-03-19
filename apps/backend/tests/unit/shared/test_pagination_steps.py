"""共用分頁 BDD Step Definitions"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.shared.pagination import PaginatedResult, PaginationParams

scenarios("unit/shared/pagination.feature")


@pytest.fixture
def context():
    return {}


@given(parsers.parse("有 {count:d} 筆機器人資料"))
def setup_data(context, count):
    context["items"] = list(range(count))
    context["total"] = count


@when(parsers.parse("查詢第 {page:d} 頁每頁 {page_size:d} 筆"))
def query_page(context, page, page_size):
    params = PaginationParams(page=page, page_size=page_size)
    all_items = context["items"]
    sliced = all_items[params.offset : params.offset + params.page_size]
    context["result"] = PaginatedResult(
        items=sliced,
        total=context["total"],
        page=params.page,
        page_size=params.page_size,
    )


@then(parsers.parse("應回傳 {count:d} 筆資料"))
def verify_count(context, count):
    assert len(context["result"].items) == count


@then(parsers.parse("total 為 {total:d}"))
def verify_total(context, total):
    assert context["result"].total == total


@then(parsers.parse("total_pages 為 {pages:d}"))
def verify_total_pages(context, pages):
    assert context["result"].total_pages == pages
