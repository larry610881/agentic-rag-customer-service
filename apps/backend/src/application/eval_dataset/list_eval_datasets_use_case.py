from src.domain.eval_dataset.entity import EvalDataset
from src.domain.eval_dataset.repository import EvalDatasetRepository


class ListEvalDatasetsUseCase:
    def __init__(self, eval_dataset_repository: EvalDatasetRepository):
        self._repo = eval_dataset_repository

    async def execute(
        self,
        tenant_id: str | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[EvalDataset]:
        if tenant_id:
            return await self._repo.find_all_by_tenant(
                tenant_id, limit=limit, offset=offset
            )
        return await self._repo.find_all(limit=limit, offset=offset)

    async def count(self, tenant_id: str | None = None) -> int:
        if tenant_id:
            return await self._repo.count_by_tenant(tenant_id)
        return await self._repo.count_all()
