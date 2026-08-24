from src.application.eval_dataset._tenant_guard import ensure_dataset_write
from src.domain.eval_dataset.repository import EvalDatasetRepository
from src.domain.shared.exceptions import EntityNotFoundError


class DeleteEvalDatasetUseCase:
    def __init__(self, eval_dataset_repository: EvalDatasetRepository):
        self._repo = eval_dataset_repository

    async def execute(
        self,
        dataset_id: str,
        tenant_id: str | None = None,
        role: str | None = None,
    ) -> None:
        dataset = await self._repo.find_by_id(dataset_id)
        if dataset is None:
            raise EntityNotFoundError("EvalDataset", dataset_id)
        ensure_dataset_write(dataset, tenant_id, role)  # C5：跨租戶/平台集 → 404/403
        await self._repo.delete(dataset_id)
