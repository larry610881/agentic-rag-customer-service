from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.security.guard_config import GuardLogRepository
from src.infrastructure.db.atomic import atomic
from src.infrastructure.db.models.guard_log_model import GuardLogModel


class SQLAlchemyGuardLogRepository(GuardLogRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_log(
        self,
        tenant_id: str,
        bot_id: str | None,
        user_id: str | None,
        log_type: str,
        rule_matched: str,
        user_message: str,
        ai_response: str | None,
    ) -> None:
        async with atomic(self._session):
            model = GuardLogModel(
                id=str(uuid4()),
                tenant_id=tenant_id,
                bot_id=bot_id,
                user_id=user_id,
                log_type=log_type,
                rule_matched=rule_matched,
                user_message=user_message,
                ai_response=ai_response,
            )
            self._session.add(model)

    async def find_logs(
        self,
        *,
        tenant_id: str | None = None,
        log_type: str | None = None,
        bot_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        stmt = select(GuardLogModel).order_by(GuardLogModel.created_at.desc())
        if tenant_id:
            stmt = stmt.where(GuardLogModel.tenant_id == tenant_id)
        if log_type:
            stmt = stmt.where(GuardLogModel.log_type == log_type)
        if bot_id:
            stmt = stmt.where(GuardLogModel.bot_id == bot_id)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [
            {
                "id": m.id,
                "tenant_id": m.tenant_id,
                "bot_id": m.bot_id,
                "user_id": m.user_id,
                "log_type": m.log_type,
                "rule_matched": m.rule_matched,
                "user_message": m.user_message,
                "ai_response": m.ai_response,
                "created_at": m.created_at.isoformat(),
            }
            for m in result.scalars().all()
        ]

    async def count_logs(
        self,
        *,
        tenant_id: str | None = None,
        log_type: str | None = None,
        bot_id: str | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(GuardLogModel)
        if tenant_id:
            stmt = stmt.where(GuardLogModel.tenant_id == tenant_id)
        if log_type:
            stmt = stmt.where(GuardLogModel.log_type == log_type)
        if bot_id:
            stmt = stmt.where(GuardLogModel.bot_id == bot_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()
