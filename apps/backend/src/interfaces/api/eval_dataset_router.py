"""Eval dataset API endpoints for prompt optimization."""
from __future__ import annotations

import logging
from math import ceil
from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from src.application.eval_dataset.create_eval_dataset_use_case import (
    CreateEvalDatasetCommand,
    CreateEvalDatasetUseCase,
)
from src.application.eval_dataset.delete_eval_dataset_use_case import (
    DeleteEvalDatasetUseCase,
)
from src.application.eval_dataset.eval_use_cases import (
    EstimateCostCommand,
    EstimateCostUseCase,
    RunEvalCommand,
    RunSingleEvalUseCase,
    RunValidationCommand,
    RunValidationEvalUseCase,
)
from src.application.eval_dataset.get_eval_dataset_use_case import (
    GetEvalDatasetUseCase,
)
from src.application.eval_dataset.list_eval_datasets_use_case import (
    ListEvalDatasetsUseCase,
)
from src.application.eval_dataset.manage_test_cases_use_case import (
    CreateTestCaseCommand,
    CreateTestCaseUseCase,
    DeleteTestCaseUseCase,
)
from src.application.eval_dataset.update_eval_dataset_use_case import (
    UpdateEvalDatasetCommand,
    UpdateEvalDatasetUseCase,
)
from src.container import Container
from src.domain.eval_dataset.entity import EvalDataset, EvalTestCase
from src.domain.shared.exceptions import EntityNotFoundError
from src.interfaces.api.deps import CurrentTenant, get_current_tenant
from src.interfaces.api.schemas.pagination import PaginatedResponse, PaginationQuery

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/prompt-optimizer",
    tags=["prompt-optimizer"],
)


# --- Request/Response Schemas ---


class CreateDatasetRequest(BaseModel):
    name: str
    bot_id: str | None = None
    description: str = ""
    target_prompt: str = "base_prompt"
    default_assertions: list[dict[str, Any]] | None = None
    cost_config: dict[str, Any] | None = None
    include_security: bool = True


class UpdateDatasetRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    target_prompt: str | None = None
    default_assertions: list[dict[str, Any]] | None = None
    cost_config: dict[str, Any] | None = None
    include_security: bool | None = None


class TestCaseRequest(BaseModel):
    case_id: str
    question: str
    priority: str = "P1"
    category: str = ""
    conversation_history: list[dict] | None = None
    assertions: list[dict[str, Any]] | None = None
    tags: list[str] | None = None


class TestCaseResponse(BaseModel):
    id: str
    dataset_id: str
    case_id: str
    question: str
    priority: str
    category: str
    conversation_history: list[dict]
    assertions: list[dict[str, Any]]
    tags: list[str]
    created_at: str


class DatasetResponse(BaseModel):
    id: str
    tenant_id: str
    bot_id: str | None
    name: str
    description: str
    target_prompt: str
    default_assertions: list[dict[str, Any]]
    cost_config: dict[str, Any]
    include_security: bool
    test_cases: list[TestCaseResponse]
    test_case_count: int
    created_at: str
    updated_at: str


class DatasetSummaryResponse(BaseModel):
    id: str
    tenant_id: str
    bot_id: str | None
    name: str
    description: str
    target_prompt: str
    include_security: bool
    test_case_count: int
    created_at: str
    updated_at: str


# --- Converters ---


def _tc_to_response(tc: EvalTestCase) -> TestCaseResponse:
    return TestCaseResponse(
        id=tc.id.value,
        dataset_id=tc.dataset_id,
        case_id=tc.case_id,
        question=tc.question,
        priority=tc.priority,
        category=tc.category,
        conversation_history=tc.conversation_history,
        assertions=tc.assertions,
        tags=tc.tags,
        created_at=tc.created_at.isoformat(),
    )


def _to_response(ds: EvalDataset) -> DatasetResponse:
    return DatasetResponse(
        id=ds.id.value,
        tenant_id=ds.tenant_id,
        bot_id=ds.bot_id,
        name=ds.name,
        description=ds.description,
        target_prompt=ds.target_prompt,
        default_assertions=ds.default_assertions,
        cost_config=ds.cost_config,
        include_security=ds.include_security,
        test_cases=[_tc_to_response(tc) for tc in ds.test_cases],
        test_case_count=len(ds.test_cases),
        created_at=ds.created_at.isoformat(),
        updated_at=ds.updated_at.isoformat(),
    )


