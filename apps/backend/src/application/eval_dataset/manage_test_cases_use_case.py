from dataclasses import dataclass
from typing import Any

from src.application.eval_dataset._tenant_guard import ensure_dataset_write
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
    # 歸屬檢查用（C6）
    tenant_id: str | None = None
    role: str | None = None


class CreateTestCaseUseCase:
    def __init__(self, eval_dataset_repository: EvalDatasetRepository):
        self._repo = eval_dataset_repository

    async def execute(self, command: CreateTestCaseCommand) -> EvalTestCase:
        # Verify dataset exists
        dataset = await self._repo.find_by_id(command.dataset_id)
        if dataset is None:
            raise EntityNotFoundError("EvalDataset", command.dataset_id)
        # C6：跨租戶新增 case → 404；平台集非 admin → 403
        ensure_dataset_write(dataset, command.tenant_id, command.role)

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
        self,
        dataset_id: str,
        test_case_id: str,
        *,
        enabled: bool,
        tenant_id: str | None = None,
        role: str | None = None,
    ) -> EvalTestCase:
        dataset = await self._repo.find_by_id(dataset_id)
        if dataset is None:
            raise EntityNotFoundError("EvalDataset", dataset_id)
        # C6：跨租戶停用/啟用 case（含靜默關閉平台集安全題）→ 404/403
        ensure_dataset_write(dataset, tenant_id, role)
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

    async def execute(
        self,
        test_case_id: str,
        dataset_id: str | None = None,
        tenant_id: str | None = None,
        role: str | None = None,
    ) -> None:
        # C6：原本以純 case_id 直刪、丟棄路徑上的 dataset_id，任一租戶可刪他人題目。
        # 帶入 dataset_id 時先驗歸屬且 case 屬於該 dataset。
        if dataset_id is not None:
            dataset = await self._repo.find_by_id(dataset_id)
            if dataset is None:
                raise EntityNotFoundError("EvalDataset", dataset_id)
            ensure_dataset_write(dataset, tenant_id, role)
            if not any(
                tc.id.value == test_case_id for tc in dataset.test_cases
            ):
                raise EntityNotFoundError("EvalTestCase", test_case_id)
        await self._repo.delete_test_case(test_case_id)
