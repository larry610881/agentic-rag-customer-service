from abc import ABC, abstractmethod

from src.domain.eval_dataset.entity import EvalDataset, EvalTestCase


class EvalDatasetRepository(ABC):
    @abstractmethod
    async def save(self, dataset: EvalDataset) -> None: ...

    @abstractmethod
    async def find_by_id(self, dataset_id: str) -> EvalDataset | None: ...

    @abstractmethod
    async def find_all_by_tenant(
        self,
        tenant_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[EvalDataset]: ...

    @abstractmethod
    async def find_all(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> list[EvalDataset]: ...

    @abstractmethod
    async def count_by_tenant(self, tenant_id: str) -> int: ...

    @abstractmethod
    async def count_all(self) -> int: ...

    @abstractmethod
    async def delete(self, dataset_id: str) -> None: ...

    @abstractmethod
    async def save_test_case(self, test_case: EvalTestCase) -> None: ...

    @abstractmethod
    async def delete_test_case(self, test_case_id: str) -> None: ...
