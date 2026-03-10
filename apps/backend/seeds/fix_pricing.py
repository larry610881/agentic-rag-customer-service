"""一次性修復 DB 中 provider_settings 的 pricing 資料。

Usage:
    cd apps/backend && uv run python -m seeds.fix_pricing
"""

import asyncio
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.domain.platform.model_registry import DEFAULT_MODELS


def _build_registry_pricing() -> dict[str, dict[str, float]]:
    """Build a flat {model_id: {input_price, output_price}} dict from registry."""
    pricing = {}
    for provider_data in DEFAULT_MODELS.values():
        for model in provider_data.get("llm", []):
            mid = model["model_id"]
            inp = model.get("input_price", 0)
            out = model.get("output_price", 0)
            if inp > 0 or out > 0:
                pricing[mid] = {"input_price": inp, "output_price": out}
    return pricing


async def main():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        # Try reading from .env
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
        )
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("DATABASE_URL="):
                        db_url = line.split("=", 1)[1].strip('"').strip("'")
                        break

    if not db_url:
        print("ERROR: DATABASE_URL not found")
        sys.exit(1)

    # Ensure async driver
    if "postgresql://" in db_url and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    registry = _build_registry_pricing()
    print(f"Registry has {len(registry)} models with pricing")

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        rows = await conn.execute(
            text(
                "SELECT id, provider_name, models FROM provider_settings WHERE provider_type = 'llm'"
            )
        )
        updated = 0
        for row in rows:
            setting_id, provider_name, models_json = row
            if not models_json:
                continue
            models = (
                json.loads(models_json)
                if isinstance(models_json, str)
                else models_json
            )
            changed = False
            for m in models:
                mid = m.get("model_id", "")
                inp = m.get("input_price") or 0
                out = m.get("output_price") or 0
                if (inp == 0 or out == 0) and mid in registry:
                    m["input_price"] = registry[mid]["input_price"]
                    m["output_price"] = registry[mid]["output_price"]
                    print(
                        f"  Fixed: {provider_name}/{mid} -> "
                        f"input={m['input_price']}, output={m['output_price']}"
                    )
                    changed = True
            if changed:
                await conn.execute(
                    text(
                        "UPDATE provider_settings SET models = :models WHERE id = :id"
                    ),
                    {"models": json.dumps(models), "id": setting_id},
                )
                updated += 1

    await engine.dispose()
    print(f"\nDone. Updated {updated} provider_settings records.")


if __name__ == "__main__":
    asyncio.run(main())
