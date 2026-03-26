from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.domain.eval_dataset.entity import EvalDataset
from src.domain.eval_dataset.repository import EvalDatasetRepository
from src.domain.shared.exceptions import EntityNotFoundError


@dataclass(frozen=True)
class UpdateEvalDatasetCommand:
    dataset_id: str
    name: str | None = None
    description: str | None = None
    target_prompt: str | None = None
    default_assertions: list[dict[str, Any]] | None = None
    cost_config: dict[str, Any] | None = None
    include_security: bool | None = None


class UpdateEvalDatasetUseCase:
    def __init__(self, eval_dataset_repository: EvalDatasetRepository):
        self._repo = eval_dataset_repository

    async def execute(self, command: UpdateEvalDatasetCommand) -> EvalDataset:
        dataset = await self._repo.find_by_id(command.dataset_id)
        if dataset is None:
            raise EntityNotFoundError("EvalDataset", command.dataset_id)

        if command.name is not None:
            dataset.name = command.name
        if command.description is not None:
            dataset.description = command.description
        if command.target_prompt is not None:
            dataset.target_prompt = command.target_prompt
        if command.default_assertions is not None:
            dataset.default_assertions = command.default_assertions
        if command.cost_config is not None:
            dataset.cost_config = command.cost_config
        if command.include_security is not None:
            dataset.include_security = command.include_security
        dataset.updated_at = datetime.now(timezone.utc)

        await self._repo.save(dataset)
        return dataset
