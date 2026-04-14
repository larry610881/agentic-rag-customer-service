"""Worker CRUD Use Cases"""

from dataclasses import dataclass, field
from typing import Any

from src.domain.bot.worker_config import WorkerConfig
from src.domain.bot.worker_repository import WorkerConfigRepository


@dataclass(frozen=True)
class CreateWorkerCommand:
    bot_id: str
    name: str
    description: str = ""
    system_prompt: str = ""
    llm_provider: str | None = None
    llm_model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 1024
    max_tool_calls: int = 5
    enabled_mcp_ids: list[str] = field(default_factory=list)
    knowledge_base_ids: list[str] = field(default_factory=list)
    sort_order: int = 0


@dataclass(frozen=True)
class UpdateWorkerCommand:
    worker_id: str
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    llm_provider: Any = ...  # sentinel — None means "clear"
    llm_model: Any = ...
    temperature: float | None = None
    max_tokens: int | None = None
    max_tool_calls: int | None = None
    enabled_mcp_ids: list[str] | None = None
    knowledge_base_ids: list[str] | None = None
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
            system_prompt=command.system_prompt,
            llm_provider=command.llm_provider,
            llm_model=command.llm_model,
            temperature=command.temperature,
            max_tokens=command.max_tokens,
            max_tool_calls=command.max_tool_calls,
            enabled_mcp_ids=list(command.enabled_mcp_ids),
            knowledge_base_ids=list(command.knowledge_base_ids),
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
        if command.system_prompt is not None:
            worker.system_prompt = command.system_prompt
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
        if command.sort_order is not None:
            worker.sort_order = command.sort_order
        await self._repo.save(worker)
        return worker


class DeleteWorkerUseCase:
    def __init__(self, repo: WorkerConfigRepository) -> None:
        self._repo = repo

    async def execute(self, worker_id: str) -> None:
        await self._repo.delete(worker_id)
