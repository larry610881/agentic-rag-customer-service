"""Excel 解析 BDD Step Definitions"""

import io

import pytest
from pytest_bdd import given, scenarios, then, when

from src.infrastructure.file_parser.default_file_parser_service import (
    DefaultFileParserService,
)

scenarios("unit/knowledge/excel_parsing.feature")


@pytest.fixture
def context():
    return {}


@pytest.fixture
def parser():
    return DefaultFileParserService()


def _create_xlsx(sheets: dict[str, list[list[object]]]) -> bytes:
    """Helper to create XLSX bytes from a dict of sheet_name → rows."""
    from openpyxl import Workbook

    wb = Workbook()
    first = True
    for name, rows in sheets.items():
        if first:
            ws = wb.active
            ws.title = name
            first = False
        else:
            ws = wb.create_sheet(title=name)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


XLSX_MIME = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


# --- Single sheet ---


@given("一個單一 sheet 的 XLSX 檔案")
def single_sheet_xlsx(context):
    context["raw"] = _create_xlsx(
        {"Products": [["Name", "Price"], ["Widget", 9.99], ["Gadget", 19.99]]}
    )


@when("解析 XLSX 檔案")
def do_parse(context, parser):
    context["result"] = parser.parse(context["raw"], XLSX_MIME)


@then("應回傳包含 sheet 標記的文字")
def verify_sheet_marker(context):
    assert "[Sheet: Products]" in context["result"]
    assert "Widget" in context["result"]
    assert "9.99" in context["result"]


# --- Multi sheet ---


@given("一個多 sheet 的 XLSX 檔案")
def multi_sheet_xlsx(context):
    context["raw"] = _create_xlsx(
        {
            "Orders": [["ID", "Total"], [1, 100]],
            "Items": [["Name", "Qty"], ["Apple", 5]],
        }
    )


@then("應回傳所有 sheet 的內容")
def verify_multi_sheets(context):
    assert "[Sheet: Orders]" in context["result"]
    assert "[Sheet: Items]" in context["result"]
    assert "Apple" in context["result"]


# --- Empty sheet skipped ---


@given("一個包含空 sheet 的 XLSX 檔案")
def xlsx_with_empty_sheet(context):
    context["raw"] = _create_xlsx(
        {
            "Data": [["A", "B"], [1, 2]],
            "Empty": [],
        }
    )


@then("空 sheet 應被跳過")
def verify_empty_skipped(context):
    assert "[Sheet: Data]" in context["result"]
    assert "[Sheet: Empty]" not in context["result"]
