"""Optimization run repository interface."""

from abc import ABC, abstractmethod

from src.domain.eval_dataset.run_entity import OptimizationIteration


class OptimizationRunRepository(ABC):
    @abstractmethod
    async def save_iteration(self, iteration: OptimizationIteration) -> None: ...

    @abstractmethod
    async def get_iterations(self, run_id: str) -> list[OptimizationIteration]: ...

    @abstractmethod
    async def get_best_iteration(
        self, run_id: str
    ) -> OptimizationIteration | None: ...

    @abstractmethod
    async def list_runs(
        self,
        tenant_id: str | None = None,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]: ...

    @abstractmethod
    async def count_runs(self, tenant_id: str | None = None) -> int: ...
