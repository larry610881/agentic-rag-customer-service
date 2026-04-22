"""一次性 seed DEFAULT_MODELS 進 model_pricing 表（S-Pricing.1）。

冪等：已存在相同 (provider, model_id, effective_from=epoch seed) 的紀錄會被 skip。

Usage:
    cd apps/backend && uv run python -m scripts.seed_model_pricing
    # 或透過 gcloud IAP SSH 登 VM 後在 backend 目錄執行相同指令
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from src.domain.platform.model_registry import DEFAULT_MODELS  # noqa: E402

# 固定 seed effective_from，讓冪等性可靠（epoch 2026-01-01 UTC）
SEED_EFFECTIVE_FROM = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
SEED_BY = "seed:default_models"
SEED_NOTE = "Initial seed from DEFAULT_MODELS dict (S-Pricing.1)"


def _build_rows() -> list[dict]:
    rows: list[dict] = []
    for provider, buckets in DEFAULT_MODELS.items():
        for category, entries in buckets.items():
            if category not in ("llm", "embedding"):
                continue
            for m in entries:
                mid = m.get("model_id")
                if not mid:
                    continue
                rows.append(
                    {
                        "id": str(uuid4()),
                        "provider": provider,
                        "model_id": mid,
                        "display_name": m.get("display_name", mid),
                        "category": category,
                        "input_price": Decimal(str(m.get("input_price", 0))),
                        "output_price": Decimal(str(m.get("output_price", 0))),
                        "cache_read_price": Decimal(
                            str(m.get("cache_read_price", 0))
                        ),
                        "cache_creation_price": Decimal(
                            str(m.get("cache_creation_price", 0))
                        ),
                        "effective_from": SEED_EFFECTIVE_FROM,
                        "created_by": SEED_BY,
                        "note": SEED_NOTE,
                    }
                )
    return rows


async def _run() -> None:
    database_url = os.environ.get("DATABASE_URL_OVERRIDE") or os.environ.get(
        "DATABASE_URL"
    )
    if not database_url:
        print(
            "ERROR: DATABASE_URL not set. "
            "For local-docker try: DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agentic_rag",
            file=sys.stderr,
        )
        sys.exit(1)

    engine = create_async_engine(database_url)
    rows = _build_rows()
    print(f"Preparing to seed {len(rows)} pricing entries...")

    async with engine.begin() as conn:
        skipped = 0
        inserted = 0
        for row in rows:
            check = await conn.execute(
                text(
                    "SELECT id FROM model_pricing "
                    "WHERE provider = :provider "
                    "AND model_id = :model_id "
                    "AND effective_from = :effective_from"
                ),
                {
                    "provider": row["provider"],
                    "model_id": row["model_id"],
                    "effective_from": row["effective_from"],
                },
            )
            if check.scalar_one_or_none() is not None:
                skipped += 1
                continue
            await conn.execute(
                text(
                    "INSERT INTO model_pricing "
                    "(id, provider, model_id, display_name, category, "
                    "input_price, output_price, cache_read_price, "
                    "cache_creation_price, effective_from, created_by, note) "
                    "VALUES (:id, :provider, :model_id, :display_name, "
                    ":category, :input_price, :output_price, "
                    ":cache_read_price, :cache_creation_price, "
                    ":effective_from, :created_by, :note)"
                ),
                row,
            )
            inserted += 1

    print(f"Seed complete: inserted={inserted}, skipped (already exists)={skipped}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_run())
