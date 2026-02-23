from dependency_injector import containers, providers

from src.application.health.health_check_use_case import HealthCheckUseCase
from src.application.knowledge.create_knowledge_base_use_case import (
    CreateKnowledgeBaseUseCase,
)
from src.application.rag.query_rag_use_case import QueryRAGUseCase
from src.application.knowledge.get_processing_task_use_case import (
    GetProcessingTaskUseCase,
)
from src.application.knowledge.list_knowledge_bases_use_case import (
    ListKnowledgeBasesUseCase,
)
from src.application.knowledge.process_document_use_case import (
    ProcessDocumentUseCase,
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
from src.infrastructure.db.repositories.chunk_repository import (
    SQLAlchemyChunkRepository,
)
from src.infrastructure.db.repositories.document_repository import (
    SQLAlchemyDocumentRepository,
)
from src.infrastructure.db.repositories.knowledge_base_repository import (
    SQLAlchemyKnowledgeBaseRepository,
)
from src.infrastructure.db.repositories.processing_task_repository import (
    SQLAlchemyProcessingTaskRepository,
)
from src.infrastructure.db.repositories.tenant_repository import (
    SQLAlchemyTenantRepository,
)
from src.infrastructure.embedding.fake_embedding_service import (
    FakeEmbeddingService,
)
from src.infrastructure.embedding.openai_embedding_service import (
    OpenAIEmbeddingService,
)
from src.infrastructure.file_parser.default_file_parser_service import (
    DefaultFileParserService,
)
from src.infrastructure.llm.anthropic_llm_service import AnthropicLLMService
from src.infrastructure.llm.fake_llm_service import FakeLLMService
from src.infrastructure.llm.openai_llm_service import OpenAILLMService
from src.infrastructure.qdrant.qdrant_vector_store import QdrantVectorStore
from src.infrastructure.text_splitter.recursive_text_splitter_service import (
    RecursiveTextSplitterService,
)


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "src.interfaces.api.health_router",
            "src.interfaces.api.auth_router",
            "src.interfaces.api.tenant_router",
            "src.interfaces.api.knowledge_base_router",
            "src.interfaces.api.document_router",
            "src.interfaces.api.task_router",
            "src.interfaces.api.rag_router",
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

    chunk_repository = providers.Factory(
        SQLAlchemyChunkRepository,
        session=db_session,
    )

    processing_task_repository = providers.Factory(
        SQLAlchemyProcessingTaskRepository,
        session=db_session,
    )

    file_parser_service = providers.Singleton(DefaultFileParserService)

    text_splitter_service = providers.Singleton(
        RecursiveTextSplitterService,
        chunk_size=500,
        chunk_overlap=100,
    )

    embedding_service = providers.Selector(
        providers.Callable(
            lambda cfg: cfg.embedding_provider, config
        ),
        fake=providers.Factory(
            FakeEmbeddingService,
            vector_size=providers.Callable(
                lambda cfg: cfg.embedding_vector_size, config
            ),
        ),
        openai=providers.Factory(
            OpenAIEmbeddingService,
            api_key=providers.Callable(
                lambda cfg: cfg.openai_api_key, config
            ),
            model=providers.Callable(
                lambda cfg: cfg.embedding_model, config
            ),
        ),
    )

    vector_store = providers.Singleton(
        QdrantVectorStore,
        host=providers.Callable(
            lambda cfg: cfg.qdrant_host, config
        ),
        port=providers.Callable(
            lambda cfg: cfg.qdrant_rest_port, config
        ),
    )

    llm_service = providers.Selector(
        providers.Callable(lambda cfg: cfg.llm_provider, config),
        fake=providers.Factory(FakeLLMService),
        anthropic=providers.Factory(
            AnthropicLLMService,
            api_key=providers.Callable(
                lambda cfg: cfg.anthropic_api_key, config
            ),
            model=providers.Callable(
                lambda cfg: cfg.llm_model or "claude-sonnet-4-20250514", config
            ),
            max_tokens=providers.Callable(
                lambda cfg: cfg.llm_max_tokens, config
            ),
        ),
        openai=providers.Factory(
            OpenAILLMService,
            api_key=providers.Callable(
                lambda cfg: cfg.openai_chat_api_key, config
            ),
            model=providers.Callable(
                lambda cfg: cfg.llm_model or "gpt-4o", config
            ),
            max_tokens=providers.Callable(
                lambda cfg: cfg.llm_max_tokens, config
            ),
        ),
    )

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
        processing_task_repository=processing_task_repository,
        file_parser_service=file_parser_service,
    )

    process_document_use_case = providers.Factory(
        ProcessDocumentUseCase,
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        processing_task_repository=processing_task_repository,
        text_splitter_service=text_splitter_service,
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    get_processing_task_use_case = providers.Factory(
        GetProcessingTaskUseCase,
        processing_task_repository=processing_task_repository,
    )

    query_rag_use_case = providers.Factory(
        QueryRAGUseCase,
        knowledge_base_repository=kb_repository,
        embedding_service=embedding_service,
        vector_store=vector_store,
        llm_service=llm_service,
    )
