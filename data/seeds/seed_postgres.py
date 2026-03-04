"""DB init + seed: create_all + migration + initial data.

Usage:
  # Local
  cd apps/backend && uv run python ../../data/seeds/seed_postgres.py

  # Cloud (Neon)
  cd apps/backend && DATABASE_URL_OVERRIDE=postgresql+asyncpg://... uv run python ../../data/seeds/seed_postgres.py
"""

import asyncio
import sys
from pathlib import Path

# Ensure backend src is importable
backend_src = Path(__file__).resolve().parent.parent.parent / "apps" / "backend"
sys.path.insert(0, str(backend_src))

from src.config import Settings  # noqa: E402
from src.infrastructure.auth.bcrypt_password_service import BcryptPasswordService  # noqa: E402
from src.infrastructure.db.base import Base  # noqa: E402
from src.infrastructure.db.models import *  # noqa: E402, F401, F403 — register all models

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy import text  # noqa: E402
from uuid import uuid4  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

MIGRATIONS = [
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS enabled_tools JSON NOT NULL DEFAULT ('[]')",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS rag_top_k INTEGER NOT NULL DEFAULT 5",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS rag_score_threshold FLOAT NOT NULL DEFAULT 0.3",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(50) NOT NULL DEFAULT ''",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS llm_model VARCHAR(100) NOT NULL DEFAULT ''",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS show_sources BOOLEAN NOT NULL DEFAULT TRUE",
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS bot_id VARCHAR(36) DEFAULT NULL",
    "CREATE INDEX IF NOT EXISTS ix_conversations_tenant_bot ON conversations (tenant_id, bot_id)",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS short_code VARCHAR(16)",
    "UPDATE bots SET short_code = LEFT(REPLACE(id, '-', ''), 8) WHERE short_code IS NULL",
    "ALTER TABLE bots ALTER COLUMN short_code SET NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_bots_short_code ON bots (short_code)",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS avg_chunk_length INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS min_chunk_length INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS max_chunk_length INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS quality_score FLOAT NOT NULL DEFAULT 0.0",
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS quality_issues TEXT NOT NULL DEFAULT ''",
]


async def seed() -> None:
    settings = Settings()
    engine = create_async_engine(settings.database_url, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 0. Drop all tables (testing phase — reset schema on every seed)
    print("=== Dropping all tables ===")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # 1. Create tables
    print("=== Creating tables ===")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Run migrations
    print("\n=== Running migrations ===")
    async with engine.begin() as conn:
        for stmt in MIGRATIONS:
            try:
                await conn.execute(text(stmt))
            except Exception as e:
                print(f"  SKIP: {stmt[:60]}... ({e})")

    # 3. Seed data
    print("\n=== Seeding data ===")
    pwd_service = BcryptPasswordService(rounds=settings.bcrypt_rounds)

    tenant_id = str(uuid4())
    system_admin_id = str(uuid4())
    tenant_admin_id = str(uuid4())
    now = datetime.now(timezone.utc)

    system_password = pwd_service.hash_password("admin123")
    tenant_password = pwd_service.hash_password("shop123")

    async with async_session() as session:
        async with session.begin():
            await session.execute(text("""
                INSERT INTO tenants (id, name, plan, created_at, updated_at)
                VALUES (:id, :name, :plan, :created_at, :updated_at)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": tenant_id,
                "name": "Demo Shop",
                "plan": "starter",
                "created_at": now,
                "updated_at": now,
            })

            await session.execute(text("""
                INSERT INTO users (id, tenant_id, email, hashed_password, role, created_at, updated_at)
                VALUES (:id, NULL, :email, :hashed_password, :role, :created_at, :updated_at)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": system_admin_id,
                "email": "admin@system.com",
                "hashed_password": system_password,
                "role": "system_admin",
                "created_at": now,
                "updated_at": now,
            })

            await session.execute(text("""
                INSERT INTO users (id, tenant_id, email, hashed_password, role, created_at, updated_at)
                VALUES (:id, :tenant_id, :email, :hashed_password, :role, :created_at, :updated_at)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": tenant_admin_id,
                "tenant_id": tenant_id,
                "email": "shop@demo.com",
                "hashed_password": tenant_password,
                "role": "tenant_admin",
                "created_at": now,
                "updated_at": now,
            })

    await engine.dispose()

    print("\n=== Seed 完成 ===")
    print(f"Tenant:       Demo Shop ({tenant_id})")
    print(f"System Admin: admin@system.com / admin123")
    print(f"Tenant Admin: shop@demo.com / shop123")


if __name__ == "__main__":
    asyncio.run(seed())
