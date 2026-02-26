from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.auth.entity import User
from src.domain.auth.repository import UserRepository
from src.domain.auth.value_objects import Email, Role, UserId
from src.infrastructure.db.models.user_model import UserModel


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_entity(self, model: UserModel) -> User:
        return User(
            id=UserId(value=model.id),
            tenant_id=model.tenant_id,
            email=Email(model.email),
            hashed_password=model.hashed_password,
            role=Role(model.role),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def save(self, user: User) -> None:
        existing = await self._session.get(UserModel, user.id.value)
        if existing:
            existing.tenant_id = user.tenant_id
            existing.email = user.email.value
            existing.hashed_password = user.hashed_password
            existing.role = user.role.value
            existing.updated_at = datetime.now(timezone.utc)
        else:
            model = UserModel(
                id=user.id.value,
                tenant_id=user.tenant_id,
                email=user.email.value,
                hashed_password=user.hashed_password,
                role=user.role.value,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            self._session.add(model)
        await self._session.commit()

    async def find_by_id(self, user_id: str) -> User | None:
        model = await self._session.get(UserModel, user_id)
        if model is None:
            return None
        return self._to_entity(model)

    async def find_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def find_all_by_tenant(self, tenant_id: str) -> list[User]:
        stmt = (
            select(UserModel)
            .where(UserModel.tenant_id == tenant_id)
            .order_by(UserModel.created_at)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]
