from dataclasses import dataclass

from src.infrastructure.db.health_repository import HealthRepository


@dataclass
class HealthStatus:
    status: str
    database: str
    version: str


class HealthCheckUseCase:
    def __init__(self, health_repository: HealthRepository, version: str) -> None:
        self._health_repository = health_repository
        self._version = version

    async def execute(self) -> HealthStatus:
        db_ok = await self._health_repository.ping()
        return HealthStatus(
            status="healthy" if db_ok else "unhealthy",
            database="connected" if db_ok else "disconnected",
            version=self._version,
        )
