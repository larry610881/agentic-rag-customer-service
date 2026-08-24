"""Phase G — 真實流量回放 pairwise 對比（spec §14 層次 2）

抽該 bot 最近 N 則真實使用者問題 → baseline（線上快照）與 candidate
（目標版本快照）各影子執行一次 → LLM judge 換位雙判 → win/lose/tie。

結果復用 `prompt_gate_runs`（details.type="replay_compare"，零 migration），
前端沿用 GET /prompt-gate/runs/{id} polling。token 消耗計入租戶
（受測對話 X-Usage-Category=eval_gate + run_id 歸因；judge 另計）。
與日限額 / 預算共用 bot 的 gate_daily_limit / gate_budget_usd。
"""

from __future__ import annotations

import asyncio
import logging

from src.application.prompt_gate.gate_run_use_cases import (
    GatePreconditionError,
    _truncate_keep_ends,
)
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.domain.prompt_gate.entity import STATUS_PUBLISHED
from src.domain.prompt_gate.gate_run_entity import PromptGateRun
from src.domain.prompt_gate.replay import (
    RESULT_TIE,
    ReplayQuestionResult,
    aggregate_replay,
    consistent_verdict,
)
from src.domain.shared.exceptions import EntityNotFoundError

logger = logging.getLogger(__name__)

_JUDGE_PROMPT = """你是客服回覆品質評審。針對同一個使用者問題，比較兩個客服回答哪個更好
（正確性、切題度、語氣、簡潔）。只回覆一個字元：「1」（回答一較佳）、
「2」（回答二較佳）或「平手」。

## 使用者問題
{question}

## 回答一
{answer_a}

## 回答二
{answer_b}

你的判定（只回 1 / 2 / 平手）："""


