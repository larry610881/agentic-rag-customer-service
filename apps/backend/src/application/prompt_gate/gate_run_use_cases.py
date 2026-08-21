"""Gate Run use cases：StartGateRun（前置 + 背景執行）/ Get / Estimate / 孤兒清理

執行機制（定案 8）：asyncio.create_task + prompt_gate_runs DB 持久化。
背景任務不碰 request-scoped session——DB 寫入一律在
independent_session_scope 內以 .provider factory 重新 resolve（Phase B 先例）。
影子執行走 HTTP 回打 /agent/chat（定案 C-1），驗的是含 interfaces 層的
完整真實路徑；JWT 從觸發者 request 剝下傳入（/validate 先例）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.prompt_gate.assertion_severity import resolve_severity
from src.domain.prompt_gate.entity import (
    BotConfigVersion,
    GateBlockedError,
)
from src.domain.prompt_gate.gate_run_entity import PromptGateRun
from src.domain.prompt_gate.verdict import (
    AssertionOutcome,
    CaseRoundResult,
    aggregate_cases,
    compute_verdict,
)
from src.domain.shared.exceptions import (
    DomainException,
    EntityNotFoundError,
)

logger = logging.getLogger(__name__)

# estimate 用的平均 token 假設（對齊 EstimateCostUseCase 的預設）
_AVG_INPUT_TOKENS = 1500
_AVG_OUTPUT_TOKENS = 400

_RESPONSE_SNIPPET_LIMIT = 4096  # 逐題報告 response 截斷上限（spec §4.5）


class GatePreconditionError(DomainException):
    """StartGateRun 前置檢查失敗；code 供測試與 router 對應 HTTP status。"""

    HTTP_STATUS = {
        "gate_not_enabled": 403,
        "gate_mode_off": 409,
        "no_dataset_bound": 422,
        "daily_limit_exceeded": 429,
        "budget_exceeded": 422,
        "no_history": 422,  # Phase G 回放：無真實對話可抽樣
    }

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.http_status = self.HTTP_STATUS.get(code, 400)
        super().__init__(message)


@dataclass(frozen=True)
class GateCase:
    """gate run 的執行單位（dataset 展開後的 case 快照）。"""

    case_id: str
    question: str
    priority: str
    assertions: list[dict] = field(default_factory=list)
    conversation_history: list[dict] = field(default_factory=list)


def _truncate_keep_ends(
    text: str, limit: int = _RESPONSE_SNIPPET_LIMIT
) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    head = limit * 2 // 3
    tail = limit - head
    return f"{text[:head]}\n…[truncated]…\n{text[-tail:]}", True


class StartGateRunUseCase:
    def __init__(
        self,
        bot_repository,
        tenant_repository,
        version_repository,
        gate_run_repository,
        eval_dataset_repository,
        api_base_url: str = "http://localhost:8000",
        # 背景任務用 provider factories（延遲 resolve，綁新 session）
        gate_run_repo_factory=None,
        version_repo_factory=None,
    ) -> None:
        self._bot_repo = bot_repository
        self._tenant_repo = tenant_repository
        self._version_repo = version_repository
        self._gate_run_repo = gate_run_repository
        self._eval_dataset_repo = eval_dataset_repository
        self._api_base_url = api_base_url
        self._gate_run_repo_factory = gate_run_repo_factory
        self._version_repo_factory = version_repo_factory

    # ── 題集組裝（平台通用集強制注入 ∪ 自訂集 enabled cases）──

    async def _collect_cases(
        self,
        bot_id: str,
        tenant_id: str,
        excluded_case_ids: frozenset[str] = frozenset(),
    ) -> tuple[list[GateCase], list[str], bool, list[str]]:
        """回傳 (cases, dataset_ids, has_custom_enabled, excluded_applied)。
        排除只施於平台通用集（定案更新 08-20：bot 級勾選子集，
        審計靠 run details 的 excluded_platform_cases）；
        自訂集用 case enabled toggle 即可（租戶有完整編輯權）。"""
        custom = await self._eval_dataset_repo.find_by_bot(bot_id, tenant_id)
        platform = await self._eval_dataset_repo.find_platform_base()

        cases: list[GateCase] = []
        dataset_ids: list[str] = []
        has_custom_enabled = False
        excluded_applied: list[str] = []
        seen_ds: set[str] = set()

        for ds in [*platform, *custom]:
            ds_id = ds.id.value
            if ds_id in seen_ds:
                continue  # bot 自訂集本身被標 platform 時不重複展開
            seen_ds.add(ds_id)
            enabled_cases = [tc for tc in ds.test_cases if tc.enabled]
            if ds.is_platform_base and excluded_case_ids:
                kept = []
                for tc in enabled_cases:
                    if tc.id.value in excluded_case_ids:
                        excluded_applied.append(tc.id.value)
                    else:
                        kept.append(tc)
                enabled_cases = kept
            if not enabled_cases:
                continue
            if not ds.is_platform_base:
                has_custom_enabled = True
            dataset_ids.append(ds_id)
            for tc in enabled_cases:
                cases.append(
                    GateCase(
                        case_id=f"{ds_id[:8]}:{tc.case_id}",
                        question=tc.question,
                        priority=tc.priority or "P1",
                        assertions=[
                            *list(ds.default_assertions or []),
                            *list(tc.assertions or []),
                        ],
                        conversation_history=list(
                            tc.conversation_history or []
                        ),
                    )
                )
        return cases, dataset_ids, has_custom_enabled, excluded_applied

    # ── estimate（§6：不改造既有 EstimateCostUseCase）──

    @staticmethod
    def _estimate(cases: list[GateCase], repeats: int, model: str) -> dict:
        per_call = RecordUsageUseCase._estimate_cost_from_registry(
            model or "", _AVG_INPUT_TOKENS, _AVG_OUTPUT_TOKENS
        ) or 0.01
        p0_count = sum(1 for c in cases if c.priority == "P0")
        history_msgs = sum(len(c.conversation_history) for c in cases)
        est_calls = len(cases) + max(repeats - 1, 0) * p0_count
        # history_override 一次帶入，不另打 API；成本近似含在該次呼叫的 input
        est_cost = est_calls * per_call
        return {
            "total_cases": len(cases),
            "p0_cases": p0_count,
            "repeats": repeats,
            "est_calls": est_calls,
            "history_messages": history_msgs,
            "cost_per_call": round(per_call, 6),
            "est_cost": round(est_cost, 4),
        }

    # ── 前置檢查 + 啟動 ──

    async def execute(
        self,
        *,
        tenant_id: str,
        bot_id: str,
        version_id: str,
        api_token: str,
        refresh_token: str = "",
        triggered_by: str | None = None,
    ) -> PromptGateRun:
        bot = await self._bot_repo.find_by_id(bot_id)
        if bot is None or bot.tenant_id != tenant_id:
            raise EntityNotFoundError("Bot", bot_id)

        tenant = await self._tenant_repo.find_by_id(tenant_id)
        if tenant is None or not tenant.prompt_gate_enabled:
            raise GatePreconditionError(
                "gate_not_enabled", "此租戶未開啟發布閘門功能"
            )
        if bot.gate_mode == "off":
            raise GatePreconditionError(
                "gate_mode_off", "此 bot 的 gate_mode 為 off"
            )

        version = await self._version_repo.find_by_id(version_id, tenant_id)
        if version is None or version.bot_id != bot_id:
            raise EntityNotFoundError("BotConfigVersion", version_id)

        cases, dataset_ids, has_custom, excluded_applied = (
            await self._collect_cases(
                bot_id,
                tenant_id,
                frozenset(bot.gate_excluded_cases or []),
            )
        )
        if not has_custom:
            raise GatePreconditionError(
                "no_dataset_bound",
                "須先設定問題集（至少 1 個含啟用案例的自訂題集）",
            )

        today = await self._gate_run_repo.count_today(bot_id)
        if today >= bot.gate_daily_limit:
            raise GatePreconditionError(
                "daily_limit_exceeded",
                f"已達每日驗證次數上限（{bot.gate_daily_limit}）",
            )

        estimate = self._estimate(cases, bot.gate_repeats, bot.llm_model)
        if estimate["est_cost"] > bot.gate_budget_usd:
            raise GatePreconditionError(
                "budget_exceeded",
                f"估算成本 ${estimate['est_cost']} 超過預算上限 "
                f"${bot.gate_budget_usd}（定案 C-4）",
            )

        run = PromptGateRun(
            tenant_id=tenant_id,
            bot_id=bot_id,
            version_id=version_id,
            dataset_ids=dataset_ids,
            repeats=bot.gate_repeats,
            soft_threshold=bot.gate_soft_threshold,
            est_cost=estimate["est_cost"],
            total_cases=len(cases),
            triggered_by=triggered_by,
        )
        version.mark_validating(run.id)  # 非法轉移在此 raise（409）
        await self._gate_run_repo.save(run)
        await self._version_repo.save(version)

        from src.application.prompt_gate._background import spawn_tracked
        spawn_tracked(
            self._execute_background(
                run_id=run.id,
                tenant_id=tenant_id,
                bot_id=bot_id,
                version_id=version_id,
                config_snapshot=dict(version.config_snapshot),
                cases=cases,
                repeats=bot.gate_repeats,
                soft_threshold=bot.gate_soft_threshold,
                budget_usd=bot.gate_budget_usd,
                api_token=api_token,
                refresh_token=refresh_token,
                excluded_platform_cases=excluded_applied,
            ),
            name=f"gate_run:{run.id}",  # M4：保存引用避免被 GC
        )
        return run

    # ── 背景執行 ──

    async def _save_background(self, run, version=None) -> None:
        """背景任務的 DB 寫入：independent session + 延遲 resolve repos。"""
        from src.infrastructure.db.session_middleware import (
            independent_session_scope,
        )

        async with independent_session_scope():
            gate_repo = (
                self._gate_run_repo_factory()
                if self._gate_run_repo_factory
                else self._gate_run_repo
            )
            await gate_repo.save(run)
            if version is not None:
                version_repo = (
                    self._version_repo_factory()
                    if self._version_repo_factory
                    else self._version_repo
                )
                await version_repo.save(version)

    async def _load_version_background(
        self, version_id: str, tenant_id: str
    ) -> BotConfigVersion | None:
        from src.infrastructure.db.session_middleware import (
            independent_session_scope,
        )

        async with independent_session_scope():
            version_repo = (
                self._version_repo_factory()
                if self._version_repo_factory
                else self._version_repo
            )
            found: BotConfigVersion | None = await version_repo.find_by_id(
                version_id, tenant_id
            )
            return found

    async def _execute_background(
        self,
        *,
        run_id: str,
        tenant_id: str,
        bot_id: str,
        version_id: str,
        config_snapshot: dict,
        cases: list[GateCase],
        repeats: int,
        soft_threshold: float,
        budget_usd: float,
        api_token: str,
        refresh_token: str = "",
        excluded_platform_cases: list[str] | None = None,
    ) -> None:
        from prompt_optimizer.api_client import AgentAPIClient

        run: PromptGateRun | None = None
        try:
            run = PromptGateRun(
                id=run_id, tenant_id=tenant_id, bot_id=bot_id,
                version_id=version_id, repeats=repeats,
                soft_threshold=soft_threshold,
            )
            # 以 DB 現值為準重載（est_cost 等欄位）
            from src.infrastructure.db.session_middleware import (
                independent_session_scope,
            )
            async with independent_session_scope():
                gate_repo = (
                    self._gate_run_repo_factory()
                    if self._gate_run_repo_factory
                    else self._gate_run_repo
                )
                loaded = await gate_repo.find_by_id(run_id, tenant_id)
            if loaded is not None:
                run = loaded

            run.mark_running()
            await self._save_background(run)

            api_client = AgentAPIClient(
                base_url=self._api_base_url,
                jwt_token=api_token,
                refresh_token=refresh_token,  # H3：長 run 中途 access token 過期可續期
                usage_category="eval_gate",
                run_id=run_id,
            )
            try:
                result = await self._run_rounds(
                    api_client=api_client,
                    bot_id=bot_id,
                    config_snapshot=config_snapshot,
                    cases=cases,
                    repeats=repeats,
                    budget_usd=budget_usd,
                )
            finally:
                await api_client.close()

            verdict = compute_verdict(
                aggregate_cases(result["rounds"]),
                soft_threshold=soft_threshold,
                budget_usd=budget_usd,
                actual_cost=result["actual_cost"],
            )
            run.verdict = None  # mark_completed 會設
            run.fail_reasons = list(verdict.fail_reasons)
            run.total_cases = verdict.total_cases
            run.hard_failed_cases = verdict.hard_failed_cases
            run.soft_pass_rate = round(verdict.soft_pass_rate, 4)
            run.unstable_cases = verdict.unstable_cases
            run.actual_cost = round(result["actual_cost"], 6)
            run.input_tokens = result["input_tokens"]
            run.output_tokens = result["output_tokens"]
            run.details = self._build_details(
                result, verdict,
                excluded_platform_cases=excluded_platform_cases or [],
            )
            run.mark_completed(passed=verdict.passed)

            version = await self._load_version_background(
                version_id, tenant_id
            )
            if version is not None:
                version.mark_validation_result(passed=verdict.passed)
                await self._save_background(run, version)
            else:
                await self._save_background(run)
        except Exception as exc:
            logger.exception("gate_run.background_error run_id=%s", run_id)
            try:
                if run is not None:
                    run.mark_error(str(exc))
                version = await self._load_version_background(
                    version_id, tenant_id
                )
                if version is not None and version.status == "validating":
                    version.mark_validation_aborted()
                await self._save_background(run, version)
            except Exception:
                logger.exception(
                    "gate_run.error_cleanup_failed run_id=%s", run_id
                )

    async def _run_rounds(
        self,
        *,
        api_client,
        bot_id: str,
        config_snapshot: dict,
        cases: list[GateCase],
        repeats: int,
        budget_usd: float,
    ) -> dict:
        """Round 策略（定案 7）：Round 1 全部 case；Round 2..repeats 只跑 P0。
        逐 case 累計成本，超過預算立即中止（budget verdict 由 Verdict Engine 判）。"""
        rounds: list[CaseRoundResult] = []
        case_reports: dict[str, dict] = {
            c.case_id: {
                "case_id": c.case_id,
                "question": c.question,
                "priority": c.priority,
                "rounds": [],
            }
            for c in cases
        }
        actual_cost = 0.0
        input_tokens = 0
        output_tokens = 0
        aborted = False

        for round_idx in range(max(repeats, 1)):
            targets = (
                cases
                if round_idx == 0
                else [c for c in cases if c.priority == "P0"]
            )
            if aborted:
                break
            for case in targets:
                cr = await self._run_single_case(
                    api_client, bot_id, case, config_snapshot
                )
                usage = cr.usage or {}
                cost = float(usage.get("estimated_cost") or 0.0)
                actual_cost += cost
                input_tokens += int(usage.get("input_tokens") or 0)
                output_tokens += int(usage.get("output_tokens") or 0)

                outcomes = self._assert_case(case, cr)
                rounds.append(
                    CaseRoundResult(
                        case_id=case.case_id,
                        priority=case.priority,
                        round_index=round_idx,
                        assertions=tuple(outcomes),
                    )
                )
                snippet, truncated = _truncate_keep_ends(cr.answer or "")
                case_reports[case.case_id]["rounds"].append(
                    {
                        "round": round_idx,
                        "response_text": snippet,
                        "truncated": truncated,
                        "assertions": [
                            {
                                "type": o.type,
                                "severity": o.severity,
                                "passed": o.passed,
                                "message": o.message,
                            }
                            for o in outcomes
                        ],
                        "latency_ms": cr.latency_ms,
                        "tokens": int(usage.get("total_tokens") or 0),
                        "cost": round(cost, 6),
                        "trace_id": cr.trace_id,
                        "trace_nodes": cr.trace_nodes,
                    }
                )
                if actual_cost > budget_usd:
                    aborted = True
                    break

        return {
            "rounds": rounds,
            "case_reports": case_reports,
            "actual_cost": actual_cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "aborted": aborted,
        }

    async def _run_single_case(
        self, api_client, bot_id: str, case: GateCase, config_snapshot: dict
    ):
        from prompt_optimizer.api_client import ChatResult

        try:
            return await api_client.chat(
                message=case.question,
                bot_id=bot_id,
                config_override=config_snapshot,
                test_mode=True,
                history_override=case.conversation_history or None,
            )
        except Exception as exc:
            logger.warning(
                "gate_run.case_api_error case=%s: %s", case.case_id, exc
            )
            return ChatResult(
                answer="", conversation_id="", tool_calls=[], sources=[]
            )

    @staticmethod
    def _assert_case(case: GateCase, cr) -> list[AssertionOutcome]:
        from prompt_optimizer.assertions import (
            AssertionContext,
            run_assertion,
        )

        usage = cr.usage or {}
        ctx = AssertionContext(
            response_text=cr.answer or "",
            tool_calls=cr.tool_calls or [],
            sources=cr.sources or [],
            user_message=case.question,
            conversation_history=case.conversation_history or [],
            latency_ms=cr.latency_ms,
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
            estimated_cost=float(usage.get("estimated_cost") or 0.0),
        )
        outcomes: list[AssertionOutcome] = []
        if not (cr.answer or "").strip():
            outcomes.append(
                AssertionOutcome(
                    type="api_error", severity="hard", passed=False,
                    message="Empty response (API failure)",
                )
            )
            return outcomes
        for a in case.assertions:
            a_type = a.get("type", "")
            params = dict(a.get("params", {}))
            severity = resolve_severity(a_type, params)
            params.pop("severity", None)  # 斷言函式是 kw-only，剔除非參數 key
            result = run_assertion(a_type, ctx, params)
            outcomes.append(
                AssertionOutcome(
                    type=a_type,
                    severity=severity,
                    passed=result.passed,
                    message=result.message,
                )
            )
        return outcomes

    @staticmethod
    def _build_details(
        result: dict, verdict, *,
        excluded_platform_cases: list[str] | None = None,
    ) -> dict:
        cases = []
        for case_id, report in result["case_reports"].items():
            agg = verdict.cases.get(case_id)
            cases.append(
                {
                    **report,
                    "pass_rate": agg.soft_pass_rate if agg else None,
                    "soft_passed": agg.soft_passed if agg else None,
                    "hard_failed": agg.hard_failed if agg else None,
                    "unstable": agg.unstable if agg else None,
                }
            )
        return {
            "cases": cases,
            "aborted": result["aborted"],
            # 審計：本次 run 被 bot 設定排除的平台題（定案更新 08-20）
            "excluded_platform_cases": excluded_platform_cases or [],
        }


class GetGateRunUseCase:
    def __init__(self, gate_run_repository) -> None:
        self._gate_run_repo = gate_run_repository

    async def execute(self, tenant_id: str, run_id: str) -> PromptGateRun:
        run: PromptGateRun | None = await self._gate_run_repo.find_by_id(
            run_id, tenant_id
        )
        if run is None:
            raise EntityNotFoundError("PromptGateRun", run_id)
        return run


class GateEstimateUseCase:
    """驗證前成本預檢（spec §2.6：驗證前必跑並顯示給操作者）。"""

    def __init__(
        self,
        bot_repository,
        eval_dataset_repository,
    ) -> None:
        self._bot_repo = bot_repository
        self._eval_dataset_repo = eval_dataset_repository

    async def execute(self, tenant_id: str, bot_id: str) -> dict:
        bot = await self._bot_repo.find_by_id(bot_id)
        if bot is None or bot.tenant_id != tenant_id:
            raise EntityNotFoundError("Bot", bot_id)
        helper = StartGateRunUseCase(
            bot_repository=self._bot_repo,
            tenant_repository=None,
            version_repository=None,
            gate_run_repository=None,
            eval_dataset_repository=self._eval_dataset_repo,
        )
        cases, dataset_ids, has_custom, excluded_applied = (
            await helper._collect_cases(
                bot_id,
                tenant_id,
                frozenset(bot.gate_excluded_cases or []),
            )
        )
        estimate = StartGateRunUseCase._estimate(
            cases, bot.gate_repeats, bot.llm_model
        )
        return {
            **estimate,
            "dataset_ids": dataset_ids,
            "has_custom_enabled": has_custom,
            "excluded_platform_cases": excluded_applied,
            "budget_usd": bot.gate_budget_usd,
            "within_budget": estimate["est_cost"] <= bot.gate_budget_usd,
        }


class CleanupOrphanGateRunsUseCase:
    """啟動時一次性清孤兒（fail-open）：queued/running run → error、
    validating 版本 → draft。"""

    def __init__(self, gate_run_repository, version_repository) -> None:
        self._gate_run_repo = gate_run_repository
        self._version_repo = version_repository

    async def execute(self) -> int:
        version_ids = await self._gate_run_repo.mark_orphans_error()
        if version_ids:
            await self._version_repo.revert_validating_to_draft(version_ids)
        # M5：mark_orphans_error 只撈 queued/running run，撈不到「run 已 completed 但
        # 版本仍卡 validating」的孤兒（非同交易寫入間進程被砍）。額外 revert 所有
        # validating 且 run 非 running 的版本，否則該版本三個 API 全 409、無 API 可解。
        stale = 0
        if hasattr(self._version_repo, "revert_stale_validating_versions"):
            stale = await self._version_repo.revert_stale_validating_versions()
        logger.info(
            "gate_run.orphans_cleaned runs=%d stale_versions_reverted=%d",
            len(version_ids), stale,
        )
        return len(version_ids)


__all__ = [
    "CleanupOrphanGateRunsUseCase",
    "GateBlockedError",
    "GateCase",
    "GateEstimateUseCase",
    "GatePreconditionError",
    "GetGateRunUseCase",
    "StartGateRunUseCase",
]
