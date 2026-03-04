from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

_is_cloud = bool(settings.database_url_override)

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5 if _is_cloud else 20,
    max_overflow=10 if _is_cloud else 30,
    pool_pre_ping=True,
    pool_recycle=300,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
