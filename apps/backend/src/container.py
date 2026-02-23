from dependency_injector import containers, providers

from src.application.health.health_check_use_case import HealthCheckUseCase
from src.config import Settings
from src.infrastructure.db.engine import async_session_factory
from src.infrastructure.db.health_repository import HealthRepository


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=["src.interfaces.api.health_router"],
    )

    config = providers.Singleton(Settings)

    db_session = providers.Factory(async_session_factory)

    health_repository = providers.Factory(
        HealthRepository,
        session=db_session,
    )

    health_check_use_case = providers.Factory(
        HealthCheckUseCase,
        health_repository=health_repository,
        version=providers.Callable(lambda cfg: cfg.app_version, config),
    )
