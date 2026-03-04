"""補建 System Tenant 並將 system_admin 綁定至該 Tenant。

不會 drop 任何資料，只做 INSERT + UPDATE。

Usage:
  cd apps/backend && DATABASE_URL_OVERRIDE="postgresql+asyncpg://..." \
    uv run python ../../data/seeds/migrate_system_tenant.py
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

backend_src = Path(__file__).resolve().parent.parent.parent / "apps" / "backend"
sys.path.insert(0, str(backend_src))

from src.config import Settings  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy import text  # noqa: E402


async def migrate() -> None:
    settings = Settings()
    url = settings.database_url
    print(f"Connecting to: {url.split('@')[-1]}")

    engine = create_async_engine(url, echo=False, connect_args={"timeout": 30})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. 檢查是否已有 System tenant
        result = await session.execute(
            text("SELECT id FROM tenants WHERE name = :name"),
            {"name": "System"},
        )
        existing = result.scalar_one_or_none()

        if existing:
            system_tenant_id = existing
            print(f"System Tenant 已存在: {system_tenant_id}")
        else:
            system_tenant_id = str(uuid4())
            now = datetime.now(timezone.utc)
            async with session.begin():
                await session.execute(
                    text("""
                        INSERT INTO tenants (id, name, plan, created_at, updated_at)
                        VALUES (:id, :name, :plan, :created_at, :updated_at)
                    """),
                    {
                        "id": system_tenant_id,
                        "name": "System",
                        "plan": "enterprise",
                        "created_at": now,
                        "updated_at": now,
                    },
                )
            print(f"System Tenant 已建立: {system_tenant_id}")

        # 2. 將所有 system_admin 的 tenant_id 指向 System Tenant
        async with session.begin():
            result = await session.execute(
                text("""
                    UPDATE users
                    SET tenant_id = :tenant_id
                    WHERE role = 'system_admin' AND (tenant_id IS NULL OR tenant_id != :tenant_id)
                """),
                {"tenant_id": system_tenant_id},
            )
        updated = result.rowcount
        print(f"已更新 {updated} 個 system_admin 的 tenant_id")

        # 3. 驗證
        result = await session.execute(
            text("SELECT id, email, tenant_id FROM users WHERE role = 'system_admin'")
        )
        for row in result.all():
            print(f"  -> {row.email} (tenant_id={row.tenant_id})")

    await engine.dispose()
    print("\n=== Migration 完成 ===")


if __name__ == "__main__":
    asyncio.run(migrate())
