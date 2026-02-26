"""PII 遮蔽擴充 BDD Step Definitions"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.shared.pii_masking import mask_pii_in_text

scenarios("unit/shared/pii_masking.feature")


@pytest.fixture
def context():
    return {}


# --- Credit Card ---


@given(parsers.parse('文本包含信用卡號 "{text}"'))
def text_with_credit_card(context, text):
    context["input"] = text


@then("文本不應包含信用卡號")
def verify_no_credit_card(context):
    assert "4111" not in context["result"]
    assert "1111-1111" not in context["result"]


@then(parsers.parse('信用卡號應被替換為 "{masked}"'))
def verify_credit_card_masked(context, masked):
    assert masked in context["result"]


# --- Taiwan National ID ---


@given(parsers.parse('文本包含身分證字號 "{text}"'))
def text_with_taiwan_id(context, text):
    context["input"] = text


@then("文本不應包含身分證字號")
def verify_no_taiwan_id(context):
    assert "A123456789" not in context["result"]


@then(parsers.parse('身分證字號應被替換為 "{masked}"'))
def verify_taiwan_id_masked(context, masked):
    assert masked in context["result"]


# --- IP Address ---


@given(parsers.parse('文本包含 IP 位址 "{text}"'))
def text_with_ip(context, text):
    context["input"] = text


@then("文本不應包含 IP 位址")
def verify_no_ip(context):
    assert "192.168.1.100" not in context["result"]


@then(parsers.parse('IP 位址應被替換為 "{masked}"'))
def verify_ip_masked(context, masked):
    assert masked in context["result"]


# --- Common ---


@when("執行 PII 遮蔽")
def execute_masking(context):
    context["result"] = mask_pii_in_text(context["input"])
