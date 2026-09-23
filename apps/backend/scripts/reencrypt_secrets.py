"""把非 active 金鑰的密文以 active 金鑰重新加密寫回（Issue #105 輪替第 3 步）。

用法（在 apps/backend，環境變數與服務相同：ENCRYPTION_MASTER_KEY /
ENCRYPTION_MASTER_KEY_ID / ENCRYPTION_PREVIOUS_KEYS / DATABASE_URL）：

    uv run python -m scripts.reencrypt_secrets --dry-run     # 只列每個欄位的待轉筆數
    uv run python -m scripts.reencrypt_secrets               # 執行
    uv run python -m scripts.reencrypt_secrets --batch-size 50

性質
- 冪等：已是 active 金鑰的密文不動，重跑只會處理剩下的
- 分批：依主鍵 keyset 分頁，每批 commit 一次
- 單筆失敗（解不開、金鑰 id 不在設定中）記錄後繼續；結束時有失敗則回傳 1
- 記錄只含主鍵、欄位與金鑰 id，不含明文或密文

涵蓋範圍＝ENCRYPTED_FIELDS。新增加密欄位必須登記在這裡，
tests/unit/scripts/test_reencrypt_fence.py 會掃 src 內每個 .encrypt( 呼叫點把關。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Literal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update  # noqa: E402

from src.infrastructure.crypto.aes_encryption_service import (  # noqa: E402
    AESEncryptionService,
    UnknownEncryptionKeyError,
)
from src.infrastructure.db.models.bot_model import BotModel  # noqa: E402
from src.infrastructure.db.models.notification_channel_model import (  # noqa: E402
    NotificationChannelModel,
)
from src.infrastructure.db.models.provider_setting_model import (  # noqa: E402
    ProviderSettingModel,
)
from src.infrastructure.db.models.tenant_identity_secret_model import (  # noqa: E402
    TenantIdentitySecretModel,
)

Kind = Literal["scalar", "mcp_env"]


@dataclass(frozen=True)
class EncryptedField:
    name: str
    model: Any
    pk: str
    column: str
    kind: Kind
    # src/ 內會把密文寫進這個欄位的檔案（相對 src/），供圍籬測試比對
    writers: tuple[str, ...]
    # 此欄位允許既有明文 JSON（遷移前資料），遇到時略過不算失敗
    plaintext_json_ok: bool = False
    # 此欄位可能有遷移前的明文（#107 LINE 憑證）：解不開且不是金鑰 id 問題 → 加密寫回
    encrypt_plaintext: bool = False


ENCRYPTED_FIELDS: tuple[EncryptedField, ...] = (
    EncryptedField(
        name="provider_settings.api_key_encrypted",
        model=ProviderSettingModel,
        pk="id",
        column="api_key_encrypted",
        kind="scalar",
        writers=(
            "application/platform/create_provider_setting_use_case.py",
            "application/platform/update_provider_setting_use_case.py",
        ),
    ),
    EncryptedField(
        name="tenant_identity_secrets.secret_encrypted",
        model=TenantIdentitySecretModel,
        pk="tenant_id",
        column="secret_encrypted",
        kind="scalar",
        writers=("application/widget/identity_use_cases.py",),
    ),
    EncryptedField(
        name="notification_channels.config_encrypted",
        model=NotificationChannelModel,
        pk="id",
        column="config_encrypted",
        kind="scalar",
        writers=("application/observability/notification_use_cases.py",),
        plaintext_json_ok=True,
    ),
    EncryptedField(
        name="bots.mcp_bindings[].env_values",
        model=BotModel,
        pk="id",
        column="mcp_bindings",
        kind="mcp_env",
        writers=(
            "application/bot/create_bot_use_case.py",
            "application/bot/update_bot_use_case.py",
        ),
    ),
    # #107：LINE 憑證 at-rest 加密（repository 層加解密）；既有明文由本腳本一次轉為密文
    EncryptedField(
        name="bots.line_channel_secret",
        model=BotModel,
        pk="id",
        column="line_channel_secret",
        kind="scalar",
        writers=("infrastructure/db/repositories/bot_repository.py",),
        encrypt_plaintext=True,
    ),
    EncryptedField(
        name="bots.line_channel_access_token",
        model=BotModel,
        pk="id",
        column="line_channel_access_token",
        kind="scalar",
        writers=("infrastructure/db/repositories/bot_repository.py",),
        encrypt_plaintext=True,
    ),
)

# 只寫進 Redis 快取（有 TTL）的密文：不需重新加密。解密失敗時各呼叫點都當作快取
# 未命中回 DB 重讀，所以移除舊金鑰不會讓快取壞掉。
CACHE_ONLY_WRITERS: dict[str, str] = {
    "application/line/handle_webhook_use_case.py": (
        "bot 快取裡的 LINE 憑證（Redis）；解密失敗即回 DB 補讀"
    ),
    "infrastructure/llm/dynamic_llm_factory.py": (
        "LLM 供應商設定快取（Redis）；解密失敗視為快取未命中"
    ),
    "infrastructure/embedding/dynamic_embedding_factory.py": (
        "Embedding 供應商設定快取（Redis）；解密失敗視為快取未命中"
    ),
}


@dataclass
class FieldReport:
    name: str
    scanned: int = 0
    already_active: int = 0
    stale: int = 0
    reencrypted: int = 0
    plaintext_skipped: int = 0
    plaintext_encrypted: int = 0
    failures: list[str] = field(default_factory=list)


def _is_plaintext_json(value: str) -> bool:
    import json

    try:
        json.loads(value)
    except (ValueError, TypeError):
        return False
    return True


def classify(
    value: str,
    svc: AESEncryptionService,
    plaintext_json_ok: bool,
    encrypt_plaintext: bool = False,
) -> str:
    """empty / plaintext / plaintext_to_encrypt / active / stale。"""
    if not value:
        return "empty"
    if plaintext_json_ok and _is_plaintext_json(value):
        return "plaintext"
    if encrypt_plaintext:
        try:
            svc.decrypt(value)
        except UnknownEncryptionKeyError:
            return "stale"  # 交給下游記為失敗（缺金鑰，不是明文）
        except Exception:
            return "plaintext_to_encrypt"
    return "stale" if svc.needs_reencrypt(value) else "active"


def _reencrypt_value(
    value: str,
    svc: AESEncryptionService,
    report: FieldReport,
    where: str,
    dry_run: bool,
    plaintext_json_ok: bool = False,
    encrypt_plaintext: bool = False,
) -> str:
    """回傳寫回的值（不需要或失敗時回原值）；統計寫進 report。"""
    kind = classify(value, svc, plaintext_json_ok, encrypt_plaintext)
    if kind == "empty":
        return value
    if kind == "plaintext":
        report.plaintext_skipped += 1
        return value
    if kind == "plaintext_to_encrypt":
        report.plaintext_encrypted += 1
        return value if dry_run else svc.encrypt(value)
    if kind == "active":
        report.already_active += 1
        return value
    report.stale += 1
    try:
        plain = svc.decrypt(value)
    except Exception as e:
        report.failures.append(
            f"{where}：{type(e).__name__}（金鑰 id {svc.key_id_of(value)}）"
        )
        return value
    if dry_run:
        return value
    report.reencrypted += 1
    return svc.encrypt(plain)


def _reencrypt_bindings(
    bindings: list[dict[str, Any]],
    svc: AESEncryptionService,
    report: FieldReport,
    pk: str,
    dry_run: bool,
) -> list[dict[str, Any]]:
    new_bindings = []
    for binding in bindings or []:
        if not binding.get("env_values"):
            new_bindings.append(binding)  # 原樣保留，重跑不產生寫入
            continue
        env = dict(binding["env_values"])
        for key, value in env.items():
            where = f"{pk} / {binding.get('registry_id', '?')} / {key}"
            env[key] = _reencrypt_value(value, svc, report, where, dry_run)
        new_bindings.append({**binding, "env_values": env})
    return new_bindings


async def process_field(
    session: Any,
    svc: AESEncryptionService,
    spec: EncryptedField,
    *,
    dry_run: bool,
    batch_size: int = 100,
) -> FieldReport:
    report = FieldReport(spec.name)
    pk_col = getattr(spec.model, spec.pk)
    value_col = getattr(spec.model, spec.column)
    last_pk = ""
    while True:
        result = await session.execute(
            select(pk_col, value_col)
            .where(pk_col > last_pk)
            .order_by(pk_col)
            .limit(batch_size)
        )
        rows = list(result.all())
        if not rows:
            break
        pending = 0
        for pk, value in rows:
            report.scanned += 1
            if spec.kind == "scalar":
                new_value: Any = _reencrypt_value(
                    value or "",
                    svc,
                    report,
                    str(pk),
                    dry_run,
                    spec.plaintext_json_ok,
                    spec.encrypt_plaintext,
                )
                changed = new_value != (value or "")
            else:
                new_value = _reencrypt_bindings(
                    value or [], svc, report, str(pk), dry_run
                )
                changed = new_value != (value or [])
            if changed and not dry_run:
                await session.execute(
                    update(spec.model)
                    .where(pk_col == pk)
                    .values({spec.column: new_value})
                )
                pending += 1
        if pending:
            await session.commit()
        last_pk = rows[-1][0]
    return report


async def count_snapshot_env_values(session: Any) -> int:
    """快照應已剝除 env_values（take_snapshot 紅線），回報殘留筆數。"""
    from sqlalchemy import text

    result = await session.execute(
        text(
            "SELECT count(*) FROM bot_config_versions "
            "WHERE config_snapshot::text LIKE '%env_values%'"
        )
    )
    return int(result.scalar_one())


def format_report(reports: list[FieldReport], dry_run: bool, active_id: str) -> str:
    verb = "待轉" if dry_run else "已轉"
    lines = [
        f"active 金鑰 id：{active_id}（{'dry-run，未寫入' if dry_run else '執行'}）",
        f"{'欄位':45} {'掃描':>6} {'已是active':>9} {verb:>6} "
        f"{'明文略過':>7} {'明文→密文':>8} {'失敗':>5}",
    ]
    for r in reports:
        done = r.stale - len(r.failures) if dry_run else r.reencrypted
        lines.append(
            f"{r.name:45} {r.scanned:6} {r.already_active:9} {done:6} "
            f"{r.plaintext_skipped:7} {r.plaintext_encrypted:8} {len(r.failures):5}"
        )
        lines.extend(f"    失敗：{f}" for f in r.failures)
    return "\n".join(lines)


async def run(dry_run: bool, batch_size: int) -> int:
    from src.config import settings
    from src.infrastructure.crypto.aes_encryption_service import (
        build_encryption_service,
    )
    from src.infrastructure.db.engine import async_session_factory

    svc = build_encryption_service(settings)
    reports = []
    async with async_session_factory() as session:
        for spec in ENCRYPTED_FIELDS:
            reports.append(
                await process_field(
                    session, svc, spec, dry_run=dry_run, batch_size=batch_size
                )
            )
        leaked = await count_snapshot_env_values(session)
    print(format_report(reports, dry_run, svc.active_key_id))
    print(f"bot_config_versions 快照含 env_values 的筆數：{leaked}（應為 0）")
    failed = sum(len(r.failures) for r in reports)
    return 1 if failed or leaked else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="只統計，不寫入")
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args(argv)
    return asyncio.run(run(args.dry_run, args.batch_size))


if __name__ == "__main__":
    raise SystemExit(main())
