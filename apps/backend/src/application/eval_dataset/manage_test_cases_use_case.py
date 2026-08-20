from dataclasses import dataclass
from typing import Any

from src.domain.eval_dataset.entity import EvalTestCase
from src.domain.eval_dataset.repository import EvalDatasetRepository
from src.domain.eval_dataset.value_objects import EvalTestCaseId
from src.domain.shared.exceptions import EntityNotFoundError


@dataclass(frozen=True)
class CreateTestCaseCommand:
    dataset_id: str
    case_id: str
    question: str
    priority: str = "P1"
    category: str = ""
    conversation_history: list[dict] | None = None
    assertions: list[dict[str, Any]] | None = None
    tags: list[str] | None = None


class CreateTestCaseUseCase:
    def __init__(self, eval_dataset_repository: EvalDatasetRepository):
        self._repo = eval_dataset_repository

    async def execute(self, command: CreateTestCaseCommand) -> EvalTestCase:
        # Verify dataset exists
        dataset = await self._repo.find_by_id(command.dataset_id)
        if dataset is None:
            raise EntityNotFoundError("EvalDataset", command.dataset_id)

        test_case = EvalTestCase(
            id=EvalTestCaseId(),
            dataset_id=command.dataset_id,
            case_id=command.case_id,
            question=command.question,
            priority=command.priority,
            category=command.category,
            conversation_history=command.conversation_history or [],
            assertions=command.assertions or [],
            tags=command.tags or [],
        )
        await self._repo.save_test_case(test_case)
        return test_case


class UpdateTestCaseUseCase:
    """Issue #54 Phase C — v1 只開 enabled toggle（停用的 case 不參與閘門）。"""

    def __init__(self, eval_dataset_repository: EvalDatasetRepository):
        self._repo = eval_dataset_repository

    async def execute(
        self, dataset_id: str, test_case_id: str, *, enabled: bool
    ) -> EvalTestCase:
        dataset = await self._repo.find_by_id(dataset_id)
        if dataset is None:
            raise EntityNotFoundError("EvalDataset", dataset_id)
        test_case = next(
            (tc for tc in dataset.test_cases if tc.id.value == test_case_id),
            None,
        )
        if test_case is None:
            raise EntityNotFoundError("EvalTestCase", test_case_id)
        test_case.enabled = enabled
        await self._repo.save_test_case(test_case)
        return test_case


class DeleteTestCaseUseCase:
    def __init__(self, eval_dataset_repository: EvalDatasetRepository):
        self._repo = eval_dataset_repository

    async def execute(self, test_case_id: str) -> None:
        await self._repo.delete_test_case(test_case_id)