class PairwiseJudge:
    """LLM pairwise 評審（換位雙判由呼叫端負責）。
    沿 mutator 先例用 langchain ChatOpenAI；失敗由呼叫端 fail-open 處理。"""

    def __init__(
        self, api_key: str = "", model: str = "gpt-4o-mini", on_usage=None
    ) -> None:
        self._api_key = api_key or None
        self._model = model
        # H5：每次 judge 呼叫的 token 用量回呼（記帳），原本 usage_metadata 被丟棄
        self._on_usage = on_usage

    async def judge(
        self, question: str, answer_a: str, answer_b: str
    ) -> str:
        from langchain_core.messages import HumanMessage
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=self._model,
            temperature=0.0,
            api_key=self._api_key,  # type: ignore[arg-type]  # 同 mutator 先例
        )
        prompt = _JUDGE_PROMPT.format(
            question=question,
            answer_a=answer_a[:2000],
            answer_b=answer_b[:2000],
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        if self._on_usage is not None:
            meta = getattr(response, "usage_metadata", None) or {}
            if meta:
                resp_meta = getattr(response, "response_metadata", None) or {}
                model_name = (
                    resp_meta.get("model_name")
                    or resp_meta.get("model")
                    or self._model
                )
                await self._on_usage(model_name, meta)
        return str(response.content).strip()


class StartReplayCompareUseCase:
    """前置檢查 + 背景執行（asyncio.create_task，與 gate run 同模式）。"""

    def __init__(
        self,
        bot_repository,
        version_repository,
        gate_run_repository,
        conversation_repository,
        provider_setting_repository=None,
        encryption_service=None,
        api_base_url: str = "http://localhost:8000",
        gate_run_repo_factory=None,
        record_usage_factory=None,
    ) -> None:
        self._bot_repo = bot_repository
        self._version_repo = version_repository
        self._gate_run_repo = gate_run_repository
        self._conversation_repo = conversation_repository
        self._provider_repo = provider_setting_repository
        self._encryption = encryption_service
        self._api_base_url = api_base_url
        self._gate_run_repo_factory = gate_run_repo_factory
        self._record_usage_factory = record_usage_factory

    async def _resolve_judge_api_key(self) -> str:
        if self._provider_repo is None or self._encryption is None:
            return ""
        try:
            settings = await self._provider_repo.find_all()
            for s in settings:
                if (
                    s.provider_type.value == "llm"
                    and s.is_enabled
                    and s.api_key_encrypted
                ):
                    return str(self._encryption.decrypt(s.api_key_encrypted))
        except Exception:
            logger.warning("replay.judge_key_resolve_failed", exc_info=True)
        return ""

    async def execute(
        self,
        *,
        tenant_id: str,
        bot_id: str,
        version_id: str,
        api_token: str,
        refresh_token: str = "",
        sample_size: int = 10,
        triggered_by: str | None = None,
    ) -> PromptGateRun:
        bot = await self._bot_repo.find_by_id(bot_id)
        if bot is None or bot.tenant_id != tenant_id:
            raise EntityNotFoundError("Bot", bot_id)

        candidate = await self._version_repo.find_by_id(version_id, tenant_id)
        if candidate is None or candidate.bot_id != bot_id:
            raise EntityNotFoundError("BotConfigVersion", version_id)

        current = await self._version_repo.find_current(bot_id)
        baseline_snapshot = (
            dict(current.config_snapshot)
            if current is not None and current.status == STATUS_PUBLISHED
            else {}
        )

        sample_size = max(1, min(sample_size, 30))
        questions = await self._conversation_repo.find_recent_user_questions(
            bot_id, tenant_id, limit=sample_size
        )
        if not questions:
            raise GatePreconditionError(
                "no_history", "此 bot 尚無真實使用者對話可供回放"
            )

        today = await self._gate_run_repo.count_today(bot_id)
        if today >= bot.gate_daily_limit:
            raise GatePreconditionError(
                "daily_limit_exceeded",
                f"已達每日驗證次數上限（{bot.gate_daily_limit}）",
            )

        # 估算：每題 2 次受測呼叫 + 2 次 judge（成本近似受測呼叫）
        per_call = RecordUsageUseCase._estimate_cost_from_registry(
            bot.llm_model or "", 1500, 400
        ) or 0.01
        est_cost = round(len(questions) * per_call * 2.5, 4)
        if est_cost > bot.gate_budget_usd:
            raise GatePreconditionError(
                "budget_exceeded",
                f"估算成本 ${est_cost} 超過預算上限 ${bot.gate_budget_usd}",
            )

        judge_api_key = await self._resolve_judge_api_key()

        run = PromptGateRun(
            tenant_id=tenant_id,
            bot_id=bot_id,
            version_id=version_id,
            repeats=1,
            soft_threshold=bot.gate_soft_threshold,
            est_cost=est_cost,
            total_cases=len(questions),
            triggered_by=triggered_by,
            details={"type": "replay_compare"},
        )
        await self._gate_run_repo.save(run)

        from src.application.prompt_gate._background import spawn_tracked
        spawn_tracked(
            self._execute_background(
                run_id=run.id,
                tenant_id=tenant_id,
                bot_id=bot_id,
                baseline_snapshot=baseline_snapshot,
                candidate_snapshot=dict(candidate.config_snapshot),
                questions=questions,
                budget_usd=bot.gate_budget_usd,
                api_token=api_token,
                refresh_token=refresh_token,
                judge_api_key=judge_api_key,
            ),
            name=f"replay_compare:{run.id}",  # M4
        )
        return run

    async def _save_background(self, run: PromptGateRun) -> None:
        from src.infrastructure.db.session_middleware import (
            independent_session_scope,
        )

        async with independent_session_scope():
            repo = (
                self._gate_run_repo_factory()
                if self._gate_run_repo_factory
                else self._gate_run_repo
            )
            await repo.save(run)

    def _make_judge_usage_recorder(
        self, *, tenant_id: str, bot_id: str, run_id: str
    ):
        """H5：回傳記 judge token 用量的 callback（eval_gate + run_id 歸因），仿
        mutator 先例。原本 judge 的 usage_metadata 完全被丟棄、record_usage_factory
        注入後零使用。"""
        async def _record(model_name: str, usage_meta: dict) -> None:
            if self._record_usage_factory is None:
                return
            try:
                from src.domain.rag.value_objects import TokenUsage
                from src.infrastructure.db.session_middleware import (
                    independent_session_scope,
                )

                usage = TokenUsage(
                    model=model_name,
                    input_tokens=int(usage_meta.get("input_tokens", 0)),
                    output_tokens=int(usage_meta.get("output_tokens", 0)),
                )
                async with independent_session_scope():
                    record_usage = self._record_usage_factory()
                    await record_usage.execute(
                        tenant_id=tenant_id,
                        request_type="eval_gate",
                        usage=usage,
                        bot_id=bot_id,
                        run_id=run_id,
                    )
            except Exception:
                logger.warning(
                    "replay.judge_usage_record_failed (fail-open)",
                    exc_info=True,
                )

        return _record

    async def _execute_background(
        self,
        *,
        run_id: str,
        tenant_id: str,
        bot_id: str,
        baseline_snapshot: dict,
        candidate_snapshot: dict,
        questions: list[str],
        budget_usd: float,
        api_token: str,
        refresh_token: str = "",
        judge_api_key: str = "",
    ) -> None:
        from prompt_optimizer.api_client import AgentAPIClient, ChatResult

        run: PromptGateRun | None = None
        try:
            from src.infrastructure.db.session_middleware import (
                independent_session_scope,
            )

            async with independent_session_scope():
                repo = (
                    self._gate_run_repo_factory()
                    if self._gate_run_repo_factory
                    else self._gate_run_repo
                )
                run = await repo.find_by_id(run_id, tenant_id)
            if run is None:
                logger.error("replay.run_missing run_id=%s", run_id)
                return
            run.mark_running()
            await self._save_background(run)

            api_client = AgentAPIClient(
                base_url=self._api_base_url,
                jwt_token=api_token,
                refresh_token=refresh_token,  # H3
                usage_category="eval_gate",
                run_id=run_id,
            )
            judge = PairwiseJudge(
                api_key=judge_api_key,
                on_usage=self._make_judge_usage_recorder(
                    tenant_id=tenant_id, bot_id=bot_id, run_id=run_id
                ),
            )

            async def _shadow(question: str, snapshot: dict) -> ChatResult:
                try:
                    return await api_client.chat(
                        message=question,
                        bot_id=bot_id,
                        config_override=snapshot or None,
                        test_mode=True,
                    )
                except Exception as exc:
                    logger.warning("replay.chat_error: %s", exc)
                    return ChatResult(
                        answer="", conversation_id="",
                        tool_calls=[], sources=[],
                    )

            items: list[ReplayQuestionResult] = []
            actual_cost = 0.0
            aborted = False
            try:
                for q in questions:
                    base_cr = await _shadow(q, baseline_snapshot)
                    cand_cr = await _shadow(q, candidate_snapshot)
                    b_cost = float(
                        (base_cr.usage or {}).get("estimated_cost") or 0.0
                    )
                    c_cost = float(
                        (cand_cr.usage or {}).get("estimated_cost") or 0.0
                    )
                    actual_cost += b_cost + c_cost

                    # 換位雙判（fail-open：judge 失敗 → tie）
                    normal = swapped = ""
                    try:
                        normal = await judge.judge(
                            q, base_cr.answer, cand_cr.answer
                        )
                        swapped = await judge.judge(
                            q, cand_cr.answer, base_cr.answer
                        )
                        verdict = consistent_verdict(normal, swapped)
                    except Exception:
                        logger.warning(
                            "replay.judge_error (fail-open → tie)",
                            exc_info=True,
                        )
                        verdict = RESULT_TIE

                    b_text, _ = _truncate_keep_ends(base_cr.answer or "")
                    c_text, _ = _truncate_keep_ends(cand_cr.answer or "")
                    items.append(
                        ReplayQuestionResult(
                            question=q,
                            baseline_answer=b_text,
                            candidate_answer=c_text,
                            verdict=verdict,
                            judge_normal=normal,
                            judge_swapped=swapped,
                            baseline_cost=b_cost,
                            candidate_cost=c_cost,
                        )
                    )
                    if actual_cost > budget_usd:
                        aborted = True
                        break
            finally:
                await api_client.close()

            summary = aggregate_replay([i.verdict for i in items])
            run.actual_cost = round(actual_cost, 6)
            run.total_cases = summary.total
            run.details = {
                "type": "replay_compare",
                "aborted": aborted,
                # M22：真實流量可能來自 LINE，但影子執行走 web 管線（無 LINE
                # channel suffix、無 direct_retrieval 快速道）。對比屬近似參考，
                # 前端據此標注限制；管線統一（channel-parity 債務 #6）後移除。
                "pipeline_approximation": "web",
                "summary": {
                    "candidate_wins": summary.candidate_wins,
                    "baseline_wins": summary.baseline_wins,
                    "ties": summary.ties,
                    "win_rate": round(summary.win_rate, 4),
                },
                "items": [
                    {
                        "question": i.question,
                        "baseline_answer": i.baseline_answer,
                        "candidate_answer": i.candidate_answer,
                        "verdict": i.verdict,
                        "judge_normal": i.judge_normal,
                        "judge_swapped": i.judge_swapped,
                        "baseline_cost": round(i.baseline_cost, 6),
                        "candidate_cost": round(i.candidate_cost, 6),
                    }
                    for i in items
                ],
            }
            # 回放是「參考性對比」非閘門：candidate 勝多 → pass，僅供 UI 呈現
            run.mark_completed(
                passed=summary.candidate_wins >= summary.baseline_wins
            )
            await self._save_background(run)
        except Exception as exc:
            logger.exception("replay.background_error run_id=%s", run_id)
            try:
                if run is not None:
                    run.mark_error(str(exc))
                    await self._save_background(run)
            except Exception:
                logger.exception("replay.error_cleanup_failed")


__all__ = ["PairwiseJudge", "StartReplayCompareUseCase"]
