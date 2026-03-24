"""Prompt Optimizer CLI entry point.

Usage:
    python -m prompt_optimizer run --dataset datasets/ecommerce_example.yaml --api-url http://localhost:8001 --api-token TOKEN --db-url postgresql://...
    python -m prompt_optimizer run --dataset ds.yaml --dry-run
    python -m prompt_optimizer rollback --run-id abc123 --iteration 0 --db-url postgresql://...
    python -m prompt_optimizer report --run-id abc123 --db-url postgresql://...
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_import(args: argparse.Namespace) -> None:
    """Import YAML dataset into DB."""
    from prompt_optimizer.dataset import DatasetLoader
    from prompt_optimizer.db_client import PromptDBClient

    if not args.db_url:
        print("ERROR: --db-url is required", file=sys.stderr)
        sys.exit(1)

    file_path = Path(args.file)
    if not file_path.exists() and not file_path.is_absolute():
        # Try relative to prompt_optimizer package
        file_path = Path(__file__).parent / file_path
    if not file_path.exists():
        print(f"ERROR: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    loader = DatasetLoader()
    dataset = loader.load(file_path)

    db_client = PromptDBClient(db_url=args.db_url)
    try:
        dataset_id = db_client.import_dataset(dataset)
    finally:
        db_client.close()

    print(f"Imported: {dataset.metadata.description} ({len(dataset.test_cases)} cases)")
    print(f"Dataset ID: {dataset_id}")


def cmd_run(args: argparse.Namespace) -> None:
    """Run optimization loop."""
    from prompt_optimizer.api_client import AgentAPIClient
    from prompt_optimizer.config import CostConfig, OptimizationConfig, PromptTarget
    from prompt_optimizer.dataset import DatasetLoader
    from prompt_optimizer.db_client import PromptDBClient
    from prompt_optimizer.evaluator import Evaluator
    from prompt_optimizer.mutator import PromptMutator
    from prompt_optimizer.report import generate_terminal_report
    from prompt_optimizer.runner import KarpathyLoopRunner

    # Load dataset (from file or DB)
    if args.dataset:
        dataset_path = Path(args.dataset)
        if not dataset_path.is_absolute():
            dataset_path = Path(__file__).parent / dataset_path
        loader = DatasetLoader()
        dataset = loader.load(dataset_path)
    elif args.dataset_id:
        if not args.db_url:
            print("ERROR: --db-url is required with --dataset-id", file=sys.stderr)
            sys.exit(1)
        db_client_for_ds = PromptDBClient(db_url=args.db_url)
        dataset = db_client_for_ds.read_dataset(args.dataset_id)
        db_client_for_ds.close()
    else:
        print("ERROR: --dataset or --dataset-id is required", file=sys.stderr)
        sys.exit(1)

    print(
        f"Dataset loaded: {dataset.metadata.description} "
        f"({len(dataset.test_cases)} cases)"
    )

    # Determine target
    target_field = args.target or dataset.metadata.target_prompt
    target_level = (
        "system"
        if target_field in ("base_prompt", "router_mode_prompt", "react_mode_prompt")
        else "bot"
    )
    target = PromptTarget(
        level=target_level,
        field=target_field,
        bot_id=dataset.metadata.bot_id or args.bot_id,
        tenant_id=dataset.metadata.tenant_id or args.tenant_id or "",
    )

    config = OptimizationConfig(
        api_base_url=args.api_url,
        api_token=args.api_token or "",
        db_url=args.db_url or "",
        target=target,
        max_iterations=args.max_iterations,
        patience=args.patience,
        budget=args.budget,
        mutator_model=args.mutator_model,
        dry_run=args.dry_run,
        cost_config=CostConfig(
            token_budget=dataset.metadata.cost_config.token_budget,
            quality_weight=dataset.metadata.cost_config.quality_weight,
            cost_weight=dataset.metadata.cost_config.cost_weight,
        ),
    )

    # Create clients
    api_client = AgentAPIClient(
        base_url=config.api_base_url, jwt_token=config.api_token
    )
    db_client = PromptDBClient(db_url=config.db_url) if config.db_url else None

    if db_client is None and not config.dry_run:
        print("ERROR: --db-url is required for non-dry-run mode", file=sys.stderr)
        sys.exit(1)

    read_prompt = db_client.read_prompt if db_client else lambda t: "(no db)"
    write_prompt = db_client.write_prompt if db_client else lambda t, p: None

    runner = KarpathyLoopRunner(
        api_client=api_client,
        db_read_prompt=read_prompt,
        db_write_prompt=write_prompt,
        evaluator=Evaluator(),
        mutator=PromptMutator(model=config.mutator_model),
    )

    # Run
    try:
        result = asyncio.run(runner.run(config, dataset))
    finally:
        asyncio.run(api_client.close())
        if db_client:
            db_client.close()

    # Report
    print(generate_terminal_report(result))


def cmd_rollback(args: argparse.Namespace) -> None:
    """Rollback to a specific iteration's prompt."""
    from prompt_optimizer.config import PromptTarget
    from prompt_optimizer.db_client import PromptDBClient
    from prompt_optimizer.history import RunHistoryClient

    if not args.db_url:
        print("ERROR: --db-url is required", file=sys.stderr)
        sys.exit(1)

    history = RunHistoryClient(args.db_url)
    iterations = history.get_run(args.run_id)

    if not iterations:
        print(f"ERROR: Run {args.run_id} not found", file=sys.stderr)
        sys.exit(1)

    target_iter = None
    for it in iterations:
        if it["iteration"] == args.iteration:
            target_iter = it
            break

    if target_iter is None:
        print(
            f"ERROR: Iteration {args.iteration} not found in run {args.run_id}",
            file=sys.stderr,
        )
        sys.exit(1)

    target = PromptTarget(
        level="bot" if target_iter["bot_id"] else "system",
        field=target_iter["target_field"],
        bot_id=target_iter["bot_id"],
        tenant_id=target_iter["tenant_id"],
    )

    db_client = PromptDBClient(args.db_url)
    db_client.write_prompt(target, target_iter["prompt_snapshot"])
    db_client.close()
    history.close()

    print(
        f"Rolled back to iteration {args.iteration} (score: {target_iter['score']:.4f})"
    )


