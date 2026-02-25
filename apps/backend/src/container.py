from dependency_injector import containers, providers

from src.application.agent.order_lookup_use_case import OrderLookupUseCase
from src.application.agent.product_search_use_case import ProductSearchUseCase
from src.application.agent.send_message_use_case import SendMessageUseCase
from src.application.agent.ticket_creation_use_case import TicketCreationUseCase
from src.application.bot.create_bot_use_case import CreateBotUseCase
from src.application.bot.delete_bot_use_case import DeleteBotUseCase
from src.application.bot.get_bot_use_case import GetBotUseCase
from src.application.bot.list_bots_use_case import ListBotsUseCase
from src.application.bot.update_bot_use_case import UpdateBotUseCase
from src.application.conversation.get_conversation_use_case import (
    GetConversationUseCase,
)
from src.application.conversation.list_conversations_use_case import (
    ListConversationsUseCase,
)
from src.application.health.health_check_use_case import HealthCheckUseCase
from src.application.knowledge.create_knowledge_base_use_case import (
    CreateKnowledgeBaseUseCase,
)
from src.application.knowledge.delete_document_use_case import (
    DeleteDocumentUseCase,
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
from src.application.knowledge.upload_document_use_case import (
    UploadDocumentUseCase,
)
from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.application.rag.query_rag_use_case import QueryRAGUseCase
from src.application.tenant.create_tenant_use_case import CreateTenantUseCase
from src.application.tenant.get_tenant_use_case import GetTenantUseCase
from src.application.tenant.list_tenants_use_case import ListTenantsUseCase
from src.application.usage.query_usage_use_case import QueryUsageUseCase
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.config import Settings
from src.domain.agent.team_supervisor import TeamSupervisor
from src.infrastructure.auth.jwt_service import JWTService
from src.infrastructure.db.engine import async_session_factory
from src.infrastructure.db.health_repository import HealthRepository
from src.infrastructure.db.repositories.chunk_repository import (
    SQLAlchemyChunkRepository,
)
from src.infrastructure.db.repositories.conversation_repository import (
    SQLAlchemyConversationRepository,
)
from src.infrastructure.db.repositories.document_repository import (
    SQLAlchemyDocumentRepository,
)
from src.infrastructure.db.repositories.bot_repository import (
    SQLAlchemyBotRepository,
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
from src.infrastructure.db.repositories.usage_repository import (
    SQLAlchemyUsageRepository,
)
from src.infrastructure.conversation import (
    FullHistoryStrategy,
    RAGHistoryStrategy,
    SlidingWindowStrategy,
    SummaryRecentStrategy,
)
from src.infrastructure.embedding.fake_embedding_service import (
    FakeEmbeddingService,
)
from src.infrastructure.embedding.openai_embedding_service import (
    OpenAIEmbeddingService,
)
from src.infrastructure.events.in_memory_event_bus import InMemoryEventBus
from src.infrastructure.file_parser.default_file_parser_service import (
    DefaultFileParserService,
)
from src.infrastructure.langgraph.langgraph_agent_service import (
    LangGraphAgentService,
)
from src.infrastructure.langgraph.meta_supervisor_service import (
    MetaSupervisorService,
)
from src.infrastructure.langgraph.tools import (
    OrderLookupTool,
    ProductRecommendTool,
    ProductSearchTool,
    RAGQueryTool,
    TicketCreationTool,
)
from src.infrastructure.langgraph.workers.fake_main_worker import FakeMainWorker
from src.infrastructure.langgraph.workers.fake_refund_worker import FakeRefundWorker
from src.infrastructure.line.line_messaging_service import HttpxLineMessagingService
from src.infrastructure.llm.anthropic_llm_service import AnthropicLLMService
from src.infrastructure.llm.fake_llm_service import FakeLLMService
from src.infrastructure.llm.openai_llm_service import OpenAILLMService
from src.infrastructure.qdrant.qdrant_vector_store import QdrantVectorStore
from src.infrastructure.sentiment.keyword_sentiment_service import (
    KeywordSentimentService,
)
from src.infrastructure.text_splitter.recursive_text_splitter_service import (
    RecursiveTextSplitterService,
)
from src.infrastructure.tools.sql_order_lookup_service import (
    SQLOrderLookupService,
)
from src.infrastructure.tools.sql_product_search_service import (
    SQLProductSearchService,
)
from src.infrastructure.tools.sql_ticket_service import SQLTicketService


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
            "src.interfaces.api.line_webhook_router",
            "src.interfaces.api.usage_router",
            "src.interfaces.api.bot_router",
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

    conversation_repository = providers.Factory(
        SQLAlchemyConversationRepository,
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

    file_parser_service = providers.Singleton(DefaultFileParserService)

    text_splitter_service = providers.Singleton(
        RecursiveTextSplitterService,
        chunk_size=providers.Callable(lambda cfg: cfg.chunk_size, config),
        chunk_overlap=providers.Callable(lambda cfg: cfg.chunk_overlap, config),
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
                lambda cfg: cfg.effective_embedding_api_key, config
            ),
            model=providers.Callable(
                lambda cfg: cfg.embedding_model, config
            ),
            base_url=providers.Callable(
                lambda cfg: cfg.embedding_base_url or "https://api.openai.com/v1",
                config,
            ),
            batch_size=providers.Callable(lambda cfg: cfg.embedding_batch_size, config),
            max_retries=providers.Callable(lambda cfg: cfg.embedding_max_retries, config),
            timeout=providers.Callable(lambda cfg: cfg.embedding_timeout, config),
            batch_delay=providers.Callable(lambda cfg: cfg.embedding_batch_delay, config),
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
            batch_size=providers.Callable(lambda cfg: cfg.embedding_batch_size, config),
            max_retries=providers.Callable(lambda cfg: cfg.embedding_max_retries, config),
            timeout=providers.Callable(lambda cfg: cfg.embedding_timeout, config),
            batch_delay=providers.Callable(lambda cfg: cfg.embedding_batch_delay, config),
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
            batch_size=providers.Callable(lambda cfg: cfg.embedding_batch_size, config),
            max_retries=providers.Callable(lambda cfg: cfg.embedding_max_retries, config),
            timeout=providers.Callable(lambda cfg: cfg.embedding_timeout, config),
            batch_delay=providers.Callable(lambda cfg: cfg.embedding_batch_delay, config),
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

    # --- Tool Services ---

    order_lookup_service = providers.Factory(
        SQLOrderLookupService,
        session_factory=providers.Object(async_session_factory),
    )

    product_search_service = providers.Factory(
        SQLProductSearchService,
        session_factory=providers.Object(async_session_factory),
    )

    ticket_service = providers.Factory(
        SQLTicketService,
        session_factory=providers.Object(async_session_factory),
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

    record_usage_use_case = providers.Factory(
        RecordUsageUseCase,
        usage_repository=usage_repository,
    )

    query_usage_use_case = providers.Factory(
        QueryUsageUseCase,
        usage_repository=usage_repository,
    )

    order_lookup_use_case = providers.Factory(
        OrderLookupUseCase,
        order_lookup_service=order_lookup_service,
    )

    product_search_use_case = providers.Factory(
        ProductSearchUseCase,
        product_search_service=product_search_service,
    )

    ticket_creation_use_case = providers.Factory(
        TicketCreationUseCase,
        ticket_service=ticket_service,
    )

    # --- Agent Tools ---

    rag_tool = providers.Factory(
        RAGQueryTool,
        query_rag_use_case=query_rag_use_case,
        top_k=config.provided.rag_top_k,
        score_threshold=config.provided.rag_score_threshold,
    )

    order_tool = providers.Factory(
        OrderLookupTool,
        use_case=order_lookup_use_case,
    )

    product_tool = providers.Factory(
        ProductSearchTool,
        use_case=product_search_use_case,
    )

    ticket_tool = providers.Factory(
        TicketCreationTool,
        use_case=ticket_creation_use_case,
    )

    product_recommend_tool = providers.Factory(
        ProductRecommendTool,
        query_rag_use_case=query_rag_use_case,
        kb_repository=kb_repository,
        top_k=config.provided.rag_top_k,
        score_threshold=config.provided.rag_score_threshold,
    )

    # --- Event Bus ---

    event_bus = providers.Singleton(InMemoryEventBus)

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
            order_tool=order_tool,
            product_tool=product_tool,
            ticket_tool=ticket_tool,
            product_recommend_tool=product_recommend_tool,
        ),
        openai=providers.Factory(
            LangGraphAgentService,
            llm_service=llm_service,
            rag_tool=rag_tool,
            order_tool=order_tool,
            product_tool=product_tool,
            ticket_tool=ticket_tool,
            product_recommend_tool=product_recommend_tool,
        ),
        qwen=providers.Factory(
            LangGraphAgentService,
            llm_service=llm_service,
            rag_tool=rag_tool,
            product_recommend_tool=product_recommend_tool,
        ),
        google=providers.Factory(
            LangGraphAgentService,
            llm_service=llm_service,
            rag_tool=rag_tool,
            product_recommend_tool=product_recommend_tool,
        ),
        openrouter=providers.Factory(
            LangGraphAgentService,
            llm_service=llm_service,
            rag_tool=rag_tool,
            order_tool=order_tool,
            product_tool=product_tool,
            ticket_tool=ticket_tool,
            product_recommend_tool=product_recommend_tool,
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
    )

    delete_bot_use_case = providers.Factory(
        DeleteBotUseCase,
        bot_repository=bot_repository,
    )

    send_message_use_case = providers.Factory(
        SendMessageUseCase,
        agent_service=agent_service,
        conversation_repository=conversation_repository,
        bot_repository=bot_repository,
        history_strategy=history_strategy,
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

    handle_webhook_use_case = providers.Factory(
        HandleWebhookUseCase,
        agent_service=agent_service,
        line_messaging_service=line_messaging_service,
        default_tenant_id=providers.Callable(
            lambda cfg: cfg.line_default_tenant_id, config
        ),
        default_kb_id=providers.Callable(
            lambda cfg: cfg.line_default_kb_id, config
        ),
    )
