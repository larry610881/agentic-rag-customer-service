"""flex_contact_builder 單元測試 — 外部瀏覽器開啟參數（POC 問題 2）。

Android 的 LINE in-app WebView 不會彈出電話/麥克風授權視窗，
導致客服頁的網路電話卡住。LINE 官方支援 `openExternalBrowser=1`
query 參數強制以外部瀏覽器開啟 → 授權彈窗正常出現。
"""
from src.infrastructure.line.flex_contact_builder import build_contact_flex


def _action_uri(flex: dict) -> str:
    return flex["footer"]["contents"][0]["action"]["uri"]


def test_url_type_appends_open_external_browser():
    """url 型別按鈕必須附加 openExternalBrowser=1（無既有 query string）。"""
    flex = build_contact_flex(
        {"label": "轉接真人客服", "url": "https://example.com/support", "type": "url"}
    )
    assert _action_uri(flex) == "https://example.com/support?openExternalBrowser=1"


def test_url_with_existing_query_appends_with_ampersand():
    """既有 query string 時用 & 拼接，不可產生兩個 ?。"""
    flex = build_contact_flex(
        {"label": "客服", "url": "https://example.com/support?lang=zh", "type": "url"}
    )
    uri = _action_uri(flex)
    assert uri == "https://example.com/support?lang=zh&openExternalBrowser=1"
    assert uri.count("?") == 1


def test_phone_type_does_not_append_param():
    """tel: 直撥不是網頁，不可附加 openExternalBrowser 參數。"""
    flex = build_contact_flex(
        {"label": "撥打客服", "url": "0800123456", "type": "phone"}
    )
    uri = _action_uri(flex)
    assert uri == "tel:0800123456"
    assert "openExternalBrowser" not in uri


def test_url_already_has_param_not_duplicated():
    """URL 已含 openExternalBrowser=1 時不可重複附加。"""
    flex = build_contact_flex(
        {
            "label": "客服",
            "url": "https://example.com/support?openExternalBrowser=1",
            "type": "url",
        }
    )
    assert _action_uri(flex).count("openExternalBrowser") == 1


def test_label_truncated_to_20_chars():
    """LINE 按鈕 label 上限 20 字元（既有行為防護）。"""
    flex = build_contact_flex(
        {"label": "很長的標籤" * 10, "url": "https://example.com", "type": "url"}
    )
    assert len(flex["footer"]["contents"][0]["action"]["label"]) <= 20
