"""AES-256-GCM 加密服務，支援金鑰輪替（Issue #105）。

密文格式
    ``<key_id>:<base64(nonce + ciphertext)>``；無前綴的舊密文一律視為 ``v1``。

    active 金鑰 id 是 ``v1`` 時照舊寫無前綴格式：只設 ``ENCRYPTION_MASTER_KEY`` 的
    部署行為與輪替機制上線前完全相同，新版寫入的密文在回滾到舊版後也解得開。
    第一次輪替到其他 id 之後才帶前綴。

金鑰設定
    - ``ENCRYPTION_MASTER_KEY``：目前加密用的金鑰（hex）
    - ``ENCRYPTION_MASTER_KEY_ID``：它的 id，預設 ``v1``
    - ``ENCRYPTION_PREVIOUS_KEYS``：``id:hex,id:hex``，只用來解密
    設定不合法（hex 長度、id 格式、id 重複、active 同時出現在 previous）即拋
    ``EncryptionKeyConfigError``；錯誤訊息只含 id 與長度，不含金鑰內容。
"""

from __future__ import annotations

import base64
import os
import re
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.domain.platform.services import EncryptionService

if TYPE_CHECKING:
    from src.config import Settings

LEGACY_KEY_ID = "v1"
_KEY_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")
_VALID_KEY_BYTES = (16, 24, 32)  # AES-128 / 192 / 256


class EncryptionKeyConfigError(ValueError):
    """金鑰設定不合法（啟動時應直接失敗，不可退回預設金鑰）。"""


class UnknownEncryptionKeyError(ValueError):
    """密文的金鑰 id 不在目前設定中。"""

    def __init__(self, key_id: str) -> None:
        self.key_id = key_id
        super().__init__(
            f"密文使用的金鑰 id「{key_id}」不在目前的金鑰設定中"
            "（ENCRYPTION_MASTER_KEY_ID 或 ENCRYPTION_PREVIOUS_KEYS）"
        )


def _parse_key(hex_value: str, label: str) -> bytes:
    try:
        key = bytes.fromhex(hex_value.strip())
    except ValueError:
        raise EncryptionKeyConfigError(f"{label} 不是合法的 hex 字串") from None
    if len(key) not in _VALID_KEY_BYTES:
        raise EncryptionKeyConfigError(
            f"{label} 長度為 {len(key) * 2} 個 hex 字元，"
            "須為 32 / 48 / 64（AES-128 / 192 / 256）"
        )
    return key


def _check_key_id(key_id: str, label: str) -> None:
    if not _KEY_ID_RE.match(key_id):
        raise EncryptionKeyConfigError(
            f"{label}「{key_id}」格式不合法：只允許英數與 . _ -，最長 32 字"
        )


def _parse_keyring(
    master_key: str, key_id: str, previous_keys: str
) -> dict[str, bytes]:
    _check_key_id(key_id, "ENCRYPTION_MASTER_KEY_ID")
    keys = {key_id: _parse_key(master_key, "ENCRYPTION_MASTER_KEY")}
    for raw in previous_keys.split(","):
        entry = raw.strip()
        if not entry:
            continue
        prev_id, sep, prev_hex = entry.partition(":")
        prev_id = prev_id.strip()
        if not sep:
            raise EncryptionKeyConfigError(
                f"ENCRYPTION_PREVIOUS_KEYS 的項目「{prev_id}」缺少 ':'，格式為 id:hex"
            )
        _check_key_id(prev_id, "ENCRYPTION_PREVIOUS_KEYS 的 id")
        if prev_id == key_id:
            raise EncryptionKeyConfigError(
                f"金鑰 id「{prev_id}」同時是 active（ENCRYPTION_MASTER_KEY_ID）"
                "又出現在 ENCRYPTION_PREVIOUS_KEYS"
            )
        if prev_id in keys:
            raise EncryptionKeyConfigError(
                f"ENCRYPTION_PREVIOUS_KEYS 的金鑰 id「{prev_id}」重複"
            )
        keys[prev_id] = _parse_key(
            prev_hex, f"ENCRYPTION_PREVIOUS_KEYS 的金鑰「{prev_id}」"
        )
    return keys


def split_ciphertext(ciphertext: str) -> tuple[str, str]:
    """密文 → (key_id, base64 本體)；無前綴視為 legacy v1。"""
    key_id, sep, body = ciphertext.partition(":")
    if sep and _KEY_ID_RE.match(key_id):
        return key_id, body
    return LEGACY_KEY_ID, ciphertext


class AESEncryptionService(EncryptionService):
    """AES-GCM（隨機 96-bit nonce），多金鑰解密、active 金鑰加密。"""

    def __init__(
        self,
        master_key: str,
        key_id: str = LEGACY_KEY_ID,
        previous_keys: str = "",
    ) -> None:
        self._keys = _parse_keyring(master_key, key_id, previous_keys)
        self._active_id = key_id

    @property
    def active_key_id(self) -> str:
        return self._active_id

    @property
    def key_ids(self) -> tuple[str, ...]:
        """active 在前，其餘依設定順序。"""
        return tuple(self._keys)

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        ct = AESGCM(self._keys[self._active_id]).encrypt(
            nonce, plaintext.encode(), None
        )
        body = base64.b64encode(nonce + ct).decode()
        if self._active_id == LEGACY_KEY_ID:
            return body  # 與輪替機制上線前相同的格式（回滾安全）
        return f"{self._active_id}:{body}"

    def decrypt(self, ciphertext: str) -> str:
        key_id, body = split_ciphertext(ciphertext)
        key = self._keys.get(key_id)
        if key is None:
            raise UnknownEncryptionKeyError(key_id)
        data = base64.b64decode(body)
        nonce, ct = data[:12], data[12:]
        return AESGCM(key).decrypt(nonce, ct, None).decode()

    def key_id_of(self, ciphertext: str) -> str:
        return split_ciphertext(ciphertext)[0]

    def needs_reencrypt(self, ciphertext: str) -> bool:
        return self.key_id_of(ciphertext) != self._active_id


def build_encryption_service(settings: Settings) -> AESEncryptionService:
    """由設定建立加密服務（DI container 與通知 dispatcher 共用同一份規則）。

    ENCRYPTION_MASTER_KEY 空時沿用既有的開發用全零金鑰；非 development 環境由
    Settings.validate_production_secrets 拒絕啟動。
    """
    return AESEncryptionService(
        master_key=settings.encryption_master_key or "0" * 64,
        key_id=settings.encryption_master_key_id or LEGACY_KEY_ID,
        previous_keys=settings.encryption_previous_keys or "",
    )
