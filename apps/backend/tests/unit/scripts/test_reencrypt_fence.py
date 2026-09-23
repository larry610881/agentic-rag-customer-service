"""圍籬（Issue #105）：程式裡每個寫入密文的地方都必須登記在重新加密腳本。

新增一個 `.encrypt(` 呼叫卻沒登記進 scripts/reencrypt_secrets.py 的 ENCRYPTED_FIELDS
（寫進 DB）或 CACHE_ONLY_WRITERS（只寫 Redis 快取）→ 本測試紅燈。否則輪替金鑰後
重新加密會漏掉那個欄位，移除舊金鑰時資料就永久解不開。
"""

import ast
from pathlib import Path

from scripts.reencrypt_secrets import CACHE_ONLY_WRITERS, ENCRYPTED_FIELDS

SRC = Path(__file__).resolve().parents[3] / "src"
# 加密服務本身（AESGCM.encrypt）不是「寫入密文的欄位」
_EXCLUDED = {"infrastructure/crypto/aes_encryption_service.py"}


def _files_calling_encrypt() -> set[str]:
    found = set()
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC).as_posix()
        if rel in _EXCLUDED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "encrypt"
            ):
                found.add(rel)
                break
    return found


def _declared_db_writers() -> set[str]:
    return {w for f in ENCRYPTED_FIELDS for w in f.writers}


def test_每個加密呼叫點都登記在重新加密腳本():
    undeclared = sorted(
        _files_calling_encrypt() - _declared_db_writers() - set(CACHE_ONLY_WRITERS)
    )
    assert undeclared == [], (
        "這些檔案會寫入密文，但沒登記在 scripts/reencrypt_secrets.py 的 "
        f"ENCRYPTED_FIELDS 或 CACHE_ONLY_WRITERS：{undeclared}"
    )


def test_登記的寫入點都還存在_清單不過期():
    calling = _files_calling_encrypt()
    stale = sorted((_declared_db_writers() | set(CACHE_ONLY_WRITERS)) - calling)
    assert stale == [], f"登記了但已不再呼叫 encrypt 的檔案：{stale}"


def test_快取例外都寫了理由_且不與_DB_欄位重疊():
    assert all(len(reason) >= 10 for reason in CACHE_ONLY_WRITERS.values())
    assert not (set(CACHE_ONLY_WRITERS) & _declared_db_writers())


def test_掃描器真的有找到呼叫點():
    assert len(_files_calling_encrypt()) >= 5
