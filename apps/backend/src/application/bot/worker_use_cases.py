"""Worker CRUD Use Cases"""

from dataclasses import dataclass, field
from typing import Any

from src.domain.bot.entity import ToolRagConfig
from src.domain.bot.worker_config import WorkerConfig
from src.domain.bot.worker_repository import WorkerConfigRepository


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


@dataclass(frozen=True)
class UpdateWorkerCommand:
    worker_id: str
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


class ListWorkersUseCase:
    def __init__(self, repo: WorkerConfigRepository) -> None:
        self._repo = repo

    async def execute(self, bot_id: str) -> list[WorkerConfig]:
        return await self._repo.find_by_bot_id(bot_id)


class CreateWorkerUseCase:
    def __init__(self, repo: WorkerConfigRepository) -> None:
        self._repo = repo

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
        )
        await self._repo.save(worker)
        return worker


class UpdateWorkerUseCase:
    def __init__(self, repo: WorkerConfigRepository) -> None:
        self._repo = repo

    async def execute(
        self, command: UpdateWorkerCommand
    ) -> WorkerConfig | None:
        worker = await self._repo.find_by_id(command.worker_id)
        if worker is None:
            return None
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
        await self._repo.save(worker)
        return worker


class DeleteWorkerUseCase:
    def __init__(self, repo: WorkerConfigRepository) -> None:
        self._repo = repo

    async def execute(self, worker_id: str) -> None:
        await self._repo.delete(worker_id)
