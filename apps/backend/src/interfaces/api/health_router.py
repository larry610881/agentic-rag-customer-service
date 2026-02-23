from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from src.application.health.health_check_use_case import HealthCheckUseCase
from src.container import Container

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
@inject
async def health_check(
    use_case: HealthCheckUseCase = Depends(Provide[Container.health_check_use_case]),
) -> dict:
    result = await use_case.execute()
    return {
        "status": result.status,
        "database": result.database,
        "version": result.version,
    }
