"""PII 遮蔽工具"""

import re


def mask_user_id(user_id: str | None) -> str:
    """遮蔽 user ID，保留前 3 後 3 字元。"""
    if not user_id:
        return "***"
    if len(user_id) <= 6:
        return "***"
    return f"{user_id[:3]}***{user_id[-3:]}"


def mask_pii_in_text(text: str | None) -> str:
    """遮蔽文本中的 PII（email, phone, LINE user ID）。"""
    if not text:
        return ""
    # Mask email addresses
    text = re.sub(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "***@***.***",
        text,
    )
    # Mask phone numbers (Taiwan format)
    text = re.sub(r"09\d{8}", "09***", text)
    # Mask LINE user IDs (U + 32 hex)
    text = re.sub(r"U[0-9a-f]{32}", "U***", text)
    return text
