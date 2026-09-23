"""Widget 宿主身分綁定用例（Issue #68 P7b / #101 B8 覆蓋率下限）。

identity secret = widget 匿名訪客升級為 end_user 的唯一認證依據，這裡守：
- 簽章驗證：正確通過、竄改 / 過期 / 別租戶 secret 一律拒絕
- 輪替：新 secret 立即生效、舊 secret 立即失效、只回傳一次、密文存放
- 停用 / 未設定 / 儲存失效 / 解密失敗的判定（fail-open 且不誤判為通過）
- 驗證失敗計 identify_fail（計分失敗不影響判定）
- 政策更新與稽核
"""

import asyncio
import time
from datetime import datetime, timezone

from src.application.widget.identity_use_cases import (
    AUDIT_ENTITY,
    GetIdentitySecretStatusUseCase,
    RotateIdentitySecretUseCase,
    UpdateIdentityPolicyUseCase,
    VerifyWidgetIdentityUseCase,
)
from src.domain.abuse.policy import SubjectKind
from src.domain.widget.identity import (
    TenantIdentitySecret,
    TenantIdentitySecretRepository,
    compute_identity_hash,
)

_T1 = "tenant-a"
_T2 = "tenant-b"


def _run(coro):
    return asyncio.run(coro)


class _Repo(TenantIdentitySecretRepository):
    def __init__(self, fail: bool = False) -> None:
        self.rows: dict[str, TenantIdentitySecret] = {}
        self.fail = fail
        self.saved: list[TenantIdentitySecret] = []

    async def get(self, tenant_id: str) -> TenantIdentitySecret | None:
        if self.fail:
            raise ConnectionError("db down")
        return self.rows.get(tenant_id)

    async def save(self, secret: TenantIdentitySecret) -> None:
        self.saved.append(secret)
        self.rows[secret.tenant_id] = secret


class _Enc:
    """可辨識的可逆加密：確認存放的是密文而非明文。"""

    def encrypt(self, plaintext: str) -> str:
        return "enc:" + plaintext[::-1]

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext.startswith("enc:"):
            raise ValueError("bad ciphertext")
        return ciphertext[4:][::-1]


class _Audit:
    def __init__(self) -> None:
        self.records: list[dict] = []

    async def record(self, **kwargs) -> None:
        self.records.append(kwargs)


class _Abuse:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple] = []
        self.fail = fail

    async def record(self, tenant_id, subject, **kwargs) -> None:
        if self.fail:
            raise ConnectionError("abuse store down")
        self.calls.append((tenant_id, subject, kwargs))


def _claim(secret: str, uid: str = "u-1", ttl: int = 600) -> tuple[str, int, str]:
    exp = int(time.time()) + ttl
    return uid, exp, compute_identity_hash(secret, uid, exp)


def _verify(repo, *, tenant_id=_T1, claim, abuse=None, visitor_id="v-1"):
    uid, exp, h = claim
    uc = VerifyWidgetIdentityUseCase(repo, _Enc(), abuse_control=abuse)
    return _run(
        uc.execute(
            tenant_id=tenant_id,
            visitor_id=visitor_id,
            user_id=uid,
            exp=exp,
            presented_hash=h,
        )
    )


def _rotate(repo, tenant_id=_T1, audit=None) -> str:
    uc = RotateIdentitySecretUseCase(repo, _Enc(), audit=audit)
    return _run(uc.execute(tenant_id, actor_user_id="admin-1"))


# ---------------------------------------------------------------- rotate


def test_rotate_first_time_stores_ciphertext_and_defaults():
    repo = _Repo()
    audit = _Audit()
    secret = _rotate(repo, audit=audit)

    row = repo.rows[_T1]
    assert len(secret) == 64
    assert secret not in row.secret_encrypted  # 明文不落地
    assert _Enc().decrypt(row.secret_encrypted) == secret
    assert row.is_enabled is True
    assert row.enforce_verified is False
    assert audit.records[0]["entity_type"] == AUDIT_ENTITY
    assert audit.records[0]["action"] == "rotate"
    assert audit.records[0]["before"] == {"rotated_at": None}
    assert audit.records[0]["tenant_id"] == _T1
    assert audit.records[0]["actor_user_id"] == "admin-1"
    # 稽核不得含 secret
    assert secret not in repr(audit.records)


def test_rotate_keeps_policy_and_invalidates_old_secret():
    repo = _Repo()
    old = _rotate(repo)
    repo.rows[_T1].is_enabled = False
    repo.rows[_T1].enforce_verified = True
    old_rotated_at = repo.rows[_T1].rotated_at
    audit = _Audit()

    new = _rotate(repo, audit=audit)

    assert new != old
    row = repo.rows[_T1]
    assert row.is_enabled is False  # 輪替不得偷偷重新啟用
    assert row.enforce_verified is True
    assert audit.records[0]["before"] == {"rotated_at": old_rotated_at.isoformat()}

    row.is_enabled = True
    assert _verify(repo, claim=_claim(old)).verified is False
    assert _verify(repo, claim=_claim(new)).verified is True


def test_rotate_without_audit_still_saves():
    repo = _Repo()
    _rotate(repo, audit=None)
    assert len(repo.saved) == 1


# ---------------------------------------------------------------- status


def test_status_not_configured():
    st = _run(GetIdentitySecretStatusUseCase(_Repo()).execute(_T1))
    assert (st.has_secret, st.is_enabled, st.enforce_verified, st.rotated_at) == (
        False,
        False,
        False,
        None,
    )


