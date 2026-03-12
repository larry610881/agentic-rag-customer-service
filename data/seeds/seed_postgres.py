"""DB init + seed: create_all + migration + initial data.

Usage:
  # Local
  cd apps/backend && uv run python ../../data/seeds/seed_postgres.py

  # Cloud (Neon)
  cd apps/backend && DATABASE_URL_OVERRIDE=postgresql+asyncpg://... uv run python ../../data/seeds/seed_postgres.py
"""

import asyncio
import json
import sys
from pathlib import Path
from uuid import NAMESPACE_DNS, uuid4, uuid5

# Ensure backend src is importable
backend_src = Path(__file__).resolve().parent.parent.parent / "apps" / "backend"
sys.path.insert(0, str(backend_src))

from datetime import datetime, timezone  # noqa: E402

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from src.config import Settings  # noqa: E402
from src.domain.platform.model_registry import DEFAULT_MODELS  # noqa: E402
from src.domain.platform.prompt_defaults import (  # noqa: E402
    SEED_BASE_PROMPT,
    SEED_REACT_MODE_PROMPT,
    SEED_ROUTER_MODE_PROMPT,
)
from src.domain.shared.constants import (  # noqa: E402
    SYSTEM_TENANT_ID,
    SYSTEM_TENANT_NAME,
)
from src.infrastructure.auth.bcrypt_password_service import (
    BcryptPasswordService,  # noqa: E402
)
from src.infrastructure.db.base import Base  # noqa: E402
from src.infrastructure.db.models import *  # noqa: E402, F401, F403 — register all models

# ── Deterministic IDs ──────────────────────────────────────────
JOYINKITCHEN_TENANT_ID = str(uuid5(NAMESPACE_DNS, "joyinkitchen"))
SPRINGFAIR_TENANT_ID = str(uuid5(NAMESPACE_DNS, "springfair"))

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
    "ALTER TABLE documents ADD COLUMN IF NOT EXISTS raw_content BYTEA",
    # Widget columns
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS widget_enabled BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS widget_allowed_origins JSON NOT NULL DEFAULT ('[]')",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS widget_keep_history BOOLEAN NOT NULL DEFAULT TRUE",
    # System Prompt Config: bots 3 override columns
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS base_prompt TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS router_prompt TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS react_prompt TEXT NOT NULL DEFAULT ''",
    # Widget Avatar columns
    "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS allowed_widget_avatar BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS avatar_type VARCHAR(16) NOT NULL DEFAULT 'none'",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS avatar_model_url VARCHAR(512) NOT NULL DEFAULT ''",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS widget_welcome_message VARCHAR(500) NOT NULL DEFAULT ''",
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS widget_placeholder_text VARCHAR(200) NOT NULL DEFAULT ''",
]

# ── Tenants ────────────────────────────────────────────────────
TENANTS = [
    {"id": SYSTEM_TENANT_ID, "name": SYSTEM_TENANT_NAME, "plan": "system"},
    {"id": JOYINKITCHEN_TENANT_ID, "name": "窩廚房", "plan": "starter"},
    {"id": SPRINGFAIR_TENANT_ID, "name": "春季展", "plan": "starter"},
]

# ── Users ──────────────────────────────────────────────────────
USERS = [
    {"email": "admin@system.com", "password": "admin123", "role": "system_admin", "tenant_id": SYSTEM_TENANT_ID},
    {"email": "admin@joyinkitchen.com", "password": "joy123", "role": "tenant_admin", "tenant_id": JOYINKITCHEN_TENANT_ID},
    {"email": "admin@springfair.com", "password": "spring123", "role": "tenant_admin", "tenant_id": SPRINGFAIR_TENANT_ID},
]

# ── Provider Settings ─────────────────────────────────────────
PROVIDER_SETTINGS = [
    {
        "provider_type": "llm",
        "provider_name": "openai",
        "display_name": "OpenAI",
        "models": DEFAULT_MODELS["openai"]["llm"],
    },
    {
        "provider_type": "llm",
        "provider_name": "deepseek",
        "display_name": "DeepSeek",
        "models": DEFAULT_MODELS["deepseek"]["llm"],
    },
    {
        "provider_type": "llm",
        "provider_name": "google",
        "display_name": "Google",
        "models": DEFAULT_MODELS["google"]["llm"],
    },
    {
        "provider_type": "llm",
        "provider_name": "anthropic",
        "display_name": "Anthropic",
        "models": DEFAULT_MODELS["anthropic"]["llm"],
    },
    {
        "provider_type": "embedding",
        "provider_name": "openai",
        "display_name": "OpenAI Embedding",
        "models": [
            {"model_id": "text-embedding-3-small", "display_name": "text-embedding-3-small", "is_default": True, "is_enabled": True},
        ],
    },
]


