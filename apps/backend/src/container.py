import redis.asyncio as aioredis
from dependency_injector import containers, providers

from src.application.agent.send_message_use_case import SendMessageUseCase
from src.application.auth.get_user_use_case import GetUserUseCase
from src.application.auth.login_use_case import LoginUseCase
from src.application.auth.register_user_use_case import RegisterUserUseCase
from src.application.bot.create_bot_use_case import CreateBotUseCase
from src.application.bot.delete_bot_use_case import DeleteBotUseCase
from src.application.bot.get_bot_use_case import GetBotUseCase
from src.application.bot.list_bots_use_case import ListBotsUseCase
from src.application.bot.update_bot_use_case import UpdateBotUseCase
from src.application.conversation.get_conversation_use_case import (
    GetConversationUseCase,
)
from src.application.conversation.get_feedback_stats_use_case import (
    GetFeedbackStatsUseCase,
)
from src.application.conversation.get_retrieval_quality_use_case import (
    GetRetrievalQualityUseCase,
)
from src.application.conversation.get_satisfaction_trend_use_case import (
    GetSatisfactionTrendUseCase,
)
from src.application.conversation.get_token_cost_stats_use_case import (
    GetTokenCostStatsUseCase,
)
from src.application.conversation.get_top_issues_use_case import (
    GetTopIssuesUseCase,
)
from src.application.conversation.list_conversations_use_case import (
    ListConversationsUseCase,
)
from src.application.conversation.list_feedback_use_case import (
    ListFeedbackUseCase,
)
from src.application.conversation.submit_feedback_use_case import (
    SubmitFeedbackUseCase,
)
from src.application.health.health_check_use_case import HealthCheckUseCase
from src.application.knowledge.create_knowledge_base_use_case import (
    CreateKnowledgeBaseUseCase,
)
from src.application.knowledge.delete_document_use_case import (
    DeleteDocumentUseCase,
)
from src.application.knowledge.get_document_chunks_use_case import (
    GetDocumentChunksUseCase,
)
from src.application.knowledge.get_document_quality_stats_use_case import (
    GetDocumentQualityStatsUseCase,
)
from src.application.knowledge.get_processing_task_use_case import (
    GetProcessingTaskUseCase,
)
from src.application.knowledge.list_documents_use_case import (
    ListDocumentsUseCase,
)
from src.application.knowledge.list_knowledge_bases_use_case import (
    ListKnowledgeBasesUseCase,
)
from src.application.knowledge.process_document_use_case import (
    ProcessDocumentUseCase,
)
from src.application.knowledge.reprocess_document_use_case import (
    ReprocessDocumentUseCase,
)
from src.application.knowledge.upload_document_use_case import (
    UploadDocumentUseCase,
)
from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.application.platform.create_provider_setting_use_case import (
    CreateProviderSettingUseCase,
)
from src.application.platform.delete_provider_setting_use_case import (
    DeleteProviderSettingUseCase,
)
from src.application.platform.get_provider_setting_use_case import (
    GetProviderSettingUseCase,
)
from src.application.platform.list_provider_settings_use_case import (
    ListProviderSettingsUseCase,
)
from src.application.platform.test_provider_connection_use_case import (
    CheckProviderConnectionUseCase,
)
from src.application.platform.update_provider_setting_use_case import (
    UpdateProviderSettingUseCase,
)
from src.application.rag.query_rag_use_case import QueryRAGUseCase
from src.application.ratelimit.get_rate_limits_use_case import GetRateLimitsUseCase
from src.application.ratelimit.seed_defaults_use_case import SeedDefaultsUseCase
from src.application.ratelimit.update_rate_limit_use_case import (
    UpdateRateLimitUseCase,
)
from src.application.tenant.create_tenant_use_case import CreateTenantUseCase
from src.application.tenant.get_tenant_use_case import GetTenantUseCase
from src.application.tenant.list_tenants_use_case import ListTenantsUseCase
from src.application.usage.query_usage_use_case import QueryUsageUseCase
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.config import Settings
from src.domain.agent.team_supervisor import TeamSupervisor
from src.infrastructure.auth.bcrypt_password_service import BcryptPasswordService
from src.infrastructure.auth.jwt_service import JWTService
from src.infrastructure.cache.redis_cache_service import RedisCacheService
from src.infrastructure.conversation import (
    FullHistoryStrategy,
    RAGHistoryStrategy,
    SlidingWindowStrategy,
    SummaryRecentStrategy,
)
from src.infrastructure.crypto.aes_encryption_service import AESEncryptionService
from src.infrastructure.db.engine import async_session_factory
from src.infrastructure.db.health_repository import HealthRepository
from src.infrastructure.db.repositories.bot_repository import (
    SQLAlchemyBotRepository,
)
from src.infrastructure.db.repositories.chunk_repository import (
    SQLAlchemyChunkRepository,
)
from src.infrastructure.db.repositories.conversation_repository import (
    SQLAlchemyConversationRepository,
)
from src.infrastructure.db.repositories.document_repository import (
    SQLAlchemyDocumentRepository,
)
from src.infrastructure.db.repositories.feedback_repository import (
    SQLAlchemyFeedbackRepository,
)
from src.infrastructure.db.repositories.knowledge_base_repository import (
    SQLAlchemyKnowledgeBaseRepository,
)
from src.infrastructure.db.repositories.processing_task_repository import (
    SQLAlchemyProcessingTaskRepository,
)
from src.infrastructure.db.repositories.provider_setting_repository import (
    SQLAlchemyProviderSettingRepository,
)
from src.infrastructure.db.repositories.rate_limit_config_repository import (
    SQLAlchemyRateLimitConfigRepository,
)
from src.infrastructure.db.repositories.tenant_repository import (
    SQLAlchemyTenantRepository,
)
from src.infrastructure.db.repositories.usage_repository import (
    SQLAlchemyUsageRepository,
)
from src.infrastructure.db.repositories.user_repository import (
    SQLAlchemyUserRepository,
)
from src.infrastructure.embedding.dynamic_embedding_factory import (
    DynamicEmbeddingServiceFactory,
    DynamicEmbeddingServiceProxy,
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
from src.infrastructure.langgraph.langgraph_agent_service import (
    LangGraphAgentService,
)
from src.infrastructure.langgraph.meta_supervisor_service import (
    MetaSupervisorService,
)
from src.infrastructure.langgraph.tools import RAGQueryTool
from src.infrastructure.langgraph.workers.fake_main_worker import FakeMainWorker
from src.infrastructure.langgraph.workers.fake_refund_worker import FakeRefundWorker
from src.infrastructure.line.line_messaging_service import HttpxLineMessagingService
from src.infrastructure.line.line_messaging_service_factory import (
    HttpxLineMessagingServiceFactory,
)
from src.infrastructure.llm.anthropic_llm_service import AnthropicLLMService
from src.infrastructure.llm.dynamic_llm_factory import (
    DynamicLLMServiceFactory,
    DynamicLLMServiceProxy,
)
from src.infrastructure.llm.fake_llm_service import FakeLLMService
from src.infrastructure.llm.openai_llm_service import OpenAILLMService
from src.infrastructure.qdrant.qdrant_vector_store import QdrantVectorStore
from src.infrastructure.sentiment.keyword_sentiment_service import (
    KeywordSentimentService,
)
from src.infrastructure.text_splitter.content_aware_text_splitter_service import (
    ContentAwareTextSplitterService,
)
from src.infrastructure.text_splitter.csv_row_text_splitter_service import (
    CSVRowTextSplitterService,
)
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
            "src.interfaces.api.agent_router",
            "src.interfaces.api.conversation_router",
            "src.interfaces.api.feedback_router",
            "src.interfaces.api.line_webhook_router",
            "src.interfaces.api.usage_router",
            "src.interfaces.api.bot_router",
            "src.interfaces.api.provider_setting_router",
            "src.interfaces.api.admin_router",
            "src.interfaces.api.deps",
        ],
    )

    config = providers.Singleton(Settings)

    # --- Infrastructure ---

    redis_client = providers.Singleton(
        aioredis.Redis.from_url,
        url=providers.Callable(lambda cfg: cfg.redis_url, config),
        decode_responses=False,
    )

    cache_service = providers.Singleton(
        RedisCacheService,
        redis_client=redis_client,
    )

    db_session = providers.Factory(async_session_factory)

    jwt_service = providers.Singleton(
        JWTService,
        secret_key=providers.Callable(lambda cfg: cfg.jwt_secret_key, config),
        algorithm=providers.Callable(lambda cfg: cfg.jwt_algorithm, config),
        access_token_expire_minutes=providers.Callable(
            lambda cfg: cfg.jwt_access_token_expire_minutes, config
        ),
    )

    password_service = providers.Singleton(
        BcryptPasswordService,
        rounds=providers.Callable(lambda cfg: cfg.bcrypt_rounds, config),
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

    conversation_repository = providers.Factory(
        SQLAlchemyConversationRepository,
        session=db_session,
    )

    feedback_repository = providers.Factory(
        SQLAlchemyFeedbackRepository,
        session=db_session,
    )

    usage_repository = providers.Factory(
        SQLAlchemyUsageRepository,
        session=db_session,
    )

    bot_repository = providers.Factory(
        SQLAlchemyBotRepository,
        session=db_session,
    )

    user_repository = providers.Factory(
        SQLAlchemyUserRepository,
        session=db_session,
    )

    rate_limit_config_repository = providers.Factory(
        SQLAlchemyRateLimitConfigRepository,
        session=db_session,
    )

    provider_setting_repository = providers.Factory(
        SQLAlchemyProviderSettingRepository,
        session=db_session,
    )

    encryption_service = providers.Singleton(
        AESEncryptionService,
        master_key=providers.Callable(
            lambda cfg: cfg.encryption_master_key
            or "0" * 64,  # fallback dev key (all zeros)
            config,
        ),
    )

    file_parser_service = providers.Singleton(DefaultFileParserService)

    _csv_splitter = providers.Singleton(
        CSVRowTextSplitterService,
        chunk_size=providers.Callable(lambda cfg: cfg.chunk_size, config),
        chunk_overlap=providers.Callable(lambda cfg: cfg.chunk_overlap, config),
    )

    _recursive_splitter = providers.Singleton(
        RecursiveTextSplitterService,
        chunk_size=providers.Callable(lambda cfg: cfg.chunk_size, config),
        chunk_overlap=providers.Callable(lambda cfg: cfg.chunk_overlap, config),
    )

    text_splitter_service = providers.Selector(
        providers.Callable(lambda cfg: cfg.chunk_strategy, config),
        auto=providers.Singleton(
            ContentAwareTextSplitterService,
            strategies=providers.Dict({"text/csv": _csv_splitter}),
            default=_recursive_splitter,
        ),
        recursive=_recursive_splitter,
        csv_row=_csv_splitter,
    )

    _static_embedding_service = providers.Selector(
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
                lambda cfg: cfg.effective_embedding_api_key, config
            ),
            model=providers.Callable(
                lambda cfg: cfg.embedding_model, config
            ),
            base_url=providers.Callable(
                lambda cfg: cfg.embedding_base_url or "https://api.openai.com/v1",
                config,
            ),
            batch_size=providers.Callable(
                lambda cfg: cfg.embedding_batch_size, config
            ),
            max_retries=providers.Callable(
                lambda cfg: cfg.embedding_max_retries, config
            ),
            timeout=providers.Callable(
                lambda cfg: cfg.embedding_timeout, config
            ),
            batch_delay=providers.Callable(
                lambda cfg: cfg.embedding_batch_delay, config
            ),
            retry_after_multiplier=providers.Callable(
                lambda cfg: cfg.embedding_retry_after_multiplier, config
            ),
            min_batch_size=providers.Callable(
                lambda cfg: cfg.embedding_min_batch_size, config
            ),
        ),
        qwen=providers.Factory(
            OpenAIEmbeddingService,
            api_key=providers.Callable(
                lambda cfg: cfg.effective_embedding_api_key, config
            ),
            model=providers.Callable(
                lambda cfg: cfg.embedding_model, config
            ),
            base_url=providers.Callable(
                lambda cfg: cfg.embedding_base_url
                or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                config,
            ),
            batch_size=providers.Callable(
                lambda cfg: cfg.embedding_batch_size, config
            ),
            max_retries=providers.Callable(
                lambda cfg: cfg.embedding_max_retries, config
            ),
            timeout=providers.Callable(
                lambda cfg: cfg.embedding_timeout, config
            ),
            batch_delay=providers.Callable(
                lambda cfg: cfg.embedding_batch_delay, config
            ),
            retry_after_multiplier=providers.Callable(
                lambda cfg: cfg.embedding_retry_after_multiplier, config
            ),
            min_batch_size=providers.Callable(
                lambda cfg: cfg.embedding_min_batch_size, config
            ),
        ),
        google=providers.Factory(
            OpenAIEmbeddingService,
            api_key=providers.Callable(
                lambda cfg: cfg.effective_embedding_api_key, config
            ),
            model=providers.Callable(
                lambda cfg: cfg.embedding_model, config
            ),
            base_url=providers.Callable(
                lambda cfg: cfg.embedding_base_url
                or "https://generativelanguage.googleapis.com/v1beta/openai",
                config,
            ),
            batch_size=providers.Callable(
                lambda cfg: cfg.embedding_batch_size, config
            ),
            max_retries=providers.Callable(
                lambda cfg: cfg.embedding_max_retries, config
            ),
            timeout=providers.Callable(
                lambda cfg: cfg.embedding_timeout, config
            ),
            batch_delay=providers.Callable(
                lambda cfg: cfg.embedding_batch_delay, config
            ),
            retry_after_multiplier=providers.Callable(
                lambda cfg: cfg.embedding_retry_after_multiplier, config
            ),
            min_batch_size=providers.Callable(
                lambda cfg: cfg.embedding_min_batch_size, config
            ),
        ),
    )

    _embedding_factory = providers.Singleton(
        DynamicEmbeddingServiceFactory,
        provider_setting_repository=provider_setting_repository,
        encryption_service=encryption_service,
        fallback_service=_static_embedding_service,
        cache_service=cache_service,
        cache_ttl=providers.Callable(
            lambda cfg: cfg.cache_provider_config_ttl, config
        ),
    )

    embedding_service = providers.Singleton(
        DynamicEmbeddingServiceProxy,
        factory=_embedding_factory,
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

    _static_llm_service = providers.Selector(
        providers.Callable(lambda cfg: cfg.llm_provider, config),
        fake=providers.Factory(FakeLLMService),
        anthropic=providers.Factory(
            AnthropicLLMService,
            api_key=providers.Callable(
                lambda cfg: cfg.effective_llm_api_key, config
            ),
            model=providers.Callable(
                lambda cfg: cfg.llm_model or "claude-sonnet-4-20250514", config
            ),
            max_tokens=providers.Callable(
                lambda cfg: cfg.llm_max_tokens, config
            ),
            pricing=providers.Callable(
                lambda cfg: cfg.llm_pricing, config
            ),
        ),
        openai=providers.Factory(
            OpenAILLMService,
            api_key=providers.Callable(
                lambda cfg: cfg.effective_llm_api_key, config
            ),
            model=providers.Callable(
                lambda cfg: cfg.llm_model or "gpt-4o", config
            ),
            max_tokens=providers.Callable(
                lambda cfg: cfg.llm_max_tokens, config
            ),
            pricing=providers.Callable(
                lambda cfg: cfg.llm_pricing, config
            ),
            base_url=providers.Callable(
                lambda cfg: cfg.llm_base_url or "https://api.openai.com/v1",
                config,
            ),
        ),
        qwen=providers.Factory(
            OpenAILLMService,
            api_key=providers.Callable(
                lambda cfg: cfg.effective_llm_api_key, config
            ),
            model=providers.Callable(
                lambda cfg: cfg.llm_model or "qwen-plus", config
            ),
            max_tokens=providers.Callable(
                lambda cfg: cfg.llm_max_tokens, config
            ),
            pricing=providers.Callable(
                lambda cfg: cfg.llm_pricing, config
            ),
            base_url=providers.Callable(
                lambda cfg: cfg.llm_base_url
                or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                config,
            ),
        ),
        google=providers.Factory(
            OpenAILLMService,
            api_key=providers.Callable(
                lambda cfg: cfg.effective_llm_api_key, config
            ),
            model=providers.Callable(
                lambda cfg: cfg.llm_model or "gemini-2.5-flash-lite", config
            ),
            max_tokens=providers.Callable(
                lambda cfg: cfg.llm_max_tokens, config
            ),
            pricing=providers.Callable(
                lambda cfg: cfg.llm_pricing, config
            ),
            base_url=providers.Callable(
                lambda cfg: cfg.llm_base_url
                or "https://generativelanguage.googleapis.com/v1beta/openai",
                config,
            ),
        ),
        openrouter=providers.Factory(
            OpenAILLMService,
            api_key=providers.Callable(
                lambda cfg: cfg.effective_llm_api_key, config
            ),
            model=providers.Callable(
                lambda cfg: cfg.llm_model or "openai/gpt-4o", config
            ),
            max_tokens=providers.Callable(
                lambda cfg: cfg.llm_max_tokens, config
            ),
            pricing=providers.Callable(
                lambda cfg: cfg.llm_pricing, config
            ),
            base_url=providers.Callable(
                lambda cfg: cfg.llm_base_url or "https://openrouter.ai/api/v1",
                config,
            ),
        ),
    )

    _llm_factory = providers.Singleton(
        DynamicLLMServiceFactory,
        provider_setting_repository=provider_setting_repository,
        encryption_service=encryption_service,
        fallback_service=_static_llm_service,
        cache_service=cache_service,
        cache_ttl=providers.Callable(
            lambda cfg: cfg.cache_provider_config_ttl, config
        ),
    )

    llm_service = providers.Singleton(
        DynamicLLMServiceProxy,
        factory=_llm_factory,
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

    register_user_use_case = providers.Factory(
        RegisterUserUseCase,
        user_repository=user_repository,
        password_service=password_service,
    )

    login_use_case = providers.Factory(
        LoginUseCase,
        user_repository=user_repository,
        password_service=password_service,
        jwt_service=jwt_service,
    )

    get_user_use_case = providers.Factory(
        GetUserUseCase,
        user_repository=user_repository,
    )

    get_rate_limits_use_case = providers.Factory(
        GetRateLimitsUseCase,
        rate_limit_config_repository=rate_limit_config_repository,
    )

    update_rate_limit_use_case = providers.Factory(
        UpdateRateLimitUseCase,
        rate_limit_config_repository=rate_limit_config_repository,
    )

    seed_defaults_use_case = providers.Factory(
        SeedDefaultsUseCase,
        rate_limit_config_repository=rate_limit_config_repository,
    )

    create_knowledge_base_use_case = providers.Factory(
        CreateKnowledgeBaseUseCase,
        knowledge_base_repository=kb_repository,
    )

    list_knowledge_bases_use_case = providers.Factory(
        ListKnowledgeBasesUseCase,
        knowledge_base_repository=kb_repository,
    )

    list_documents_use_case = providers.Factory(
        ListDocumentsUseCase,
        document_repository=document_repository,
    )

    delete_document_use_case = providers.Factory(
        DeleteDocumentUseCase,
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        vector_store=vector_store,
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

    get_document_chunks_use_case = providers.Factory(
        GetDocumentChunksUseCase,
        chunk_repository=chunk_repository,
    )

    reprocess_document_use_case = providers.Factory(
        ReprocessDocumentUseCase,
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        processing_task_repository=processing_task_repository,
        text_splitter_service=text_splitter_service,
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    get_document_quality_stats_use_case = providers.Factory(
        GetDocumentQualityStatsUseCase,
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        feedback_repository=feedback_repository,
    )

    query_rag_use_case = providers.Factory(
        QueryRAGUseCase,
        knowledge_base_repository=kb_repository,
        embedding_service=embedding_service,
        vector_store=vector_store,
        llm_service=llm_service,
    )

    get_conversation_use_case = providers.Factory(
        GetConversationUseCase,
        conversation_repository=conversation_repository,
    )

    list_conversations_use_case = providers.Factory(
        ListConversationsUseCase,
        conversation_repository=conversation_repository,
    )

    submit_feedback_use_case = providers.Factory(
        SubmitFeedbackUseCase,
        feedback_repository=feedback_repository,
        conversation_repository=conversation_repository,
    )

    get_feedback_stats_use_case = providers.Factory(
        GetFeedbackStatsUseCase,
        feedback_repository=feedback_repository,
        cache_service=cache_service,
        cache_ttl=providers.Callable(
            lambda cfg: cfg.cache_feedback_stats_ttl, config
        ),
    )

    list_feedback_use_case = providers.Factory(
        ListFeedbackUseCase,
        feedback_repository=feedback_repository,
    )

    get_satisfaction_trend_use_case = providers.Factory(
        GetSatisfactionTrendUseCase,
        feedback_repository=feedback_repository,
    )

    get_top_issues_use_case = providers.Factory(
        GetTopIssuesUseCase,
        feedback_repository=feedback_repository,
    )

    get_retrieval_quality_use_case = providers.Factory(
        GetRetrievalQualityUseCase,
        feedback_repository=feedback_repository,
    )

    get_token_cost_stats_use_case = providers.Factory(
        GetTokenCostStatsUseCase,
        usage_repository=usage_repository,
    )

    record_usage_use_case = providers.Factory(
        RecordUsageUseCase,
        usage_repository=usage_repository,
    )

    query_usage_use_case = providers.Factory(
        QueryUsageUseCase,
        usage_repository=usage_repository,
    )

    # --- Agent Tools ---

    rag_tool = providers.Factory(
        RAGQueryTool,
        query_rag_use_case=query_rag_use_case,
        top_k=config.provided.rag_top_k,
        score_threshold=config.provided.rag_score_threshold,
    )

    # --- Agent Service ---

    sentiment_service = providers.Singleton(KeywordSentimentService)

    customer_team = providers.Factory(
        TeamSupervisor,
        team_name="customer",
        workers=providers.List(
            providers.Factory(FakeRefundWorker),
            providers.Factory(FakeMainWorker),
        ),
    )

    agent_service = providers.Selector(
        providers.Callable(lambda cfg: cfg.llm_provider, config),
        fake=providers.Factory(
            MetaSupervisorService,
            teams=providers.Dict(
                customer=customer_team,
            ),
            sentiment_service=sentiment_service,
        ),
        anthropic=providers.Factory(
            LangGraphAgentService,
            llm_service=llm_service,
            rag_tool=rag_tool,
        ),
        openai=providers.Factory(
            LangGraphAgentService,
            llm_service=llm_service,
            rag_tool=rag_tool,
        ),
        qwen=providers.Factory(
            LangGraphAgentService,
            llm_service=llm_service,
            rag_tool=rag_tool,
        ),
        google=providers.Factory(
            LangGraphAgentService,
            llm_service=llm_service,
            rag_tool=rag_tool,
        ),
        openrouter=providers.Factory(
            LangGraphAgentService,
            llm_service=llm_service,
            rag_tool=rag_tool,
        ),
    )

    # --- Conversation History Strategy ---

    history_strategy = providers.Selector(
        providers.Callable(
            lambda cfg: cfg.history_strategy, config
        ),
        full=providers.Factory(FullHistoryStrategy),
        sliding_window=providers.Factory(SlidingWindowStrategy),
        summary_recent=providers.Factory(
            SummaryRecentStrategy,
            llm_service=llm_service,
            cache_service=cache_service,
            cache_ttl=providers.Callable(
                lambda cfg: cfg.cache_summary_ttl, config
            ),
        ),
        rag_history=providers.Factory(RAGHistoryStrategy),
    )

    create_bot_use_case = providers.Factory(
        CreateBotUseCase,
        bot_repository=bot_repository,
    )

    list_bots_use_case = providers.Factory(
        ListBotsUseCase,
        bot_repository=bot_repository,
    )

    get_bot_use_case = providers.Factory(
        GetBotUseCase,
        bot_repository=bot_repository,
    )

    update_bot_use_case = providers.Factory(
        UpdateBotUseCase,
        bot_repository=bot_repository,
        cache_service=cache_service,
    )

    delete_bot_use_case = providers.Factory(
        DeleteBotUseCase,
        bot_repository=bot_repository,
        cache_service=cache_service,
    )

    send_message_use_case = providers.Factory(
        SendMessageUseCase,
        agent_service=agent_service,
        conversation_repository=conversation_repository,
        bot_repository=bot_repository,
        history_strategy=history_strategy,
    )

    # --- Platform: Provider Settings ---

    create_provider_setting_use_case = providers.Factory(
        CreateProviderSettingUseCase,
        provider_setting_repository=provider_setting_repository,
        encryption_service=encryption_service,
    )

    update_provider_setting_use_case = providers.Factory(
        UpdateProviderSettingUseCase,
        provider_setting_repository=provider_setting_repository,
        encryption_service=encryption_service,
        cache_service=cache_service,
    )

    delete_provider_setting_use_case = providers.Factory(
        DeleteProviderSettingUseCase,
        provider_setting_repository=provider_setting_repository,
        cache_service=cache_service,
    )

    list_provider_settings_use_case = providers.Factory(
        ListProviderSettingsUseCase,
        provider_setting_repository=provider_setting_repository,
    )

    get_provider_setting_use_case = providers.Factory(
        GetProviderSettingUseCase,
        provider_setting_repository=provider_setting_repository,
    )

    check_provider_connection_use_case = providers.Factory(
        CheckProviderConnectionUseCase,
        provider_setting_repository=provider_setting_repository,
        encryption_service=encryption_service,
    )

    # --- LINE Bot ---

    line_messaging_service = providers.Singleton(
        HttpxLineMessagingService,
        channel_secret=providers.Callable(
            lambda cfg: cfg.line_channel_secret, config
        ),
        channel_access_token=providers.Callable(
            lambda cfg: cfg.line_channel_access_token, config
        ),
    )

    line_messaging_service_factory = providers.Singleton(
        HttpxLineMessagingServiceFactory,
    )

    handle_webhook_use_case = providers.Factory(
        HandleWebhookUseCase,
        agent_service=agent_service,
        bot_repository=bot_repository,
        line_service_factory=line_messaging_service_factory,
        default_line_service=line_messaging_service,
        default_tenant_id=providers.Callable(
            lambda cfg: cfg.line_default_tenant_id, config
        ),
        default_kb_id=providers.Callable(
            lambda cfg: cfg.line_default_kb_id, config
        ),
        feedback_repository=feedback_repository,
        cache_service=cache_service,
        cache_ttl=providers.Callable(
            lambda cfg: cfg.cache_bot_ttl, config
        ),
    )
