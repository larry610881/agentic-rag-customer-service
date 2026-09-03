"""Worker CRUD Use Cases"""

from dataclasses import dataclass, field
from typing import Any

from src.domain.bot.entity import ToolRagConfig
from src.domain.bot.worker_config import WorkerConfig
from src.domain.bot.worker_repository import WorkerConfigRepository
from src.domain.shared.exceptions import EntityNotFoundError


def _build_tool_configs(
    raw: dict | None,
) -> dict[str, ToolRagConfig]:
    """將 API 傳入的 dict 轉為 {tool_name: ToolRagConfig}，供 entity 使用。"""
    if not raw:
        return {}
    return {
        name: ToolRagConfig(
            rag_top_k=cfg.get("rag_top_k"),
            rag_score_threshold=cfg.get("rag_score_threshold"),
            rerank_enabled=cfg.get("rerank_enabled"),
            rerank_model=cfg.get("rerank_model"),
            rerank_top_n=cfg.get("rerank_top_n"),
            kb_ids=cfg.get("kb_ids"),
        )
        for name, cfg in raw.items()
        if isinstance(cfg, dict)
    }


@dataclass(frozen=True)
class CreateWorkerCommand:
    bot_id: str
    name: str
    description: str = ""
    worker_prompt: str = ""
    llm_provider: str | None = None
    llm_model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 1024
    max_tool_calls: int = 5
    enabled_mcp_ids: list[str] = field(default_factory=list)
    knowledge_base_ids: list[str] = field(default_factory=list)
    # None = 繼承 Bot.enabled_tools；list 為顯式覆蓋
    enabled_tools: list[str] | None = None
    tool_configs: dict = field(default_factory=dict)
    sort_order: int = 0
    direct_retrieval: bool = False  # Issue #66：快速道開關進 API
    actor_user_id: str | None = None  # Issue #60：稽核 actor


@dataclass(frozen=True)
class UpdateWorkerCommand:
    worker_id: str
    # Issue #67：路徑上的 bot_id；給定時 worker 必須屬於該 bot
    #（跨 bot / 跨租戶一律視為找不到）
    bot_id: str | None = None
    name: str | None = None
    description: str | None = None
    worker_prompt: str | None = None
    llm_provider: Any = ...  # sentinel — None means "clear"
    llm_model: Any = ...
    temperature: float | None = None
    max_tokens: int | None = None
    max_tool_calls: int | None = None
    enabled_mcp_ids: list[str] | None = None
    knowledge_base_ids: list[str] | None = None
    # sentinel: ... = 不更新；None = 清空/繼承；list = 顯式設定
    enabled_tools: Any = ...
    tool_configs: dict | None = None
    sort_order: int | None = None
    direct_retrieval: bool | None = None  # Issue #66：快速道開關進 API
    actor_user_id: str | None = None  # Issue #60：稽核 actor


class ListWorkersUseCase:
    def __init__(self, repo: WorkerConfigRepository) -> None:
        self._repo = repo

    async def execute(self, bot_id: str) -> list[WorkerConfig]:
        return await self._repo.find_by_bot_id(bot_id)


def _worker_view(w: WorkerConfig | None) -> dict | None:
    """Issue #60：稽核用可比較視圖（含 worker_prompt——最常被改壞的欄位）。"""
    if w is None:
        return None
    return {
        "bot_id": w.bot_id,
        "name": w.name,
        "description": w.description,
        "worker_prompt": w.worker_prompt,
        "llm_provider": w.llm_provider,
        "llm_model": w.llm_model,
        "temperature": w.temperature,
        "max_tokens": w.max_tokens,
        "max_tool_calls": w.max_tool_calls,
        "enabled_mcp_ids": list(w.enabled_mcp_ids or []),
        "knowledge_base_ids": list(w.knowledge_base_ids or []),
        "enabled_tools": list(w.enabled_tools) if w.enabled_tools is not None else None,
        "tool_configs": str(w.tool_configs),
        "sort_order": w.sort_order,
        "direct_retrieval": getattr(w, "direct_retrieval", False),
    }


