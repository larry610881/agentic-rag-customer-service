from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.eval_dataset.entity import EvalDataset, EvalTestCase
from src.domain.eval_dataset.repository import EvalDatasetRepository
from src.domain.eval_dataset.value_objects import EvalDatasetId, EvalTestCaseId
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.eval_dataset_model import (
    EvalDatasetModel,
    EvalTestCaseModel,
)


class SQLAlchemyEvalDatasetRepository(EvalDatasetRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    def _to_entity(self, model: EvalDatasetModel) -> EvalDataset:
        test_cases = [
            EvalTestCase(
                id=EvalTestCaseId(value=tc.id),
                dataset_id=tc.dataset_id,
                case_id=tc.case_id,
                question=tc.question,
                priority=tc.priority,
                category=tc.category or "",
                conversation_history=list(tc.conversation_history or []),
                assertions=list(tc.assertions or []),
                tags=list(tc.tags or []),
                created_at=tc.created_at,
            )
            for tc in (model.test_cases or [])
        ]
        return EvalDataset(
            id=EvalDatasetId(value=model.id),
            tenant_id=model.tenant_id,
            bot_id=model.bot_id,
            name=model.name,
            description=model.description or "",
            target_prompt=model.target_prompt,
            agent_mode=model.agent_mode,
            default_assertions=list(model.default_assertions or []),
            cost_config=dict(model.cost_config or {}),
            include_security=model.include_security,
            test_cases=test_cases,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, dataset: EvalDataset) -> None:
        async with atomic(self._session):
            model = EvalDatasetModel(
                id=dataset.id.value,
                tenant_id=dataset.tenant_id,
                bot_id=dataset.bot_id,
                name=dataset.name,
                description=dataset.description,
                target_prompt=dataset.target_prompt,
                agent_mode=dataset.agent_mode,
                default_assertions=dataset.default_assertions,
                cost_config=dataset.cost_config,
                include_security=dataset.include_security,
                created_at=dataset.created_at,
                updated_at=dataset.updated_at,
            )
            await self._session.merge(model)

    async def find_by_id(self, dataset_id: str) -> EvalDataset | None:
        stmt = (
            select(EvalDatasetModel)
            .options(selectinload(EvalDatasetModel.test_cases))
            .where(EvalDatasetModel.id == dataset_id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_all_by_tenant(
        self,
        tenant_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[EvalDataset]:
        stmt = (
            select(EvalDatasetModel)
            .options(selectinload(EvalDatasetModel.test_cases))
            .where(EvalDatasetModel.tenant_id == tenant_id)
            .order_by(EvalDatasetModel.created_at.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_all(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> list[EvalDataset]:
        stmt = (
            select(EvalDatasetModel)
            .options(selectinload(EvalDatasetModel.test_cases))
            .order_by(EvalDatasetModel.created_at.desc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_by_tenant(self, tenant_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(EvalDatasetModel)
            .where(EvalDatasetModel.tenant_id == tenant_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def count_all(self) -> int:
        stmt = select(func.count()).select_from(EvalDatasetModel)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete(self, dataset_id: str) -> None:
        async with atomic(self._session):
            stmt = delete(EvalDatasetModel).where(
                EvalDatasetModel.id == dataset_id
            )
            await self._session.execute(stmt)

    async def save_test_case(self, test_case: EvalTestCase) -> None:
        async with atomic(self._session):
            model = EvalTestCaseModel(
                id=test_case.id.value,
                dataset_id=test_case.dataset_id,
                case_id=test_case.case_id,
                question=test_case.question,
                priority=test_case.priority,
                category=test_case.category,
                conversation_history=test_case.conversation_history,
                assertions=test_case.assertions,
                tags=test_case.tags,
                created_at=test_case.created_at,
            )
            await self._session.merge(model)

    async def delete_test_case(self, test_case_id: str) -> None:
        async with atomic(self._session):
            stmt = delete(EvalTestCaseModel).where(
                EvalTestCaseModel.id == test_case_id
            )
            await self._session.execute(stmt)
