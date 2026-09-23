"""加密金鑰輪替（Issue #105 B10）。

密文格式：`<key_id>:<base64>`；無前綴＝legacy，以 v1 解密。active 為 v1 時照舊寫
無前綴格式，讓「只設 ENCRYPTION_MASTER_KEY」的行為與輪替前完全相同，
而且新版寫入的密文在回滾到舊版後仍解得開（B9 回滾）。
"""

import base64

import pytest

from src.infrastructure.crypto.aes_encryption_service import (
    AESEncryptionService,
    EncryptionKeyConfigError,
    UnknownEncryptionKeyError,
)

K1 = "11" * 32
K2 = "22" * 32
K3 = "33" * 16  # AES-128，仍是合法長度


# ---- 向後相容：只設舊的一個變數 ----


def test_只設一把金鑰時寫出與舊版相同的無前綴密文():
    svc = AESEncryptionService(master_key=K1)
    ct = svc.encrypt("secret")
    assert ":" not in ct
    base64.b64decode(ct, validate=True)  # 純 base64，舊版程式讀得懂
    assert svc.decrypt(ct) == "secret"


def test_舊版產生的無前綴密文照樣解得開():
    legacy = AESEncryptionService(master_key=K1).encrypt("old")
    assert AESEncryptionService(master_key=K1, key_id="v1").decrypt(legacy) == "old"


# ---- 輪替 ----


def test_active_非_v1_時寫出帶前綴的密文():
    svc = AESEncryptionService(master_key=K2, key_id="v2", previous_keys=f"v1:{K1}")
    ct = svc.encrypt("secret")
    assert ct.startswith("v2:")
    assert svc.decrypt(ct) == "secret"


def test_輪替後仍能以_previous_解開_legacy_與舊_id_密文():
    legacy = AESEncryptionService(master_key=K1).encrypt("a")
    v3_ct = AESEncryptionService(
        master_key=K3, key_id="v3", previous_keys=f"v1:{K1}"
    ).encrypt("b")
    svc = AESEncryptionService(
        master_key=K2, key_id="v2", previous_keys=f"v1:{K1},v3:{K3}"
    )
    assert svc.decrypt(legacy) == "a"
    assert svc.decrypt(v3_ct) == "b"


def test_回滾_active_切回舊_id_時仍解得開新金鑰寫的密文():
    rotated = AESEncryptionService(master_key=K2, key_id="v2", previous_keys=f"v1:{K1}")
    ct = rotated.encrypt("x")
    rolled_back = AESEncryptionService(
        master_key=K1, key_id="v1", previous_keys=f"v2:{K2}"
    )
    assert rolled_back.decrypt(ct) == "x"


def test_key_id_of_與_needs_reencrypt():
    svc = AESEncryptionService(master_key=K2, key_id="v2", previous_keys=f"v1:{K1}")
    legacy = AESEncryptionService(master_key=K1).encrypt("a")
    assert svc.key_id_of(legacy) == "v1"
    assert svc.needs_reencrypt(legacy)
    assert not svc.needs_reencrypt(svc.encrypt("b"))


def test_找不到_key_id_時錯誤訊息帶_id_但不帶金鑰():
    rotated = AESEncryptionService(master_key=K2, key_id="v2", previous_keys=f"v1:{K1}")
    ct = rotated.encrypt("x")
    only_v1 = AESEncryptionService(master_key=K1)
    with pytest.raises(UnknownEncryptionKeyError) as exc:
        only_v1.decrypt(ct)
    msg = str(exc.value)
    assert "v2" in msg
    assert K1 not in msg and K2 not in msg


# ---- 設定驗證：啟動時失敗，不 fallback ----


@pytest.mark.parametrize(
    ("kwargs", "hint"),
    [
        ({"master_key": "abc"}, "ENCRYPTION_MASTER_KEY"),
        ({"master_key": "zz" * 32}, "ENCRYPTION_MASTER_KEY"),
        ({"master_key": K1, "key_id": "bad id"}, "ENCRYPTION_MASTER_KEY_ID"),
        ({"master_key": K2, "key_id": "v2", "previous_keys": "v1"}, "v1"),
        ({"master_key": K2, "key_id": "v2", "previous_keys": "v1:1234"}, "v1"),
        (
            {"master_key": K2, "key_id": "v2", "previous_keys": f"v1:{K1},v1:{K3}"},
            "v1",
        ),
        ({"master_key": K2, "key_id": "v2", "previous_keys": f"v2:{K1}"}, "v2"),
    ],
)
def test_設定不合法時拒絕建立且訊息不含金鑰(kwargs, hint):
    with pytest.raises(EncryptionKeyConfigError) as exc:
        AESEncryptionService(**kwargs)
    msg = str(exc.value)
    assert hint in msg
    for secret in (K1, K2, K3, "zz" * 32):
        assert secret not in msg


def test_previous_允許空白與空項():
    svc = AESEncryptionService(
        master_key=K2, key_id="v2", previous_keys=f" v1:{K1} , ,"
    )
    assert svc.key_ids == ("v2", "v1")


# ---- 啟動檢查：設定不合法 → 任何環境都拒絕啟動 ----


def test_啟動時金鑰設定不合法就拒絕啟動(monkeypatch):
    import src.main as main_mod

    monkeypatch.setattr(main_mod.settings, "encryption_master_key", K2)
    monkeypatch.setattr(main_mod.settings, "encryption_master_key_id", "v2")
    monkeypatch.setattr(main_mod.settings, "encryption_previous_keys", f"v2:{K1}")
    with pytest.raises(RuntimeError) as exc:
        main_mod._validate_encryption_keys()
    assert "v2" in str(exc.value) and K1 not in str(exc.value)


def test_啟動時只設舊的一個變數照常通過(monkeypatch):
    import src.main as main_mod

    monkeypatch.setattr(main_mod.settings, "encryption_master_key", K1)
    monkeypatch.setattr(main_mod.settings, "encryption_master_key_id", "v1")
    monkeypatch.setattr(main_mod.settings, "encryption_previous_keys", "")
    main_mod._validate_encryption_keys()
