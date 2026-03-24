"""Optimization run report generator."""

from __future__ import annotations

from prompt_optimizer.runner import RunResult


def generate_terminal_report(result: RunResult) -> str:
    """Generate a colorful terminal report from a RunResult."""
    lines: list[str] = []

    BOLD = "\033[1m"
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    RESET = "\033[0m"
    DIM = "\033[2m"

    lines.append(f"\n{BOLD}{'=' * 60}{RESET}")
    lines.append(f"{BOLD}  Prompt Optimizer — Run Report{RESET}")
    lines.append(f"{BOLD}{'=' * 60}{RESET}")

    # Summary
    lines.append(f"\n{CYAN}Run ID:{RESET}     {result.run_id}")
    lines.append(
        f"{CYAN}Target:{RESET}     {result.target.level}.{result.target.field}"
    )
    if result.target.bot_id:
        lines.append(f"{CYAN}Bot ID:{RESET}     {result.target.bot_id}")
    lines.append(f"{CYAN}Stopped:{RESET}    {result.stopped_reason}")

    # Score progression
    baseline = result.baseline_score
    best = result.best_score
    delta = best - baseline
    delta_pct = (delta / baseline * 100) if baseline > 0 else 0
    color = GREEN if delta > 0 else (RED if delta < 0 else YELLOW)

    lines.append(f"\n{BOLD}分數變化:{RESET}")
    lines.append(f"  Baseline:  {baseline:.4f}")
    lines.append(
        f"  Best:      {color}{best:.4f} "
        f"({'+' if delta >= 0 else ''}{delta:.4f}, "
        f"{'+' if delta_pct >= 0 else ''}{delta_pct:.1f}%){RESET}"
    )
    lines.append(f"  Iterations: {len(result.iterations) - 1}")  # -1 for baseline
    lines.append(f"  API Calls:  {result.total_api_calls}")

    # Per-iteration table
    lines.append(f"\n{BOLD}迭代歷史:{RESET}")
    lines.append(f"  {'#':>3}  {'Score':>8}  {'Best':>5}  {'Status':<10}")
    lines.append(f"  {'---':>3}  {'--------':>8}  {'-----':>5}  {'----------':<10}")
    for it in result.iterations:
        score_str = f"{it.eval_summary.final_score:.4f}"
        best_mark = f"{GREEN}★{RESET}" if it.is_best else " "
        status = f"{GREEN}ACCEPTED{RESET}" if it.accepted else f"{DIM}discarded{RESET}"
        if it.iteration == 0:
            status = f"{CYAN}baseline{RESET}"
        lines.append(f"  {it.iteration:>3}  {score_str:>8}  {best_mark:>5}  {status}")

    # Cost analysis (if available)
    if result.iterations:
        first = result.iterations[0].eval_summary
        last = result.iterations[-1].eval_summary
        if first.avg_total_tokens > 0:
            lines.append(f"\n{BOLD}成本分析:{RESET}")
            token_delta = last.avg_total_tokens - first.avg_total_tokens
            token_pct = (
                (token_delta / first.avg_total_tokens * 100)
                if first.avg_total_tokens
                else 0
            )
            lines.append(
                f"  Avg tokens: {first.avg_total_tokens} → {last.avg_total_tokens} "
                f"({'+' if token_pct >= 0 else ''}{token_pct:.0f}%)"
            )
            if first.avg_cost_per_call > 0:
                cost_delta = last.avg_cost_per_call - first.avg_cost_per_call
                cost_pct = cost_delta / first.avg_cost_per_call * 100
                lines.append(
                    f"  Avg cost:   ${first.avg_cost_per_call:.4f} → "
                    f"${last.avg_cost_per_call:.4f} "
                    f"({'+' if cost_pct >= 0 else ''}{cost_pct:.0f}%)"
                )
            lines.append(f"  Total cost: ${last.total_run_cost:.4f}")

    # Category breakdown (if cases have categories)
    categories: dict[str, list[float]] = {}
    if result.iterations and result.iterations[-1].eval_summary.case_results:
        for cr in result.iterations[-1].eval_summary.case_results:
            if cr.category:
                categories.setdefault(cr.category, []).append(cr.score)

    if categories:
        lines.append(f"\n{BOLD}分類明細:{RESET}")
        for cat, scores in sorted(categories.items()):
            avg = sum(scores) / len(scores)
            bar_len = int(avg * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            color = GREEN if avg >= 0.8 else (YELLOW if avg >= 0.5 else RED)
            lines.append(f"  {cat:<25} {color}{bar} {avg:.0%}{RESET}")

    # P0 failures
    if result.iterations:
        last_summary = result.iterations[-1].eval_summary
        if last_summary.p0_failures:
            lines.append(f"\n{RED}{BOLD}P0 失敗:{RESET}")
            for case_id in last_summary.p0_failures:
                lines.append(f"  {RED}✗{RESET} {case_id}")

    lines.append(f"\n{BOLD}{'=' * 60}{RESET}\n")

    return "\n".join(lines)


def generate_markdown_report(result: RunResult) -> str:
    """Generate a Markdown report from a RunResult."""
    lines: list[str] = []

    lines.append("# Prompt Optimizer — Run Report\n")
    lines.append(f"- **Run ID**: `{result.run_id}`")
    lines.append(f"- **Target**: `{result.target.level}.{result.target.field}`")
    if result.target.bot_id:
        lines.append(f"- **Bot ID**: `{result.target.bot_id}`")
    lines.append(f"- **Stopped**: {result.stopped_reason}")
    lines.append(f"- **Iterations**: {len(result.iterations) - 1}")
    lines.append(f"- **API Calls**: {result.total_api_calls}")

    baseline = result.baseline_score
    best = result.best_score
    delta = best - baseline

    lines.append("\n## Score Summary\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Baseline | {baseline:.4f} |")
    lines.append(f"| Best | {best:.4f} |")
    delta_pct = (delta / baseline * 100) if baseline else 0
    lines.append(
        f"| Delta | {'+' if delta >= 0 else ''}{delta:.4f} ({delta_pct:+.1f}%) |"
    )

    lines.append("\n## Iteration History\n")
    lines.append("| # | Score | Best | Status |")
    lines.append("|---|-------|------|--------|")
    for it in result.iterations:
        best_mark = "★" if it.is_best else ""
        status = "ACCEPTED" if it.accepted else "discarded"
        if it.iteration == 0:
            status = "baseline"
        lines.append(
            f"| {it.iteration} | {it.eval_summary.final_score:.4f} "
            f"| {best_mark} | {status} |"
        )

    # P0 failures
    if result.iterations:
        last = result.iterations[-1].eval_summary
        if last.p0_failures:
            lines.append("\n## P0 Failures\n")
            for case_id in last.p0_failures:
                lines.append(f"- ✗ {case_id}")

    return "\n".join(lines)
