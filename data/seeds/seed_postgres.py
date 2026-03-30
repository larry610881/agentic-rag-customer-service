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
    "ALTER TABLE bots ADD COLUMN IF NOT EXISTS busy_reply_message VARCHAR(500) NOT NULL DEFAULT '小編正在努力回覆中，請稍等一下喔～'",
    # Cache-aware token billing
    "ALTER TABLE token_usage_records ADD COLUMN IF NOT EXISTS cache_read_tokens INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE token_usage_records ADD COLUMN IF NOT EXISTS cache_creation_tokens INTEGER NOT NULL DEFAULT 0",
]

# ── Tenants ────────────────────────────────────────────────────
TENANTS = [
    {"id": SYSTEM_TENANT_ID, "name": SYSTEM_TENANT_NAME, "plan": "system"},
]

# ── Users ──────────────────────────────────────────────────────
USERS = [
    {"email": "admin@system.com", "password": "admin123", "role": "system_admin", "tenant_id": SYSTEM_TENANT_ID},
]

# ── Knowledge Bases ───────────────────────────────────────────
KNOWLEDGE_BASES = []

# ── Bots ──────────────────────────────────────────────────────
BOTS = []

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

    # 2a. Run inline migrations
    print("\n=== Running inline migrations ===")
    async with engine.begin() as conn:
        for stmt in MIGRATIONS:
            try:
                await conn.execute(text(stmt))
            except Exception as e:
                print(f"  SKIP: {stmt[:60]}... ({e})")

    # 2b. Run migration SQL files
    migration_dir = Path(__file__).resolve().parent.parent.parent / "apps" / "backend" / "migrations"
    if migration_dir.exists():
        print("\n=== Running migration SQL files ===")
        for sql_file in sorted(migration_dir.glob("*.sql")):
            print(f"  Running: {sql_file.name}")
            sql = sql_file.read_text()
            async with engine.begin() as conn:
                for stmt in sql.split(";"):
                    stmt = stmt.strip()
                    if stmt and not stmt.startswith("--"):
                        try:
                            await conn.execute(text(stmt))
                        except Exception as e:
                            print(f"    SKIP: {stmt[:60]}... ({e})")

    # 3. Seed data
    print("\n=== Seeding data ===")
    pwd_service = BcryptPasswordService(rounds=settings.bcrypt_rounds)
    now = datetime.now(timezone.utc)

    async with async_session() as session:
        async with session.begin():
            # ── Tenants ───────────────────────────────────
            for t in TENANTS:
                await session.execute(text("""
                    INSERT INTO tenants (id, name, plan, allowed_agent_modes, allowed_widget_avatar, created_at, updated_at)
                    VALUES (:id, :name, :plan, :allowed_agent_modes, :allowed_widget_avatar, :created_at, :updated_at)
                    ON CONFLICT (id) DO NOTHING
                """), {
                    "id": t["id"],
                    "name": t["name"],
                    "plan": t["plan"],
                    "allowed_agent_modes": json.dumps(["router", "react", "supervisor"]) if t["plan"] == "system" else '["router", "react"]',
                    "allowed_widget_avatar": True,
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

            # ── Knowledge Bases ────────────────────────────
            for kb in KNOWLEDGE_BASES:
                kb_id = str(uuid5(NAMESPACE_DNS, f"{kb['tenant_id']}:{kb['name']}"))
                await session.execute(text("""
                    INSERT INTO knowledge_bases (id, tenant_id, name, description, kb_type, created_at, updated_at)
                    VALUES (:id, :tenant_id, :name, :description, 'user', :created_at, :updated_at)
                    ON CONFLICT (id) DO NOTHING
                """), {
                    "id": kb_id,
                    "tenant_id": kb["tenant_id"],
                    "name": kb["name"],
                    "description": kb["description"],
                    "created_at": now,
                    "updated_at": now,
                })

            # ── Bots ──────────────────────────────────────
            for bot in BOTS:
                bot_id = str(uuid5(NAMESPACE_DNS, f"{bot['tenant_id']}:{bot['name']}"))
                short_code = bot_id.replace("-", "")[:8]
                await session.execute(text("""
                    INSERT INTO bots (id, short_code, tenant_id, name, description,
                        is_active, system_prompt, enabled_tools, llm_provider, llm_model,
                        agent_mode, mcp_servers, mcp_bindings, max_tool_calls, audit_mode,
                        eval_depth, base_prompt, router_prompt, react_prompt,
                        widget_enabled, widget_allowed_origins, widget_keep_history,
                        avatar_type, avatar_model_url, widget_welcome_message, widget_placeholder_text,
                        show_sources, temperature, max_tokens, history_limit,
                        frequency_penalty, reasoning_effort, rag_top_k, rag_score_threshold,
                        created_at, updated_at)
                    VALUES (:id, :short_code, :tenant_id, :name, :description,
                        :is_active, :system_prompt, :enabled_tools, :llm_provider, :llm_model,
                        :agent_mode, :mcp_servers, :mcp_bindings, :max_tool_calls, :audit_mode,
                        :eval_depth, :base_prompt, :router_prompt, :react_prompt,
                        :widget_enabled, :widget_allowed_origins, :widget_keep_history,
                        :avatar_type, :avatar_model_url, :widget_welcome_message, :widget_placeholder_text,
                        :show_sources, :temperature, :max_tokens, :history_limit,
                        :frequency_penalty, :reasoning_effort, :rag_top_k, :rag_score_threshold,
                        :created_at, :updated_at)
                    ON CONFLICT (id) DO NOTHING
                """), {
                    "id": bot_id,
                    "short_code": short_code,
                    "tenant_id": bot["tenant_id"],
                    "name": bot["name"],
                    "description": bot["description"],
                    "is_active": True,
                    "system_prompt": "",
                    "enabled_tools": json.dumps(bot["enabled_tools"]),
                    "llm_provider": bot["llm_provider"],
                    "llm_model": bot["llm_model"],
                    "agent_mode": bot["agent_mode"],
                    "mcp_servers": "[]",
                    "mcp_bindings": "[]",
                    "max_tool_calls": 5,
                    "audit_mode": "minimal",
                    "eval_depth": "L1",
                    "base_prompt": "",
                    "router_prompt": "",
                    "react_prompt": "",
                    "widget_enabled": False,
                    "widget_allowed_origins": "[]",
                    "widget_keep_history": True,
                    "avatar_type": "none",
                    "avatar_model_url": "",
                    "widget_welcome_message": "",
                    "widget_placeholder_text": "",
                    "show_sources": True,
                    "temperature": 0.3,
                    "max_tokens": 1024,
                    "history_limit": 10,
                    "frequency_penalty": 0.0,
                    "reasoning_effort": "medium",
                    "rag_top_k": 5,
                    "rag_score_threshold": 0.3,
                    "created_at": now,
                    "updated_at": now,
                })

            # ── Bot-KB 關聯 ───────────────────────────────
            for bot in BOTS:
                bot_id = str(uuid5(NAMESPACE_DNS, f"{bot['tenant_id']}:{bot['name']}"))
                for kb in KNOWLEDGE_BASES:
                    if kb["tenant_id"] == bot["tenant_id"]:
                        kb_id = str(uuid5(NAMESPACE_DNS, f"{kb['tenant_id']}:{kb['name']}"))
                        await session.execute(text("""
                            INSERT INTO bot_knowledge_bases (bot_id, knowledge_base_id, created_at)
                            VALUES (:bot_id, :kb_id, :created_at)
                            ON CONFLICT DO NOTHING
                        """), {
                            "bot_id": bot_id,
                            "kb_id": kb_id,
                            "created_at": now,
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
