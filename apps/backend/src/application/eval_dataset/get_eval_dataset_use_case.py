from src.domain.eval_dataset.entity import EvalDataset
from src.domain.eval_dataset.repository import EvalDatasetRepository
from src.domain.shared.exceptions import EntityNotFoundError


class GetEvalDatasetUseCase:
    def __init__(self, eval_dataset_repository: EvalDatasetRepository):
        self._repo = eval_dataset_repository

    async def execute(self, dataset_id: str) -> EvalDataset:
        dataset = await self._repo.find_by_id(dataset_id)
        if dataset is None:
            raise EntityNotFoundError("EvalDataset", dataset_id)
        return dataset
