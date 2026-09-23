"""MCP 網址與 stdio 參數的憑證遮罩（Issue #102）。

憑證正確的放法是 env_values + {KEY} 佔位符（已遮罩）；但若有人直接寫在網址或參數，
API 回應不可原樣吐出。遮罩後的值送回存檔時要保留舊值，不可把 *** 存進去。
"""

from src.domain.shared.secret_masking import (
    MASK,
    keep_if_masked,
    mask_args,
    mask_url,
)


def test_查詢參數裡像憑證的值被遮罩_其餘不動():
    url = "https://mcp.example.com/sse?api_key=sk-live-123&region=tw&access_token=abc"
    assert mask_url(url) == (
        f"https://mcp.example.com/sse?api_key={MASK}&region=tw&access_token={MASK}"
    )


def test_網址帳密段的密碼被遮罩():
    assert mask_url("https://bob:hunter2@mcp.example.com/x") == (
        f"https://bob:{MASK}@mcp.example.com/x"
    )


def test_只有帳號段的網址把整段視為憑證():
    assert mask_url("https://ghp_tokenvalue@mcp.example.com/x") == (
        f"https://{MASK}@mcp.example.com/x"
    )


def test_佔位符不遮罩_沒有憑證的網址原樣回傳():
    url = "https://mcp.example.com/sse?token={TOKEN}&q=a%20b"
    assert mask_url(url) == url
    assert mask_url("") == ""


def test_stdio_參數的三種寫法都遮罩():
    args = ["--token", "abc", "--api-key=def", "API_SECRET=ghi", "--port", "8080"]
    assert mask_args(args) == [
        "--token",
        MASK,
        f"--api-key={MASK}",
        f"API_SECRET={MASK}",
        "--port",
        "8080",
    ]


def test_stdio_參數佔位符不遮罩():
    args = ["--token", "{TOKEN}", "--api-key={API_KEY}"]
    assert mask_args(args) == args


def test_送回遮罩值時保留舊值_改過則採用新值():
    old = "https://mcp.example.com/sse?api_key=sk-live-123"
    assert keep_if_masked(mask_url(old), old, mask_url) == old
    new = "https://mcp.example.com/sse?api_key=sk-live-456"
    assert keep_if_masked(new, old, mask_url) == new
    old_args = ["--token", "abc"]
    assert keep_if_masked(mask_args(old_args), old_args, mask_args) == old_args
