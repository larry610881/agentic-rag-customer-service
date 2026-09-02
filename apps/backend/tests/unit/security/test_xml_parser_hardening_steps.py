"""上傳 XML 防 XXE BDD Step Definitions（bandit B314 修復回歸）"""

import pytest
from pytest_bdd import parsers, scenarios, then, when

from src.infrastructure.file_parser.default_file_parser_service import (
    DefaultFileParserService,
)

scenarios("unit/security/xml_parser_hardening.feature")

_XXE = (
    '<?xml version="1.0"?>\n'
    '<!DOCTYPE root [<!ENTITY xxe SYSTEM "file:///etc/passwd">'
    '<!ENTITY lol "lollollollollol">]>\n'
    "<root>&xxe;&lol;</root>"
)


@pytest.fixture
def context():
    return {}


def _parse(text: str) -> str:
    return DefaultFileParserService()._parse_xml(text.encode("utf-8"))


@when(parsers.parse('解析 XML "{xml}"'))
def parse_ok(context, xml):
    context["result"] = _parse(xml)


@then(parsers.parse('解析結果應含 "{a}" 與 "{b}"'))
def result_contains(context, a, b):
    assert a in context["result"] and b in context["result"]


@when("解析含 DOCTYPE 實體宣告的 XML")
def parse_xxe(context):
    try:
        context["result"] = _parse(_XXE)
        context["error"] = None
    except Exception as e:  # noqa: BLE001
        context["error"] = e
        context["result"] = None


@then("應拋出 XML 解析錯誤且訊息不含實體展開內容")
def xxe_rejected(context):
    assert context["error"] is not None, context["result"]
    assert "lollol" not in str(context["error"])
    assert "root:" not in str(context["error"])