def cmd_report(args: argparse.Namespace) -> None:
    """Show report for a past run."""
    from prompt_optimizer.history import RunHistoryClient

    if not args.db_url:
        print("ERROR: --db-url is required", file=sys.stderr)
        sys.exit(1)

    history = RunHistoryClient(args.db_url)
    iterations = history.get_run(args.run_id)
    history.close()

    if not iterations:
        print(f"ERROR: Run {args.run_id} not found", file=sys.stderr)
        sys.exit(1)

    print(f"\nRun: {args.run_id}")
    print(f"Target: {iterations[0]['target_field']}")
    print(f"Iterations: {len(iterations)}")
    print(f"\n{'#':>3}  {'Score':>8}  {'Passed':>6}  {'Total':>5}  {'Best':>4}")
    print(f"{'---':>3}  {'--------':>8}  {'------':>6}  {'-----':>5}  {'----':>4}")
    for it in iterations:
        best = "★" if it["is_best"] else ""
        print(
            f"{it['iteration']:>3}  {it['score']:>8.4f}  "
            f"{it['passed_count']:>6}  {it['total_count']:>5}  {best:>4}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="prompt_optimizer",
        description="AutoResearch Prompt Optimizer — Karpathy Loop",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # run
    run_parser = subparsers.add_parser("run", help="Run optimization loop")
    run_parser.add_argument("--dataset", default="", help="Path to dataset YAML")
    run_parser.add_argument(
        "--dataset-id", default="", help="Dataset ID from DB (alternative to --dataset)"
    )
    run_parser.add_argument(
        "--api-url", default="http://localhost:8001", help="Backend API URL"
    )
    run_parser.add_argument("--api-token", default="", help="JWT token")
    run_parser.add_argument("--db-url", default="", help="Database URL")
    run_parser.add_argument(
        "--target", default="", help="Prompt target field (or 'cascade')"
    )
    run_parser.add_argument("--bot-id", default="", help="Bot ID override")
    run_parser.add_argument("--tenant-id", default="", help="Tenant ID override")
    run_parser.add_argument(
        "--max-iterations", type=int, default=20, help="Max iterations"
    )
    run_parser.add_argument(
        "--patience", type=int, default=5, help="Early stop patience"
    )
    run_parser.add_argument("--budget", type=int, default=200, help="Max API calls")
    run_parser.add_argument(
        "--mutator-model", default="gpt-4o-mini", help="Mutator LLM model"
    )
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Eval only, no mutation"
    )

    # rollback
    rb_parser = subparsers.add_parser("rollback", help="Rollback to iteration")
    rb_parser.add_argument("--run-id", required=True, help="Run ID")
    rb_parser.add_argument(
        "--iteration", type=int, required=True, help="Iteration number"
    )
    rb_parser.add_argument("--db-url", required=True, help="Database URL")

    # report
    rpt_parser = subparsers.add_parser("report", help="Show run report")
    rpt_parser.add_argument("--run-id", required=True, help="Run ID")
    rpt_parser.add_argument("--db-url", required=True, help="Database URL")

    # import
    import_parser = subparsers.add_parser("import", help="Import YAML dataset into DB")
    import_parser.add_argument("--file", required=True, help="Path to YAML dataset file")
    import_parser.add_argument("--db-url", required=True, help="Database URL")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "run":
        cmd_run(args)
    elif args.command == "rollback":
        cmd_rollback(args)
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "import":
        cmd_import(args)


if __name__ == "__main__":
    main()
