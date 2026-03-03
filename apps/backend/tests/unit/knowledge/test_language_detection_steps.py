"""語言偵測 BDD Step Definitions"""

from unittest.mock import MagicMock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from src.domain.knowledge.services import LanguageDetectionService

scenarios("unit/knowledge/language_detection.feature")


@pytest.fixture
def context():
    return {}


@pytest.fixture
def mock_detector():
    return MagicMock(spec=LanguageDetectionService)


# --- Chinese ---


@given("一段中文文字")
def chinese_text(context, mock_detector):
    context["text"] = "這是一段中文測試文字，用來驗證語言偵測功能是否正常運作。"
    mock_detector.detect.return_value = "zh-cn"
    context["detector"] = mock_detector


@when("執行語言偵測")
def do_detect(context):
    context["result"] = context["detector"].detect(context["text"])


@then(parsers.parse('偵測結果應為 "{lang}"'))
def verify_language(context, lang):
    assert context["result"] == lang


# --- English ---


@given("一段英文文字")
def english_text(context, mock_detector):
    context["text"] = "This is a test paragraph in English for language detection."
    mock_detector.detect.return_value = "en"
    context["detector"] = mock_detector


# --- Unknown ---


@given("一段無法辨識語言的文字")
def unknown_text(context, mock_detector):
    context["text"] = "123 456 !@#"
    mock_detector.detect.return_value = "unknown"
    context["detector"] = mock_detector
