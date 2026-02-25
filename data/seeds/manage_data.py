"""Unified CLI for Olist data management.

Usage:
    python manage_data.py download              # Download Kaggle CSV
    python manage_data.py seed                  # Seed DB (auto mode)
    python manage_data.py seed --mock           # Force mock data
    python manage_data.py seed --kaggle         # Force Kaggle CSV
    python manage_data.py reset                 # Reset Olist tables only
    python manage_data.py reset --all           # Reset all tables
    python manage_data.py status                # Show table row counts
    python manage_data.py enrich                # Generate synthetic product catalog
    python manage_data.py vectorize             # Vectorize product catalog → system KB → Qdrant
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Ensure data/seeds is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

import download_kaggle  # noqa: E402
import generate_synthetic_products  # noqa: E402
import seed_postgres  # noqa: E402
import seed_product_knowledge  # noqa: E402

import asyncpg  # noqa: E402


def _get_dsn() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/agentic_rag",
    )


async def _cmd_seed(args: argparse.Namespace) -> None:
    if args.kaggle:
        mode = "kaggle"
    elif args.mock:
        mode = "mock"
    else:
        mode = "auto"
    await seed_postgres.seed(database_url=_get_dsn(), mode=mode)


async def _cmd_reset(args: argparse.Namespace) -> None:
    conn = await asyncpg.connect(_get_dsn())
    try:
        if args.all:
            await seed_postgres.reset_all(conn)
        else:
            await seed_postgres.reset_olist(conn)
    finally:
        await conn.close()


async def _cmd_status(_args: argparse.Namespace) -> None:
    conn = await asyncpg.connect(_get_dsn())
    try:
        counts = await seed_postgres.status(conn)
    finally:
        await conn.close()

    mode = seed_postgres._detect_mode(counts)
    print(f"\nData mode: {mode}")
    print(f"{'Table':<35} {'Rows':>10}")
    print("-" * 47)

    total = 0
    for table, count in counts.items():
        if count < 0:
            print(f"  {table:<33} {'N/A':>10}")
        else:
            print(f"  {table:<33} {count:>10,}")
            total += count

    print("-" * 47)
    print(f"  {'TOTAL':<33} {total:>10,}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Olist data management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # download
    sub.add_parser("download", help="Download Kaggle Olist CSV dataset")

    # seed
    seed_p = sub.add_parser("seed", help="Seed database with Olist data")
    seed_group = seed_p.add_mutually_exclusive_group()
    seed_group.add_argument("--mock", action="store_true", help="Force mock data")
    seed_group.add_argument("--kaggle", action="store_true", help="Force Kaggle CSV data")

    # reset
    reset_p = sub.add_parser("reset", help="Reset (truncate) tables")
    reset_p.add_argument("--all", action="store_true", help="Reset all tables (Olist + App)")

    # status
    sub.add_parser("status", help="Show table row counts and data mode")

    # enrich
    sub.add_parser("enrich", help="Generate synthetic product catalog from Olist data")

    # vectorize
    sub.add_parser("vectorize", help="Vectorize product catalog into system KB + Qdrant")

    args = parser.parse_args()

    if args.command == "download":
        download_kaggle.main()
    elif args.command == "seed":
        asyncio.run(_cmd_seed(args))
    elif args.command == "reset":
        asyncio.run(_cmd_reset(args))
    elif args.command == "status":
        asyncio.run(_cmd_status(args))
    elif args.command == "enrich":
        asyncio.run(generate_synthetic_products.generate(_get_dsn()))
    elif args.command == "vectorize":
        asyncio.run(seed_product_knowledge.vectorize(_get_dsn()))


if __name__ == "__main__":
    main()
