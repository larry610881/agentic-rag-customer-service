from dataclasses import dataclass
from typing import Any

from src.domain.eval_dataset.entity import EvalDataset
from src.domain.eval_dataset.repository import EvalDatasetRepository
from src.domain.eval_dataset.value_objects import EvalDatasetId


@dataclass(frozen=True)
class CreateEvalDatasetCommand:
    tenant_id: str
    name: str
    bot_id: str | None = None
    description: str = ""
    target_prompt: str = "base_prompt"
    default_assertions: list[dict[str, Any]] | None = None
    cost_config: dict[str, Any] | None = None
    include_security: bool = True


class CreateEvalDatasetUseCase:
    def __init__(self, eval_dataset_repository: EvalDatasetRepository):
        self._repo = eval_dataset_repository

    async def execute(self, command: CreateEvalDatasetCommand) -> EvalDataset:
        dataset = EvalDataset(
            id=EvalDatasetId(),
            tenant_id=command.tenant_id,
            bot_id=command.bot_id,
            name=command.name,
            description=command.description,
            target_prompt=command.target_prompt,
            default_assertions=command.default_assertions or [],
            cost_config=command.cost_config or {},
            include_security=command.include_security,
        )
        await self._repo.save(dataset)
        return dataset
