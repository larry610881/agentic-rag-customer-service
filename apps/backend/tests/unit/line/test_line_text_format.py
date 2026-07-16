"""LINE 出口 Markdown strip 安全網測試（POC 問題 4）。

LINE 是純文字通路，LLM 輸出的 Markdown 符號會原樣顯示給使用者。
Prompt 已加格式約束，此 util 為第二層保險。
"""
from src.application.line._text_format import strip_markdown_for_line


def test_strip_bold_markers():
    result = strip_markdown_for_line("**板橋店有百元理髮店服務**")
    assert result == "板橋店有百元理髮店服務"


def test_strip_bold_inline():
    text = "成為 **VIP 會員** 需累積消費滿 **10萬元**"
    assert strip_markdown_for_line(text) == "成為 VIP 會員 需累積消費滿 10萬元"


def test_strip_heading_hashes():
    result = strip_markdown_for_line("### 目前可確認的資訊\n內容")
    assert result == "目前可確認的資訊\n內容"


def test_list_markers_converted_to_bullet():
    text = "- 第一點\n- 第二點\n* 第三點"
    assert strip_markdown_for_line(text) == "・第一點\n・第二點\n・第三點"


def test_markdown_link_unwrapped_keeps_url():
    """WP-B1 允許輸出知識庫連結後，模型可能用 markdown link 語法 — 保留文字與 URL。"""
    text = "詳見 [綁定教學](https://www.carrefour.com.tw/carrefourapp/)"
    assert strip_markdown_for_line(text) == (
        "詳見 綁定教學 https://www.carrefour.com.tw/carrefourapp/"
    )


def test_inline_code_backticks_removed():
    assert strip_markdown_for_line("輸入 `94歡迎` 折扣碼") == "輸入 94歡迎 折扣碼"


def test_plain_url_untouched():
    text = "官網：https://www.carrefour.com.tw/?lang=zh"
    assert strip_markdown_for_line(text) == text


def test_math_asterisk_untouched():
    """單一星號（非成對粗體）不可誤刪 — 例如乘法。"""
    text = "3*5=15 元"
    assert strip_markdown_for_line(text) == text


def test_plain_text_untouched():
    text = "您好，板橋店設有百元理髮服務。\n\n營業時間為 09:00-22:00。"
    assert strip_markdown_for_line(text) == text