class CreateWorkerUseCase:
    def __init__(self, repo: WorkerConfigRepository, audit: Any | None = None) -> None:
        self._repo = repo
        self._audit = audit

    async def execute(
        self, command: CreateWorkerCommand
    ) -> WorkerConfig:
        worker = WorkerConfig(
            bot_id=command.bot_id,
            name=command.name,
            description=command.description,
            worker_prompt=command.worker_prompt,
            llm_provider=command.llm_provider,
            llm_model=command.llm_model,
            temperature=command.temperature,
            max_tokens=command.max_tokens,
            max_tool_calls=command.max_tool_calls,
            enabled_mcp_ids=list(command.enabled_mcp_ids),
            knowledge_base_ids=list(command.knowledge_base_ids),
            enabled_tools=(
                list(command.enabled_tools)
                if command.enabled_tools is not None else None
            ),
            tool_configs=_build_tool_configs(command.tool_configs),
            sort_order=command.sort_order,
            direct_retrieval=command.direct_retrieval,
        )
        await self._repo.save(worker)
        if self._audit is not None:
            await self._audit.record(
                entity_type="worker", entity_id=worker.id, action="create",
                before=None, after=_worker_view(worker),
                actor_user_id=command.actor_user_id,
            )
        return worker


class UpdateWorkerUseCase:
    def __init__(self, repo: WorkerConfigRepository, audit: Any | None = None) -> None:
        self._repo = repo
        self._audit = audit

    async def execute(
        self, command: UpdateWorkerCommand
    ) -> WorkerConfig | None:
        worker = await self._repo.find_by_id(command.worker_id)
        if worker is None:
            return None
        if command.bot_id is not None and worker.bot_id != command.bot_id:
            return None
        before = _worker_view(worker) if self._audit is not None else None
        if command.name is not None:
            worker.name = command.name
        if command.description is not None:
            worker.description = command.description
        if command.worker_prompt is not None:
            worker.worker_prompt = command.worker_prompt
        if command.llm_provider is not ...:
            worker.llm_provider = command.llm_provider
        if command.llm_model is not ...:
            worker.llm_model = command.llm_model
        if command.temperature is not None:
            worker.temperature = command.temperature
        if command.max_tokens is not None:
            worker.max_tokens = command.max_tokens
        if command.max_tool_calls is not None:
            worker.max_tool_calls = command.max_tool_calls
        if command.enabled_mcp_ids is not None:
            worker.enabled_mcp_ids = list(command.enabled_mcp_ids)
        if command.knowledge_base_ids is not None:
            worker.knowledge_base_ids = list(command.knowledge_base_ids)
        if command.enabled_tools is not ...:
            worker.enabled_tools = (
                list(command.enabled_tools)
                if command.enabled_tools is not None else None
            )
        if command.tool_configs is not None:
            worker.tool_configs = _build_tool_configs(command.tool_configs)
        if command.sort_order is not None:
            worker.sort_order = command.sort_order
        if command.direct_retrieval is not None:
            worker.direct_retrieval = command.direct_retrieval
        await self._repo.save(worker)
        if self._audit is not None:
            await self._audit.record(
                entity_type="worker", entity_id=worker.id, action="update",
                before=before, after=_worker_view(worker),
                actor_user_id=command.actor_user_id,
            )
        return worker


class DeleteWorkerUseCase:
    def __init__(self, repo: WorkerConfigRepository, audit: Any | None = None) -> None:
        self._repo = repo
        self._audit = audit

    async def execute(
        self,
        worker_id: str,
        actor_user_id: str | None = None,
        bot_id: str | None = None,
    ) -> None:
        before = None
        if bot_id is not None:
            # Issue #67：只允許刪除路徑 bot 底下的 worker
            worker = await self._repo.find_by_id(worker_id)
            if worker is None or worker.bot_id != bot_id:
                raise EntityNotFoundError("Worker", worker_id)
            if self._audit is not None:
                before = _worker_view(worker)
        elif self._audit is not None:
            before = _worker_view(await self._repo.find_by_id(worker_id))
        await self._repo.delete(worker_id)
        if self._audit is not None:
            await self._audit.record(
                entity_type="worker", entity_id=worker_id, action="delete",
                before=before, after=None, actor_user_id=actor_user_id,
            )
