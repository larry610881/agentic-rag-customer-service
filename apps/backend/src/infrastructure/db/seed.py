"""Entry point for `make seed-data`.

Run from monorepo root: python data/seeds/seed_postgres.py
Or via Makefile: make seed-data
"""

import asyncio
import importlib.util
import sys
from pathlib import Path


def main() -> None:
    # Locate seed_postgres.py relative to this file
    seed_script = (
        Path(__file__).resolve().parent.parent.parent.parent.parent.parent
        / "data"
        / "seeds"
        / "seed_postgres.py"
    )
    if not seed_script.exists():
        print(f"ERROR: seed script not found at {seed_script}")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("seed_postgres", seed_script)
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    asyncio.run(module.seed())


if __name__ == "__main__":
    main()