def _build_model_json(models: list[dict]) -> str:
    """Build JSON for provider_settings.models column."""
    enriched = []
    for m in models:
        enriched.append({
            "model_id": m["model_id"],
            "display_name": m["display_name"],
            "is_default": m.get("is_default", False),
            "is_enabled": m.get("is_enabled", True),
            "price": m.get("price", ""),
            "input_price": m.get("input_price", 0),
            "output_price": m.get("output_price", 0),
        })
    # Mark first model as default if none set
    if enriched and not any(m["is_default"] for m in enriched):
        enriched[0]["is_default"] = True
    return json.dumps(enriched)


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
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        async with session.begin():
            # ── Tenants ───────────────────────────────────
            for t in TENANTS:
                await session.execute(text("""
                    INSERT INTO tenants (id, name, plan, allowed_agent_modes, created_at, updated_at)
                    VALUES (:id, :name, :plan, :allowed_agent_modes, :created_at, :updated_at)
                    ON CONFLICT (id) DO NOTHING
                """), {
                    "id": t["id"],
                    "name": t["name"],
                    "plan": t["plan"],
                    "allowed_agent_modes": '["router", "react"]',
                    "created_at": now,
                    "updated_at": now,
                })

            # ── Users ─────────────────────────────────────
            for u in USERS:
                hashed = pwd_service.hash_password(u["password"])
                await session.execute(text("""
                    INSERT INTO users (id, tenant_id, email, hashed_password, role, created_at, updated_at)
                    VALUES (:id, :tenant_id, :email, :hashed_password, :role, :created_at, :updated_at)
                    ON CONFLICT (id) DO NOTHING
                """), {
                    "id": str(uuid4()),
                    "tenant_id": u["tenant_id"],
                    "email": u["email"],
                    "hashed_password": hashed,
                    "role": u["role"],
                    "created_at": now,
                    "updated_at": now,
                })

            # ── System Prompt Config ──────────────────────
            await session.execute(text("""
                INSERT INTO system_prompt_configs (id, base_prompt, router_mode_prompt, react_mode_prompt, updated_at)
                VALUES (:id, :base_prompt, :router_mode_prompt, :react_mode_prompt, :updated_at)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": "default",
                "base_prompt": SEED_BASE_PROMPT,
                "router_mode_prompt": SEED_ROUTER_MODE_PROMPT,
                "react_mode_prompt": SEED_REACT_MODE_PROMPT,
                "updated_at": now,
            })

            # ── Provider Settings ─────────────────────────
            for ps in PROVIDER_SETTINGS:
                await session.execute(text("""
                    INSERT INTO provider_settings
                        (id, provider_type, provider_name, display_name, is_enabled, api_key_encrypted, base_url, models, extra_config, created_at, updated_at)
                    VALUES
                        (:id, :provider_type, :provider_name, :display_name, :is_enabled, :api_key_encrypted, :base_url, :models, :extra_config, :created_at, :updated_at)
                    ON CONFLICT DO NOTHING
                """), {
                    "id": str(uuid4()),
                    "provider_type": ps["provider_type"],
                    "provider_name": ps["provider_name"],
                    "display_name": ps["display_name"],
                    "is_enabled": True,
                    "api_key_encrypted": "",
                    "base_url": "",
                    "models": _build_model_json(ps["models"]),
                    "extra_config": "{}",
                    "created_at": now,
                    "updated_at": now,
                })

    await engine.dispose()

    print("\n=== Seed 完成 ===")
    print(f"Tenants: {len(TENANTS)}")
    for t in TENANTS:
        print(f"  {t['name']} ({t['id']})")
    print(f"Users: {len(USERS)}")
    for u in USERS:
        print(f"  {u['email']} / {u['password']} ({u['role']})")
    print(f"Provider Settings: {len(PROVIDER_SETTINGS)}")
    for ps in PROVIDER_SETTINGS:
        print(f"  {ps['provider_type']}:{ps['provider_name']} — {ps['display_name']}")
    print("System Prompt Config: 1 (id=default)")


if __name__ == "__main__":
    asyncio.run(seed())