def _to_summary(ds: EvalDataset) -> DatasetSummaryResponse:
    return DatasetSummaryResponse(
        id=ds.id.value,
        tenant_id=ds.tenant_id,
        bot_id=ds.bot_id,
        name=ds.name,
        description=ds.description,
        target_prompt=ds.target_prompt,
        include_security=ds.include_security,
        test_case_count=len(ds.test_cases),
        created_at=ds.created_at.isoformat(),
        updated_at=ds.updated_at.isoformat(),
    )


# --- Dataset CRUD ---


@router.get("/datasets", response_model=PaginatedResponse[DatasetSummaryResponse])
@inject
async def list_datasets(
    pagination: PaginationQuery = Depends(),
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: ListEvalDatasetsUseCase = Depends(
        Provide[Container.list_eval_datasets_use_case]
    ),
) -> PaginatedResponse[DatasetSummaryResponse]:
    limit = pagination.page_size
    offset = (pagination.page - 1) * pagination.page_size

    tenant_id = None if tenant.role == "system_admin" else tenant.tenant_id
    datasets = await use_case.execute(tenant_id, limit=limit, offset=offset)
    total = await use_case.count(tenant_id)
    total_pages = ceil(total / pagination.page_size) if total > 0 else 0

    return PaginatedResponse(
        items=[_to_summary(ds) for ds in datasets],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.post(
    "/datasets",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_dataset(
    body: CreateDatasetRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: CreateEvalDatasetUseCase = Depends(
        Provide[Container.create_eval_dataset_use_case]
    ),
) -> DatasetResponse:
    tenant_id = tenant.tenant_id

    command = CreateEvalDatasetCommand(
        tenant_id=tenant_id,
        name=body.name,
        bot_id=body.bot_id,
        description=body.description,
        target_prompt=body.target_prompt,
        default_assertions=body.default_assertions,
        cost_config=body.cost_config,
        include_security=body.include_security,
    )
    dataset = await use_case.execute(command)
    return _to_response(dataset)


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
@inject
async def get_dataset(
    dataset_id: str,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: GetEvalDatasetUseCase = Depends(
        Provide[Container.get_eval_dataset_use_case]
    ),
) -> DatasetResponse:
    try:
        dataset = await use_case.execute(dataset_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e
    return _to_response(dataset)


@router.put("/datasets/{dataset_id}", response_model=DatasetResponse)
@inject
async def update_dataset(
    dataset_id: str,
    body: UpdateDatasetRequest,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: UpdateEvalDatasetUseCase = Depends(
        Provide[Container.update_eval_dataset_use_case]
    ),
) -> DatasetResponse:
    try:
        command = UpdateEvalDatasetCommand(
            dataset_id=dataset_id,
            name=body.name,
            description=body.description,
            target_prompt=body.target_prompt,
            default_assertions=body.default_assertions,
            cost_config=body.cost_config,
            include_security=body.include_security,
        )
        dataset = await use_case.execute(command)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e
    return _to_response(dataset)


@router.delete(
    "/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT
)
@inject
async def delete_dataset(
    dataset_id: str,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: DeleteEvalDatasetUseCase = Depends(
        Provide[Container.delete_eval_dataset_use_case]
    ),
) -> None:
    try:
        await use_case.execute(dataset_id)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e


# --- YAML Import / Export ---


class ImportDatasetRequest(BaseModel):
    yaml_content: str
    tenant_id: str | None = None


@router.post(
    "/datasets/import",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def import_dataset_from_yaml(
    body: ImportDatasetRequest,
    tenant: CurrentTenant = Depends(get_current_tenant),
    create_use_case: CreateEvalDatasetUseCase = Depends(
        Provide[Container.create_eval_dataset_use_case]
    ),
    create_tc_use_case: CreateTestCaseUseCase = Depends(
        Provide[Container.create_test_case_use_case]
    ),
    get_use_case: GetEvalDatasetUseCase = Depends(
        Provide[Container.get_eval_dataset_use_case]
    ),
) -> DatasetResponse:
    """Import a YAML dataset string into DB."""
    from prompt_optimizer.dataset import DatasetLoader

    loader = DatasetLoader()
    try:
        ds = loader.load_from_string(body.yaml_content)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {e}") from e

    tenant_id = body.tenant_id or tenant.tenant_id

    # Create dataset
    dataset = await create_use_case.execute(
        CreateEvalDatasetCommand(
            tenant_id=tenant_id,
            name=ds.metadata.description or "Imported Dataset",
            bot_id=ds.metadata.bot_id or None,
            description=ds.metadata.description,
            target_prompt=ds.metadata.target_prompt,
            default_assertions=[
                {"type": a.type, "params": a.params} for a in ds.default_assertions
            ],
            cost_config={
                "token_budget": ds.metadata.cost_config.token_budget,
                "quality_weight": ds.metadata.cost_config.quality_weight,
                "cost_weight": ds.metadata.cost_config.cost_weight,
            },
        )
    )

    # Create test cases (excluding defaults which are already in default_assertions)
    default_set = {(a.type, str(a.params)) for a in ds.default_assertions}
    for tc in ds.test_cases:
        case_assertions = [
            {"type": a.type, "params": a.params}
            for a in tc.assertions
            if (a.type, str(a.params)) not in default_set
        ]
        await create_tc_use_case.execute(
            CreateTestCaseCommand(
                dataset_id=dataset.id.value,
                case_id=tc.id,
                question=tc.question,
                priority=tc.priority,
                category=tc.category,
                conversation_history=list(tc.conversation_history)
                if tc.conversation_history
                else None,
                assertions=case_assertions,
            )
        )

    # Re-fetch to get full dataset with cases
    result = await get_use_case.execute(dataset.id.value)
    return _to_response(result)


@router.get("/datasets/{dataset_id}/export")
@inject
async def export_dataset(
    dataset_id: str,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: GetEvalDatasetUseCase = Depends(
        Provide[Container.get_eval_dataset_use_case]
    ),
) -> dict:
    """Export a dataset as YAML string."""
    from prompt_optimizer.dataset import (
        Assertion,
        CostConfigData,
        Dataset,
        DatasetMetadata,
        TestCase,
        dataset_to_yaml,
    )

    try:
        ds_entity = await use_case.execute(dataset_id)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e

    # Convert DB entity to prompt_optimizer Dataset
    default_assertions = tuple(
        Assertion(type=a["type"], params=a.get("params", {}))
        for a in ds_entity.default_assertions
    )
    cost_raw = ds_entity.cost_config or {}
    dataset = Dataset(
        metadata=DatasetMetadata(
            tenant_id=ds_entity.tenant_id,
            bot_id=ds_entity.bot_id or "",
            target_prompt=ds_entity.target_prompt,
            agent_mode="react",
            description=ds_entity.description,
            cost_config=CostConfigData(
                token_budget=cost_raw.get("token_budget", 2000),
                quality_weight=cost_raw.get("quality_weight", 0.85),
                cost_weight=cost_raw.get("cost_weight", 0.15),
            ),
        ),
        default_assertions=default_assertions,
        test_cases=tuple(
            TestCase(
                id=tc.case_id,
                question=tc.question,
                priority=tc.priority,
                category=tc.category,
                assertions=tuple(
                    Assertion(type=a["type"], params=a.get("params", {}))
                    for a in tc.assertions
                ),
                conversation_history=tuple(tc.conversation_history)
                if tc.conversation_history
                else (),
            )
            for tc in ds_entity.test_cases
        ),
    )

    yaml_str = dataset_to_yaml(dataset)
    return {"yaml": yaml_str, "dataset_id": dataset_id, "name": ds_entity.name}


# --- Test Case CRUD ---


@router.post(
    "/datasets/{dataset_id}/cases",
    response_model=TestCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_test_case(
    dataset_id: str,
    body: TestCaseRequest,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: CreateTestCaseUseCase = Depends(
        Provide[Container.create_test_case_use_case]
    ),
) -> TestCaseResponse:
    try:
        command = CreateTestCaseCommand(
            dataset_id=dataset_id,
            case_id=body.case_id,
            question=body.question,
            priority=body.priority,
            category=body.category,
            conversation_history=body.conversation_history,
            assertions=body.assertions,
            tags=body.tags,
        )
        test_case = await use_case.execute(command)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e
    return _tc_to_response(test_case)


@router.delete(
    "/datasets/{dataset_id}/cases/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@inject
async def delete_test_case(
    dataset_id: str,
    case_id: str,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: DeleteTestCaseUseCase = Depends(
        Provide[Container.delete_test_case_use_case]
    ),
) -> None:
    await use_case.execute(case_id)


# --- Single Eval & Cost Estimate ---


class RunEvalRequest(BaseModel):
    dataset_id: str


class EstimateCostRequest(BaseModel):
    dataset_id: str
    bot_id: str = ""
    model_id: str = ""
    mutator_model_id: str = ""
    max_iterations: int = 20
    patience: int = 5
    budget: int = 200


@router.post("/eval")
@inject
async def run_single_eval(
    body: RunEvalRequest,
    request: Request,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: RunSingleEvalUseCase = Depends(
        Provide[Container.run_single_eval_use_case]
    ),
) -> dict:
    """Run one eval cycle against current prompt (no optimization loop)."""
    auth_header = request.headers.get("authorization", "")
    api_token = auth_header.removeprefix("Bearer ").strip()
    command = RunEvalCommand(
        tenant_id=tenant.tenant_id,
        dataset_id=body.dataset_id,
        api_token=api_token,
    )
    try:
        return await use_case.execute(command)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e


@router.post("/estimate")
@inject
async def estimate_cost(
    body: EstimateCostRequest,
    _: CurrentTenant = Depends(get_current_tenant),
    use_case: EstimateCostUseCase = Depends(
        Provide[Container.estimate_cost_use_case]
    ),
) -> dict:
    """Estimate optimization cost based on dataset size + settings."""
    command = EstimateCostCommand(
        dataset_id=body.dataset_id,
        bot_id=body.bot_id,
        model_id=body.model_id,
        mutator_model_id=body.mutator_model_id,
        max_iterations=body.max_iterations,
        patience=body.patience,
        budget=body.budget,
    )
    try:
        return await use_case.execute(command)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e


class RunValidationRequest(BaseModel):
    dataset_id: str
    bot_id: str = ""
    repeats: int = 5


@router.post("/validate")
@inject
async def run_validation_eval(
    body: RunValidationRequest,
    request: Request,
    tenant: CurrentTenant = Depends(get_current_tenant),
    use_case: RunValidationEvalUseCase = Depends(
        Provide[Container.run_validation_eval_use_case]
    ),
) -> dict:
    """Run N evaluation repeats and return PASS/FAIL verdict with per-case pass rates."""
    if body.repeats < 1 or body.repeats > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="repeats must be between 1 and 100",
        )
    auth_header = request.headers.get("authorization", "")
    api_token = auth_header.removeprefix("Bearer ").strip()
    command = RunValidationCommand(
        tenant_id=tenant.tenant_id,
        dataset_id=body.dataset_id,
        api_token=api_token,
        repeats=body.repeats,
        bot_id=body.bot_id,
    )
    try:
        return await use_case.execute(command)
    except EntityNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=e.message
        ) from e


# ── Exchange Rate (for TWD display) ──────────────────────

EXCHANGE_RATE_URL = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
EXCHANGE_RATE_CACHE_KEY = "exchange_rate:usd"
EXCHANGE_RATE_TTL = 3600  # 1 hour


@router.get("/exchange-rate")
@inject
async def get_exchange_rate(
    target: str = "twd",
    _: CurrentTenant = Depends(get_current_tenant),
    redis_client=Depends(Provide[Container.redis_client]),
) -> dict:
    """Get USD → target currency exchange rate with Redis cache."""
    import json as _json
    from datetime import datetime, timezone

    import httpx as _httpx

    target = target.lower()
    cache_key = f"{EXCHANGE_RATE_CACHE_KEY}:{target}"

    # Try Redis cache first
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return _json.loads(cached)
    except Exception:
        pass  # Redis down → fallback to API

    # Fetch from API
    try:
        async with _httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(EXCHANGE_RATE_URL)
            resp.raise_for_status()
            data = resp.json()

        rate = data.get("usd", {}).get(target)
        if rate is None:
            raise HTTPException(status_code=400, detail=f"Unknown currency: {target}")

        result = {
            "from": "USD",
            "to": target.upper(),
            "rate": round(float(rate), 4),
            "source_date": data.get("date", ""),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

        # Cache in Redis
        try:
            await redis_client.set(cache_key, _json.dumps(result), ex=EXCHANGE_RATE_TTL)
        except Exception:
            pass

        return result

    except _httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Exchange rate API error: {e}") from e