def test_status_configured_never_exposes_secret():
    repo = _Repo()
    secret = _rotate(repo)
    repo.rows[_T1].enforce_verified = True
    st = _run(GetIdentitySecretStatusUseCase(repo).execute(_T1))
    assert st.has_secret and st.is_enabled and st.enforce_verified
    assert st.rotated_at == repo.rows[_T1].rotated_at
    assert secret not in repr(st)


# ---------------------------------------------------------------- policy


def test_update_policy_without_secret_is_noop():
    repo = _Repo()
    audit = _Audit()
    st = _run(
        UpdateIdentityPolicyUseCase(repo, audit).execute(
            _T1, is_enabled=True, enforce_verified=True, actor_user_id="a"
        )
    )
    assert st.has_secret is False and st.enforce_verified is False
    assert repo.saved == [] and audit.records == []


def test_update_policy_partial_and_audited():
    repo = _Repo()
    _rotate(repo)
    audit = _Audit()
    uc = UpdateIdentityPolicyUseCase(repo, audit)

    st = _run(
        uc.execute(_T1, is_enabled=None, enforce_verified=True, actor_user_id="a")
    )
    assert st.is_enabled is True and st.enforce_verified is True
    assert audit.records[-1]["before"] == {
        "is_enabled": True,
        "enforce_verified": False,
    }
    assert audit.records[-1]["after"] == {
        "is_enabled": True,
        "enforce_verified": True,
    }

    st = _run(
        uc.execute(_T1, is_enabled=False, enforce_verified=None, actor_user_id="a")
    )
    assert st.is_enabled is False and st.enforce_verified is True
    assert repo.rows[_T1].is_enabled is False


def test_update_policy_without_audit():
    repo = _Repo()
    _rotate(repo)
    st = _run(
        UpdateIdentityPolicyUseCase(repo).execute(
            _T1, is_enabled=False, enforce_verified=None, actor_user_id=None
        )
    )
    assert st.is_enabled is False


# ---------------------------------------------------------------- verify


def test_verify_valid_signature_passes_and_carries_enforce():
    repo = _Repo()
    secret = _rotate(repo)
    repo.rows[_T1].enforce_verified = True
    v = _verify(repo, claim=_claim(secret))
    assert v.verified is True and v.enforce is True and v.reason == ""


def test_verify_other_tenants_secret_is_rejected():
    """跨租戶：用 B 租戶的 secret 簽的身分，不能在 A 租戶通過。"""
    repo = _Repo()
    _rotate(repo, _T1)
    secret_b = _rotate(repo, _T2)
    abuse = _Abuse()
    v = _verify(repo, tenant_id=_T1, claim=_claim(secret_b), abuse=abuse)
    assert v.verified is False and v.reason == "invalid"
    assert abuse.calls[0][0] == _T1
    # 同一個簽章在 B 租戶本來就合法
    assert _verify(repo, tenant_id=_T2, claim=_claim(secret_b)).verified is True


def test_verify_tampered_user_id_rejected_and_scored():
    repo = _Repo()
    secret = _rotate(repo)
    uid, exp, h = _claim(secret, uid="alice")
    abuse = _Abuse()
    v = _verify(repo, claim=("mallory", exp, h), abuse=abuse, visitor_id="v-9")
    assert v.verified is False and v.reason == "invalid" and v.enforce is False
    tenant, subject, kw = abuse.calls[0]
    assert tenant == _T1
    assert subject.kind == SubjectKind.VISITOR and subject.id == "v-9"
    assert kw == {"identify_fail": True, "channel": "widget"}


def test_verify_expired_signature_rejected():
    repo = _Repo()
    secret = _rotate(repo)
    v = _verify(repo, claim=_claim(secret, ttl=-5))
    assert v.verified is False and v.reason == "invalid"


def test_verify_failure_without_visitor_is_not_scored():
    repo = _Repo()
    _rotate(repo)
    abuse = _Abuse()
    v = _verify(repo, claim=("u", int(time.time()) + 60, "0" * 64), abuse=abuse,
                visitor_id=None)
    assert v.verified is False
    assert abuse.calls == []


def test_verify_abuse_store_failure_does_not_change_verdict():
    repo = _Repo()
    _rotate(repo)
    repo.rows[_T1].enforce_verified = True
    v = _verify(
        repo, claim=("u", int(time.time()) + 60, "0" * 64), abuse=_Abuse(fail=True)
    )
    assert v.verified is False and v.enforce is True and v.reason == "invalid"


def test_verify_not_configured():
    v = _verify(_Repo(), claim=("u", int(time.time()) + 60, "x"))
    assert (v.verified, v.enforce, v.reason) == (False, False, "not_configured")


def test_verify_repo_unavailable_fails_open_as_not_configured():
    v = _verify(_Repo(fail=True), claim=("u", int(time.time()) + 60, "x"))
    assert (v.verified, v.enforce, v.reason) == (False, False, "not_configured")


def test_verify_disabled_secret_never_verifies_even_with_valid_hash():
    repo = _Repo()
    secret = _rotate(repo)
    repo.rows[_T1].is_enabled = False
    repo.rows[_T1].enforce_verified = True
    v = _verify(repo, claim=_claim(secret))
    assert (v.verified, v.enforce, v.reason) == (False, False, "disabled")


def test_verify_decrypt_failure_is_invalid_and_keeps_enforce():
    repo = _Repo()
    repo.rows[_T1] = TenantIdentitySecret(
        tenant_id=_T1,
        secret_encrypted="corrupted",
        enforce_verified=True,
        rotated_at=datetime.now(timezone.utc),
    )
    v = _verify(repo, claim=("u", int(time.time()) + 60, "x"))
    assert (v.verified, v.enforce, v.reason) == (False, True, "invalid")
