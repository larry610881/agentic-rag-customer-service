from dependency_injector import containers, providers

from src.application.health.health_check_use_case import HealthCheckUseCase
from src.application.knowledge.create_knowledge_base_use_case import (
    CreateKnowledgeBaseUseCase,
)
from src.application.knowledge.list_knowledge_bases_use_case import (
    ListKnowledgeBasesUseCase,
)
from src.application.knowledge.upload_document_use_case import (
    UploadDocumentUseCase,
)
from src.application.tenant.create_tenant_use_case import CreateTenantUseCase
from src.application.tenant.get_tenant_use_case import GetTenantUseCase
from src.application.tenant.list_tenants_use_case import ListTenantsUseCase
from src.config import Settings
from src.infrastructure.auth.jwt_service import JWTService
from src.infrastructure.db.engine import async_session_factory
from src.infrastructure.db.health_repository import HealthRepository
from src.infrastructure.db.repositories.document_repository import (
    SQLAlchemyDocumentRepository,
)
from src.infrastructure.db.repositories.knowledge_base_repository import (
    SQLAlchemyKnowledgeBaseRepository,
)
from src.infrastructure.db.repositories.tenant_repository import (
    SQLAlchemyTenantRepository,
)
from src.infrastructure.file_parser.default_file_parser_service import (
    DefaultFileParserService,
)


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "src.interfaces.api.health_router",
            "src.interfaces.api.auth_router",
            "src.interfaces.api.tenant_router",
            "src.interfaces.api.knowledge_base_router",
            "src.interfaces.api.document_router",
            "src.interfaces.api.deps",
        ],
    )

    config = providers.Singleton(Settings)

    # --- Infrastructure ---

    db_session = providers.Factory(async_session_factory)

    jwt_service = providers.Singleton(
        JWTService,
        secret_key=providers.Callable(lambda cfg: cfg.jwt_secret_key, config),
        algorithm=providers.Callable(lambda cfg: cfg.jwt_algorithm, config),
        access_token_expire_minutes=providers.Callable(
            lambda cfg: cfg.jwt_access_token_expire_minutes, config
        ),
    )

    health_repository = providers.Factory(
        HealthRepository,
        session=db_session,
    )

    tenant_repository = providers.Factory(
        SQLAlchemyTenantRepository,
        session=db_session,
    )

    kb_repository = providers.Factory(
        SQLAlchemyKnowledgeBaseRepository,
        session=db_session,
    )

    document_repository = providers.Factory(
        SQLAlchemyDocumentRepository,
        session=db_session,
    )

    file_parser_service = providers.Singleton(DefaultFileParserService)

    # --- Application ---

    health_check_use_case = providers.Factory(
        HealthCheckUseCase,
        health_repository=health_repository,
        version=providers.Callable(lambda cfg: cfg.app_version, config),
    )

    create_tenant_use_case = providers.Factory(
        CreateTenantUseCase,
        tenant_repository=tenant_repository,
    )

    get_tenant_use_case = providers.Factory(
        GetTenantUseCase,
        tenant_repository=tenant_repository,
    )

    list_tenants_use_case = providers.Factory(
        ListTenantsUseCase,
        tenant_repository=tenant_repository,
    )

    create_knowledge_base_use_case = providers.Factory(
        CreateKnowledgeBaseUseCase,
        knowledge_base_repository=kb_repository,
    )

    list_knowledge_bases_use_case = providers.Factory(
        ListKnowledgeBasesUseCase,
        knowledge_base_repository=kb_repository,
    )

    upload_document_use_case = providers.Factory(
        UploadDocumentUseCase,
        knowledge_base_repository=kb_repository,
        document_repository=document_repository,
        processing_task_repository=providers.Object(None),
        file_parser_service=file_parser_service,
    )
