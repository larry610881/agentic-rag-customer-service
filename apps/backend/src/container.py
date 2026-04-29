import redis.asyncio as aioredis
from dependency_injector import containers, providers

from src.application.agent.intent_classifier import IntentClassifier
from src.application.agent.list_built_in_tools_use_case import (
    ListBuiltInToolsUseCase,
)
from src.application.agent.send_message_use_case import SendMessageUseCase
from src.application.agent.tool_registry import ToolRegistry
from src.application.agent.update_built_in_tool_scope_use_case import (
    UpdateBuiltInToolScopeUseCase,
)
from src.application.auth.change_password_use_case import ChangePasswordUseCase
from src.application.auth.delete_user_use_case import DeleteUserUseCase
from src.application.auth.get_user_use_case import GetUserUseCase
from src.application.auth.list_users_use_case import ListUsersUseCase
from src.application.auth.login_use_case import LoginUseCase
from src.application.auth.register_user_use_case import RegisterUserUseCase
from src.application.auth.reset_password_use_case import ResetPasswordUseCase
from src.application.auth.update_user_use_case import UpdateUserUseCase
from src.application.billing.get_billing_dashboard_use_case import (
    GetBillingDashboardUseCase,
)
from src.application.billing.list_quota_events_use_case import (
    ListQuotaEventsUseCase,
)
from src.application.billing.process_quota_alerts_use_case import (
    ProcessQuotaAlertsUseCase,
)
from src.application.billing.quota_email_dispatch_use_case import (
    QuotaEmailDispatchUseCase,
)
from src.application.billing.topup_addon_use_case import TopupAddonUseCase
from src.application.bot.create_bot_use_case import CreateBotUseCase
from src.application.bot.delete_bot_use_case import DeleteBotUseCase
from src.application.bot.get_bot_use_case import GetBotUseCase
from src.application.bot.list_all_bots_use_case import ListAllBotsUseCase
from src.application.bot.list_bots_use_case import ListBotsUseCase
from src.application.bot.update_bot_use_case import UpdateBotUseCase
from src.application.bot.upload_bot_icon_use_case import UploadBotIconUseCase
from src.application.bot.worker_use_cases import (
    CreateWorkerUseCase,
    DeleteWorkerUseCase,
    ListWorkersUseCase,
    UpdateWorkerUseCase,
)
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
from src.application.conversation.generate_summary_use_case import (
    GenerateConversationSummaryUseCase,
)
from src.application.conversation.search_conversations_use_case import (
    SearchConversationsUseCase,
)
from src.application.eval_dataset.create_eval_dataset_use_case import (
    CreateEvalDatasetUseCase,
)
from src.application.eval_dataset.delete_eval_dataset_use_case import (
    DeleteEvalDatasetUseCase,
)
from src.application.eval_dataset.eval_use_cases import (
    EstimateCostUseCase,
    RunSingleEvalUseCase,
    RunValidationEvalUseCase,
)
from src.application.eval_dataset.get_eval_dataset_use_case import (
    GetEvalDatasetUseCase,
)
from src.application.eval_dataset.list_eval_datasets_use_case import (
    ListEvalDatasetsUseCase,
)
from src.application.eval_dataset.manage_test_cases_use_case import (
    CreateTestCaseUseCase,
    DeleteTestCaseUseCase,
)
from src.application.eval_dataset.run_use_cases import (
    GetRunDiffUseCase,
    GetRunReportUseCase,
    GetRunUseCase,
    ListRunsUseCase,
    RollbackRunUseCase,
    StartRunUseCase,
    StopRunUseCase,
)
from src.application.eval_dataset.update_eval_dataset_use_case import (
    UpdateEvalDatasetUseCase,
)
from src.application.health.health_check_use_case import HealthCheckUseCase
from src.application.knowledge.classify_kb_use_case import ClassifyKbUseCase
from src.application.knowledge.create_knowledge_base_use_case import (
    CreateKnowledgeBaseUseCase,
)
from src.application.knowledge.delete_document_use_case import (
    DeleteDocumentUseCase,
)
from src.application.knowledge.delete_knowledge_base_use_case import (
    DeleteKnowledgeBaseUseCase,
)
from src.application.knowledge.get_category_chunks_use_case import (
    GetCategoryChunksUseCase,
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
from src.application.knowledge.list_all_knowledge_bases_use_case import (
    ListAllKnowledgeBasesUseCase,
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
from src.application.knowledge.split_pdf_use_case import SplitPdfUseCase
from src.application.knowledge.update_knowledge_base_use_case import (
    UpdateKnowledgeBaseUseCase,
)
from src.application.knowledge.upload_document_use_case import (
    UploadDocumentUseCase,
)
from src.application.knowledge.view_document_use_case import (
    ViewDocumentUseCase,
)
from src.application.ledger.ensure_ledger_use_case import EnsureLedgerUseCase
from src.application.ledger.get_tenant_quota_use_case import (
    GetTenantQuotaUseCase,
)
from src.application.ledger.list_all_tenants_quotas_use_case import (
    ListAllTenantsQuotasUseCase,
)
from src.application.ledger.process_monthly_reset_use_case import (
    ProcessMonthlyResetUseCase,
)
from src.application.quota.compute_tenant_quota_use_case import (
    ComputeTenantQuotaUseCase,
)
from src.application.line.handle_webhook_use_case import HandleWebhookUseCase
from src.application.memory.extract_memory_use_case import ExtractMemoryUseCase
from src.application.memory.load_memory_use_case import LoadMemoryUseCase
from src.application.memory.resolve_identity_use_case import (
    ResolveIdentityUseCase,
)
from src.application.observability.diagnostic_rules_use_cases import (
    GetDiagnosticRulesUseCase,
    ResetDiagnosticRulesUseCase,
    UpdateDiagnosticRulesUseCase,
)
from src.application.observability.error_event_use_cases import (
    GetErrorEventUseCase,
    ListErrorEventsUseCase,
    ReportErrorUseCase,
    ResolveErrorEventUseCase,
)
from src.application.observability.log_retention_use_cases import (
    ExecuteLogCleanupUseCase,
    GetLogRetentionPolicyUseCase,
    UpdateLogRetentionPolicyUseCase,
)
from src.application.observability.notification_use_cases import (
    CreateChannelUseCase,
    DeleteChannelUseCase,
    DispatchNotificationUseCase,
    ListChannelsUseCase,
    NotificationDispatcher,
    SendTestNotificationUseCase,
    UpdateChannelUseCase,
)
from src.application.observability.rag_evaluation_use_case import (
    RAGEvaluationUseCase,
)
from src.application.plan.assign_plan_to_tenant_use_case import (
    AssignPlanToTenantUseCase,
)
from src.application.plan.create_plan_use_case import CreatePlanUseCase
from src.application.plan.delete_plan_use_case import DeletePlanUseCase
from src.application.plan.get_plan_use_case import GetPlanUseCase
from src.application.plan.list_plans_use_case import ListPlansUseCase
from src.application.plan.update_plan_use_case import UpdatePlanUseCase
from src.application.platform.create_provider_setting_use_case import (
    CreateProviderSettingUseCase,
)
from src.application.pricing.create_pricing_use_case import (
    CreatePricingUseCase,
)
from src.application.pricing.deactivate_pricing_use_case import (
    DeactivatePricingUseCase,
)
from src.application.pricing.dry_run_recalculate_use_case import (
    DryRunRecalculateUseCase,
)
from src.application.pricing.execute_recalculate_use_case import (
    ExecuteRecalculateUseCase,
)
from src.application.pricing.list_pricing_use_case import ListPricingUseCase

# S-KB-Studio.1 use cases
from src.application.knowledge.update_chunk_use_case import UpdateChunkUseCase
from src.application.knowledge.delete_chunk_use_case import DeleteChunkUseCase
from src.application.knowledge.list_kb_chunks_use_case import ListKbChunksUseCase
from src.application.knowledge.test_retrieval_use_case import TestRetrievalUseCase
from src.application.knowledge.reembed_chunk_use_case import ReEmbedChunkUseCase
from src.application.knowledge.get_kb_quality_summary_use_case import (
    GetKbQualitySummaryUseCase,
)
from src.application.chunk_category.create_category_use_case import (
    CreateCategoryUseCase,
)
from src.application.chunk_category.delete_category_use_case import (
    DeleteCategoryUseCase,
)
from src.application.chunk_category.assign_chunks_use_case import (
    AssignChunksUseCase,
)
from src.application.milvus.list_collections_use_case import (
    ListCollectionsUseCase as ListMilvusCollectionsUseCase,
)
from src.application.milvus.get_collection_stats_use_case import (
    GetCollectionStatsUseCase,
)
from src.application.milvus.rebuild_index_use_case import RebuildIndexUseCase
from src.application.conversation.get_conversation_messages_use_case import (
    GetConversationMessagesUseCase,
)
from src.application.conversation.get_conversation_token_usage_use_case import (
    GetConversationTokenUsageUseCase,
)
from src.application.conversation.list_conv_summaries_use_case import (
    ListConvSummariesUseCase,
)
from src.application.pricing.list_recalc_history_use_case import (
    ListRecalcHistoryUseCase,
)
from src.application.platform.delete_provider_setting_use_case import (
    DeleteProviderSettingUseCase,
)
from src.application.platform.get_provider_setting_use_case import (
    GetProviderSettingUseCase,
)
from src.application.platform.list_enabled_models_use_case import (
    ListEnabledModelsUseCase,
)
from src.application.platform.list_provider_settings_use_case import (
    ListProviderSettingsUseCase,
)
from src.application.platform.mcp.create_mcp_server_use_case import (
    CreateMcpServerUseCase,
)
from src.application.platform.mcp.delete_mcp_server_use_case import (
    DeleteMcpServerUseCase,
)
from src.application.platform.mcp.discover_mcp_server_use_case import (
    DiscoverMcpServerUseCase,
)
from src.application.platform.mcp.test_connection_use_case import (
    TestMcpConnectionUseCase,
)
from src.application.platform.mcp.update_mcp_server_use_case import (
    UpdateMcpServerUseCase,
)
from src.application.platform.system_prompt_use_cases import (
    GetSystemPromptsUseCase,
    UpdateSystemPromptsUseCase,
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
from src.application.security.guard_rules_use_cases import (
    GetGuardRulesUseCase,
    ResetGuardRulesUseCase,
    UpdateGuardRulesUseCase,
)
from src.application.security.prompt_guard_service import PromptGuardService
from src.application.tenant.create_tenant_use_case import CreateTenantUseCase
from src.application.tenant.get_tenant_use_case import GetTenantUseCase
from src.application.tenant.list_tenants_use_case import ListTenantsUseCase
from src.application.tenant.update_tenant_use_case import UpdateTenantUseCase
from src.application.usage.query_bot_usage_use_case import QueryBotUsageUseCase
from src.application.usage.query_daily_usage_use_case import QueryDailyUsageUseCase
from src.application.usage.query_monthly_usage_use_case import QueryMonthlyUsageUseCase
from src.application.usage.query_usage_use_case import QueryUsageUseCase
from src.application.usage.record_usage_use_case import RecordUsageUseCase
from src.config import Settings
from src.domain.agent.team_supervisor import TeamSupervisor
from src.infrastructure.auth.bcrypt_password_service import BcryptPasswordService
from src.infrastructure.auth.jwt_service import JWTService
from src.infrastructure.cache.redis_cache_service import RedisCacheService
from src.infrastructure.classification.cluster_classification_service import (
    ClusterClassificationService,
)
from src.infrastructure.concurrency import RedisConversationLock
from src.infrastructure.context.llm_chunk_context_service import (
    LLMChunkContextService,
)
from src.infrastructure.conversation import (
    FullHistoryStrategy,
    RAGHistoryStrategy,
    SlidingWindowStrategy,
    SummaryRecentStrategy,
)
from src.infrastructure.conversation.llm_summary_service import (
    LLMConversationSummaryService,
)
from src.infrastructure.crypto.aes_encryption_service import AESEncryptionService
from src.infrastructure.db.engine import (
    async_session_factory as _async_session_factory,
)
from src.infrastructure.db.health_repository import HealthRepository
from src.infrastructure.db.repositories.billing_transaction_repository import (
    SQLAlchemyBillingTransactionRepository,
)
from src.infrastructure.db.repositories.bot_repository import (
    SQLAlchemyBotRepository,
)
from src.infrastructure.db.repositories.built_in_tool_repository import (
    SQLAlchemyBuiltInToolRepository,
)
from src.infrastructure.db.repositories.chunk_category_repository import (
    SQLAlchemyChunkCategoryRepository,
)
from src.infrastructure.db.repositories.conversation_repository import (
    SQLAlchemyConversationRepository,
)
from src.infrastructure.db.repositories.diagnostic_rules_config_repository import (
    SQLAlchemyDiagnosticRulesConfigRepository,
)
from src.infrastructure.db.repositories.document_repository import (
    SQLAlchemyDocumentRepository,
)
from src.infrastructure.db.repositories.error_event_repository import (
    SQLAlchemyErrorEventRepository,
)
from src.infrastructure.db.repositories.eval_dataset_repository import (
    SQLAlchemyEvalDatasetRepository,
)
from src.infrastructure.db.repositories.feedback_repository import (
    SQLAlchemyFeedbackRepository,
)
from src.infrastructure.db.repositories.guard_log_repository import (
    SQLAlchemyGuardLogRepository,
)
from src.infrastructure.db.repositories.guard_rules_config_repository import (
    SQLAlchemyGuardRulesConfigRepository,
)
from src.infrastructure.db.repositories.knowledge_base_repository import (
    SQLAlchemyKnowledgeBaseRepository,
)
from src.infrastructure.db.repositories.log_retention_policy_repository import (
    SQLAlchemyLogRetentionPolicyRepository,
)
from src.infrastructure.db.repositories.mcp_server_repository import (
    SQLAlchemyMcpServerRepository,
)
from src.infrastructure.db.repositories.memory_fact_repository import (
    SQLAlchemyMemoryFactRepository,
)
from src.infrastructure.db.repositories.notification_channel_repository import (
    SQLAlchemyNotificationChannelRepository,
)
from src.infrastructure.db.repositories.optimization_run_repository import (
    SQLAlchemyOptimizationRunRepository,
)
from src.infrastructure.db.repositories.plan_repository import (
    SQLAlchemyPlanRepository,
)
from src.infrastructure.db.repositories.processing_task_repository import (
    SQLAlchemyProcessingTaskRepository,
)
from src.infrastructure.pricing.pricing_cache import InMemoryPricingCache
from src.infrastructure.pricing.pricing_repository import (
    SQLAlchemyModelPricingRepository,
    SQLAlchemyPricingRecalcAuditRepository,
)
from src.infrastructure.pricing.usage_recalc_adapter import (
    SQLAlchemyUsageRecalcAdapter,
)
from src.infrastructure.db.repositories.provider_setting_repository import (
    SQLAlchemyProviderSettingRepository,
)
from src.infrastructure.db.repositories.quota_alert_log_repository import (
    SQLAlchemyQuotaAlertLogRepository,
)
from src.infrastructure.db.repositories.rate_limit_config_repository import (
    SQLAlchemyRateLimitConfigRepository,
)
from src.infrastructure.db.repositories.system_prompt_config_repository import (
    SQLAlchemySystemPromptConfigRepository,
)
from src.infrastructure.db.repositories.tenant_repository import (
    SQLAlchemyTenantRepository,
)
from src.infrastructure.db.repositories.token_ledger_repository import (
    SQLAlchemyTokenLedgerRepository,
)
from src.infrastructure.db.repositories.token_ledger_topup_repository import (
    SQLAlchemyTokenLedgerTopupRepository,
)
from src.infrastructure.db.repositories.usage_repository import (
    SQLAlchemyUsageRepository,
)
from src.infrastructure.db.repositories.user_repository import (
    SQLAlchemyUserRepository,
)
from src.infrastructure.db.repositories.visitor_profile_repository import (
    SQLAlchemyVisitorProfileRepository,
)
from src.infrastructure.db.repositories.worker_config_repository import (
    SQLAlchemyWorkerConfigRepository,
)
from src.infrastructure.db.session_middleware import get_tracked_session
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
from src.infrastructure.file_parser.ocr_engines.claude_vision_ocr import (
    ClaudeVisionOcrEngine,
)
from src.infrastructure.file_parser.ocr_file_parser_service import (
    OcrFileParserService,
)
from src.infrastructure.langgraph.dm_image_query_tool import (
    DmImageQueryTool,
)
from src.infrastructure.langgraph.meta_supervisor_service import (
    MetaSupervisorService,
)
from src.infrastructure.langgraph.react_agent_service import (
    ReActAgentService,
)
from src.infrastructure.langgraph.tools import RAGQueryTool
from src.infrastructure.langgraph.transfer_to_human_tool import (
    TransferToHumanTool,
)
from src.infrastructure.langgraph.workers.fake_main_worker import FakeMainWorker
from src.infrastructure.langgraph.workers.fake_refund_worker import FakeRefundWorker
from src.infrastructure.language_detection import (
    LangdetectLanguageDetectionService,
)
from src.infrastructure.line.line_messaging_service import HttpxLineMessagingService
from src.infrastructure.line.line_messaging_service_factory import (
    HttpxLineMessagingServiceFactory,
)
from src.infrastructure.llm.dynamic_llm_factory import (
    DynamicLLMServiceFactory,
    DynamicLLMServiceProxy,
)
from src.infrastructure.llm.fake_llm_service import FakeLLMService
from src.infrastructure.llm.ollama_warm_up import OllamaWarmUpService
from src.infrastructure.logging.db_error_reporter import DBErrorReporter
from src.infrastructure.mcp.cached_tool_loader import CachedMCPToolLoader
from src.infrastructure.memory.llm_memory_extraction_service import (
    LLMMemoryExtractionService,
)
from src.infrastructure.milvus.milvus_vector_store import MilvusVectorStore
from src.infrastructure.notification.email_sender import EmailNotificationSender
from src.infrastructure.notification.redis_throttle import RedisNotificationThrottle
from src.infrastructure.notification.sendgrid_quota_alert_sender import (
    SendGridQuotaAlertSender,
)
from src.infrastructure.prompt_optimizer.run_manager import RunManager
from src.infrastructure.storage.gcs_document_file_storage import (
    GCSDocumentFileStorageService,
)
from src.infrastructure.storage.local_document_file_storage import (
    LocalDocumentFileStorageService,
)
from src.infrastructure.storage.local_file_storage import LocalFileStorageService
from src.infrastructure.text_splitter.content_aware_text_splitter_service import (
    ContentAwareTextSplitterService,
)
from src.infrastructure.text_splitter.csv_row_text_splitter_service import (
    CSVRowTextSplitterService,
)
from src.infrastructure.text_splitter.json_record_text_splitter_service import (
    JsonRecordTextSplitterService,
)
from src.infrastructure.text_splitter.recursive_text_splitter_service import (
    RecursiveTextSplitterService,
)


class _AvgChunkSizeProvider:
    """Async callable to query avg chunk size from DB for a tenant."""

    def __init__(self, session):
        self._session = session

    async def __call__(self, tenant_id: str) -> int:
        from sqlalchemy import text

        result = await self._session.execute(
            text(
                "SELECT ROUND(AVG(LENGTH(content))) FROM chunks WHERE tenant_id = :tid"
            ),
            {"tid": tenant_id},
        )
        row = result.scalar()
        return int(row) if row else 500


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "src.interfaces.api.health_router",
            "src.interfaces.api.auth_router",
            "src.interfaces.api.tenant_router",
            "src.interfaces.api.knowledge_base_router",
            "src.interfaces.api.document_router",
            "src.interfaces.api.task_router",
            "src.interfaces.api.agent_router",
            "src.interfaces.api.conversation_router",
            "src.interfaces.api.feedback_router",
            "src.interfaces.api.line_webhook_router",
            "src.interfaces.api.usage_router",
            "src.interfaces.api.bot_router",
            "src.interfaces.api.worker_router",
            "src.interfaces.api.provider_setting_router",
            "src.interfaces.api.admin_router",
            "src.interfaces.api.admin_tools_router",
            "src.interfaces.api.admin_bot_router",
            "src.interfaces.api.admin_knowledge_base_router",
            "src.interfaces.api.admin_pricing_router",
            "src.interfaces.api.admin_chunk_router",
            "src.interfaces.api.admin_milvus_router",
            "src.interfaces.api.admin_conv_summary_router",
            "src.interfaces.api.admin_conversation_insights_router",
            "src.interfaces.api.plan_router",
            "src.interfaces.api.knowledge_base_router",
            "src.interfaces.api.mcp_router",
            "src.interfaces.api.mcp_server_router",
            "src.interfaces.api.observability_router",
            "src.interfaces.api.error_event_router",
            "src.interfaces.api.notification_router",
            "src.interfaces.api.system_prompt_router",
            "src.interfaces.api.security_router",
            "src.interfaces.api.widget_router",
            "src.interfaces.api.eval_dataset_router",
            "src.interfaces.api.prompt_optimizer_run_router",
            "src.interfaces.api.deps",
        ],
    )

    config = providers.Singleton(Settings)

    ollama_warm_up = providers.Singleton(
        OllamaWarmUpService,
        base_url=providers.Callable(lambda cfg: cfg.ollama_base_url, config),
    )

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

    conversation_lock = providers.Singleton(
        RedisConversationLock,
        redis_client=redis_client,
    )

    db_session = providers.Factory(get_tracked_session)
    trace_session_factory = providers.Object(_async_session_factory)

    jwt_service = providers.Singleton(
        JWTService,
        secret_key=providers.Callable(lambda cfg: cfg.jwt_secret_key, config),
        algorithm=providers.Callable(lambda cfg: cfg.jwt_algorithm, config),
        access_token_expire_minutes=providers.Callable(
            lambda cfg: cfg.jwt_access_token_expire_minutes, config
        ),
        refresh_token_expire_days=providers.Callable(
            lambda cfg: cfg.jwt_refresh_token_expire_days, config
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

    processing_task_repository = providers.Factory(
        SQLAlchemyProcessingTaskRepository,
        session=db_session,
    )

    chunk_category_repository = providers.Factory(
        SQLAlchemyChunkCategoryRepository,
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

    worker_config_repository = providers.Factory(
        SQLAlchemyWorkerConfigRepository,
        session=db_session,
    )

    list_workers_use_case = providers.Factory(
        ListWorkersUseCase,
        repo=worker_config_repository,
    )

    create_worker_use_case = providers.Factory(
        CreateWorkerUseCase,
        repo=worker_config_repository,
    )

    update_worker_use_case = providers.Factory(
        UpdateWorkerUseCase,
        repo=worker_config_repository,
    )

    delete_worker_use_case = providers.Factory(
        DeleteWorkerUseCase,
        repo=worker_config_repository,
    )

    user_repository = providers.Factory(
        SQLAlchemyUserRepository,
        session=db_session,
    )

    rate_limit_config_repository = providers.Factory(
        SQLAlchemyRateLimitConfigRepository,
        session=db_session,
    )

    plan_repository = providers.Factory(
        SQLAlchemyPlanRepository,
        session=db_session,
    )

    # S-Pricing.1: Model Pricing repos + in-memory cache
    model_pricing_repository = providers.Factory(
        SQLAlchemyModelPricingRepository,
        session=db_session,
    )

    pricing_recalc_audit_repository = providers.Factory(
        SQLAlchemyPricingRecalcAuditRepository,
        session=db_session,
    )

    usage_recalc_port = providers.Factory(
        SQLAlchemyUsageRecalcAdapter,
        session=db_session,
    )

    pricing_cache = providers.Singleton(
        InMemoryPricingCache,
        repo_factory=model_pricing_repository.provider,
    )

    token_ledger_repository = providers.Factory(
        SQLAlchemyTokenLedgerRepository,
        session=db_session,
    )

    # S-Ledger-Unification P1: append-only topups
    token_ledger_topup_repository = providers.Factory(
        SQLAlchemyTokenLedgerTopupRepository,
        session=db_session,
    )

    # S-Token-Gov.3: Billing + QuotaAlert repositories
    billing_transaction_repository = providers.Factory(
        SQLAlchemyBillingTransactionRepository,
        session=db_session,
    )

    quota_alert_log_repository = providers.Factory(
        SQLAlchemyQuotaAlertLogRepository,
        session=db_session,
    )

    provider_setting_repository = providers.Factory(
        SQLAlchemyProviderSettingRepository,
        session=db_session,
    )

    mcp_server_repository = providers.Factory(
        SQLAlchemyMcpServerRepository,
        session=db_session,
    )

    built_in_tool_repository = providers.Factory(
        SQLAlchemyBuiltInToolRepository,
        session=db_session,
    )

    system_prompt_config_repository = providers.Factory(
        SQLAlchemySystemPromptConfigRepository,
        session=db_session,
    )

    diagnostic_rules_config_repository = providers.Factory(
        SQLAlchemyDiagnosticRulesConfigRepository,
        session=db_session,
    )

    guard_rules_config_repository = providers.Factory(
        SQLAlchemyGuardRulesConfigRepository,
        session=db_session,
    )

    guard_log_repository = providers.Factory(
        SQLAlchemyGuardLogRepository,
        session=db_session,
    )

    log_retention_policy_repository = providers.Factory(
        SQLAlchemyLogRetentionPolicyRepository,
        session=db_session,
    )

    error_event_repository = providers.Factory(
        SQLAlchemyErrorEventRepository,
        session=db_session,
    )

    eval_dataset_repository = providers.Factory(
        SQLAlchemyEvalDatasetRepository,
        session=db_session,
    )

    notification_channel_repository = providers.Factory(
        SQLAlchemyNotificationChannelRepository,
        session=db_session,
    )

    notification_throttle_service = providers.Singleton(
        RedisNotificationThrottle,
        redis_client=redis_client,
    )

    encryption_service = providers.Singleton(
        AESEncryptionService,
        master_key=providers.Callable(
            lambda cfg: cfg.encryption_master_key
            or "0" * 64,  # fallback dev key (all zeros)
            config,
        ),
    )

    error_reporter = providers.Singleton(DBErrorReporter)

    file_storage_service = providers.Singleton(LocalFileStorageService)

    document_file_storage_service = providers.Selector(
        config.provided.storage_backend,
        local=providers.Singleton(
            LocalDocumentFileStorageService,
            base_dir=config.provided.local_storage_dir,
        ),
        gcs=providers.Singleton(
            GCSDocumentFileStorageService,
            bucket_name=config.provided.gcs_bucket_name,
        ),
    )

    _ocr_engine = providers.Singleton(
        ClaudeVisionOcrEngine,
        api_key=config.provided.anthropic_api_key,
        # Sonnet 4.6 OCR 準確度遠勝 Haiku（DM 裝飾字體 / 緊密小字差異明顯）
        # 成本：DM 每頁約 $0.005（vs Haiku $0.001），accuracy 換成本是值得的
        # 之前 Haiku 把「紫檀筷」OCR 成「茶槽杯」typical 形似字誤判
        # ⚠️ 待後續：應讓 ProcessDocumentUseCase 讀 KB.ocr_model 動態決定
        model="claude-sonnet-4-6",
    )

    file_parser_service = providers.Singleton(
        OcrFileParserService,
        ocr_engine=_ocr_engine,
    )

    language_detection_service = providers.Singleton(
        LangdetectLanguageDetectionService,
    )

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

    _json_splitter = providers.Singleton(
        JsonRecordTextSplitterService,
        chunk_size=providers.Callable(lambda cfg: cfg.chunk_size, config),
        fallback=_recursive_splitter,
    )

    text_splitter_service = providers.Selector(
        providers.Callable(lambda cfg: cfg.chunk_strategy, config),
        auto=providers.Singleton(
            ContentAwareTextSplitterService,
            strategies=providers.Dict({
                "text/csv": _csv_splitter,
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet": _csv_splitter,
                "application/vnd.ms-excel": _csv_splitter,
                "application/json": _json_splitter,
            }),
            default=_recursive_splitter,
        ),
        recursive=_recursive_splitter,
        csv_row=_csv_splitter,
        json_record=_json_splitter,
    )

    # Static fallback embedding (model/base_url/key all from .env)
    _real_embedding_service = providers.Factory(
        OpenAIEmbeddingService,
        api_key=providers.Callable(
            lambda cfg: cfg.effective_embedding_api_key, config
        ),
        model=providers.Callable(
            lambda cfg: cfg.effective_embedding_model, config
        ),
        base_url=providers.Callable(
            lambda cfg: cfg.effective_embedding_base_url, config
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
        openai=_real_embedding_service,
        google=_real_embedding_service,
    )

    _embedding_factory = providers.Singleton(
        DynamicEmbeddingServiceFactory,
        provider_setting_repo_factory=provider_setting_repository.provider,
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
        MilvusVectorStore,
        uri=config.provided.milvus_uri,
        token=config.provided.milvus_token,
        db_name=config.provided.milvus_db_name,
    )

    _static_llm_service = providers.Factory(FakeLLMService)

    _llm_factory = providers.Singleton(
        DynamicLLMServiceFactory,
        provider_setting_repo_factory=provider_setting_repository.provider,
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

    # Wire OCR engine's api_key_resolver to _llm_factory (lazy — defined after _ocr_engine)
    _ocr_engine.add_kwargs(
        api_key_resolver=providers.Callable(
            lambda factory: factory.resolve_api_key,
            _llm_factory,
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

    update_tenant_use_case = providers.Factory(
        UpdateTenantUseCase,
        tenant_repository=tenant_repository,
        plan_repository=plan_repository,
    )

    list_plans_use_case = providers.Factory(
        ListPlansUseCase,
        plan_repository=plan_repository,
    )

    get_plan_use_case = providers.Factory(
        GetPlanUseCase,
        plan_repository=plan_repository,
    )

    create_plan_use_case = providers.Factory(
        CreatePlanUseCase,
        plan_repository=plan_repository,
    )

    update_plan_use_case = providers.Factory(
        UpdatePlanUseCase,
        plan_repository=plan_repository,
    )

    delete_plan_use_case = providers.Factory(
        DeletePlanUseCase,
        plan_repository=plan_repository,
    )

    assign_plan_to_tenant_use_case = providers.Factory(
        AssignPlanToTenantUseCase,
        plan_repository=plan_repository,
        tenant_repository=tenant_repository,
    )

    # S-Pricing.1: Pricing use cases
    list_pricing_use_case = providers.Factory(
        ListPricingUseCase,
        repo=model_pricing_repository,
    )

    create_pricing_use_case = providers.Factory(
        CreatePricingUseCase,
        repo=model_pricing_repository,
    )

    deactivate_pricing_use_case = providers.Factory(
        DeactivatePricingUseCase,
        repo=model_pricing_repository,
    )

    dry_run_recalculate_use_case = providers.Factory(
        DryRunRecalculateUseCase,
        pricing_repo=model_pricing_repository,
        usage_port=usage_recalc_port,
        cache=cache_service,
    )

    execute_recalculate_use_case = providers.Factory(
        ExecuteRecalculateUseCase,
        pricing_repo=model_pricing_repository,
        audit_repo=pricing_recalc_audit_repository,
        usage_port=usage_recalc_port,
        cache=cache_service,
    )

    list_recalc_history_use_case = providers.Factory(
        ListRecalcHistoryUseCase,
        repo=pricing_recalc_audit_repository,
    )

    # --- S-KB-Studio.1 Use Cases ---

    update_chunk_use_case = providers.Factory(
        UpdateChunkUseCase,
        document_repo=document_repository,
        kb_repo=kb_repository,
    )

    delete_chunk_use_case = providers.Factory(
        DeleteChunkUseCase,
        document_repo=document_repository,
        kb_repo=kb_repository,
        vector_store=vector_store,
    )

    list_kb_chunks_use_case = providers.Factory(
        ListKbChunksUseCase,
        document_repo=document_repository,
        kb_repo=kb_repository,
    )

    test_retrieval_use_case = providers.Factory(
        TestRetrievalUseCase,
        kb_repo=kb_repository,
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    get_kb_quality_summary_use_case = providers.Factory(
        GetKbQualitySummaryUseCase,
        document_repo=document_repository,
        kb_repo=kb_repository,
    )

    create_category_use_case = providers.Factory(
        CreateCategoryUseCase,
        category_repo=chunk_category_repository,
        kb_repo=kb_repository,
    )

    delete_category_use_case = providers.Factory(
        DeleteCategoryUseCase,
        category_repo=chunk_category_repository,
        kb_repo=kb_repository,
    )

    assign_chunks_use_case = providers.Factory(
        AssignChunksUseCase,
        category_repo=chunk_category_repository,
        document_repo=document_repository,
        kb_repo=kb_repository,
    )

    list_milvus_collections_use_case = providers.Factory(
        ListMilvusCollectionsUseCase,
        vector_store=vector_store,
        kb_repo=kb_repository,
        tenant_repo=tenant_repository,
    )

    get_collection_stats_use_case = providers.Factory(
        GetCollectionStatsUseCase,
        vector_store=vector_store,
    )

    rebuild_index_use_case = providers.Factory(
        RebuildIndexUseCase,
        vector_store=vector_store,
    )

    list_conv_summaries_use_case = providers.Factory(
        ListConvSummariesUseCase,
        conv_repo=conversation_repository,
        bot_repo=bot_repository,
    )

    # S-ConvInsights.1: 對話與追蹤頁右側 tabs 用
    get_conversation_messages_use_case = providers.Factory(
        GetConversationMessagesUseCase,
        conversation_repo=conversation_repository,
    )

    get_conversation_token_usage_use_case = providers.Factory(
        GetConversationTokenUsageUseCase,
        conversation_repo=conversation_repository,
        session_factory=trace_session_factory,
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

    list_users_use_case = providers.Factory(
        ListUsersUseCase,
        user_repository=user_repository,
    )

    update_user_use_case = providers.Factory(
        UpdateUserUseCase,
        user_repository=user_repository,
    )

    delete_user_use_case = providers.Factory(
        DeleteUserUseCase,
        user_repository=user_repository,
    )

    reset_password_use_case = providers.Factory(
        ResetPasswordUseCase,
        user_repository=user_repository,
        password_service=password_service,
    )

    change_password_use_case = providers.Factory(
        ChangePasswordUseCase,
        user_repository=user_repository,
        password_service=password_service,
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

    update_knowledge_base_use_case = providers.Factory(
        UpdateKnowledgeBaseUseCase,
        knowledge_base_repository=kb_repository,
    )

    list_knowledge_bases_use_case = providers.Factory(
        ListKnowledgeBasesUseCase,
        knowledge_base_repository=kb_repository,
    )

    list_all_knowledge_bases_use_case = providers.Factory(
        ListAllKnowledgeBasesUseCase,
        knowledge_base_repository=kb_repository,
    )

    delete_knowledge_base_use_case = providers.Factory(
        DeleteKnowledgeBaseUseCase,
        knowledge_base_repository=kb_repository,
        document_repository=document_repository,
        vector_store=vector_store,
    )

    list_documents_use_case = providers.Factory(
        ListDocumentsUseCase,
        document_repository=document_repository,
    )

    delete_document_use_case = providers.Factory(
        DeleteDocumentUseCase,
        document_repository=document_repository,
        vector_store=vector_store,
        document_file_storage=document_file_storage_service,
    )

    upload_document_use_case = providers.Factory(
        UploadDocumentUseCase,
        knowledge_base_repository=kb_repository,
        document_repository=document_repository,
        processing_task_repository=processing_task_repository,
        document_file_storage=document_file_storage_service,
    )

    # S-Token-Gov.2 + Tier 1 T1.2: EnsureLedger 注入計算 carryover 需要的 repos。
    # 改 inline 算（不呼叫 ComputeTenantQuotaUseCase）避免 DI 循環依賴：
    #   ComputeQuota(cycle=None) → EnsureLedger → [若] ComputeQuota(cycle=last) → ...
    # 這邊 inline 計算，math 同 ComputeQuota 的 addon_remaining 公式，SSOT 一致。
    ensure_ledger_use_case = providers.Factory(
        EnsureLedgerUseCase,
        ledger_repository=token_ledger_repository,
        plan_repository=plan_repository,
        usage_repository=usage_repository,
        topup_repository=token_ledger_topup_repository,
        tenant_repository=tenant_repository,
    )

    # S-Ledger-Unification P3: 唯一 quota 讀取入口 — 需先於其他依賴它的 use case 定義
    compute_tenant_quota_use_case = providers.Factory(
        ComputeTenantQuotaUseCase,
        tenant_repository=tenant_repository,
        ensure_ledger=ensure_ledger_use_case,
        usage_repository=usage_repository,
        topup_repository=token_ledger_topup_repository,
    )

    # S-Ledger-Unification P4 + Tier 1 T1.1: topup_addon 寫 append-only log
    # + 注入 ledger_repository 以 fetch 真實 ledger.id 進 BillingTransaction（FK 合規）
    topup_addon_use_case = providers.Factory(
        TopupAddonUseCase,
        topup_repository=token_ledger_topup_repository,
        billing_transaction_repository=billing_transaction_repository,
        ledger_repository=token_ledger_repository,
    )

    process_quota_alerts_use_case = providers.Factory(
        ProcessQuotaAlertsUseCase,
        ledger_repository=token_ledger_repository,
        alert_repository=quota_alert_log_repository,
        compute_quota=compute_tenant_quota_use_case,
    )

    list_quota_events_use_case = providers.Factory(
        ListQuotaEventsUseCase,
        billing_transaction_repository=billing_transaction_repository,
        alert_repository=quota_alert_log_repository,
        tenant_repository=tenant_repository,
    )

    # S-Token-Gov.4: Billing dashboard
    get_billing_dashboard_use_case = providers.Factory(
        GetBillingDashboardUseCase,
        billing_transaction_repository=billing_transaction_repository,
        tenant_repository=tenant_repository,
    )

    # S-Token-Gov.3.5: Quota Alert Email
    quota_alert_email_sender = providers.Singleton(
        SendGridQuotaAlertSender,
        api_key=providers.Callable(
            lambda cfg: cfg.sendgrid_api_key, config
        ),
        from_email=providers.Callable(
            lambda cfg: cfg.quota_alert_from_email, config
        ),
        from_name=providers.Callable(
            lambda cfg: cfg.quota_alert_from_name, config
        ),
    )

    quota_email_dispatch_use_case = providers.Factory(
        QuotaEmailDispatchUseCase,
        alert_repository=quota_alert_log_repository,
        tenant_repository=tenant_repository,
        user_repository=user_repository,
        email_sender=quota_alert_email_sender,
        dashboard_url=providers.Callable(
            lambda cfg: cfg.quota_alert_dashboard_url, config
        ),
    )

    # S-Ledger-Unification P4: DeductTokensUseCase 已廢棄，將於 P7 刪除
    # 所有 quota 扣除改由 ComputeTenantQuotaUseCase 即時計算

    process_monthly_reset_use_case = providers.Factory(
        ProcessMonthlyResetUseCase,
        tenant_repository=tenant_repository,
        ledger_repository=token_ledger_repository,
        ensure_ledger=ensure_ledger_use_case,
    )

    get_tenant_quota_use_case = providers.Factory(
        GetTenantQuotaUseCase,
        tenant_repository=tenant_repository,
        ensure_ledger=ensure_ledger_use_case,
        usage_repository=usage_repository,
    )

    # S-Ledger-Unification P5: 切換底層到 ComputeTenantQuotaUseCase
    list_all_tenants_quotas_use_case = providers.Factory(
        ListAllTenantsQuotasUseCase,
        tenant_repository=tenant_repository,
        ledger_repository=token_ledger_repository,
        compute_quota=compute_tenant_quota_use_case,
    )

    record_usage_use_case = providers.Factory(
        RecordUsageUseCase,
        usage_repository=usage_repository,
        # S-Ledger-Unification P4: 不再 hook ledger.deduct，改為 auto-topup check
        compute_quota=compute_tenant_quota_use_case,
        topup_addon=topup_addon_use_case,
        tenant_repository=tenant_repository,
        plan_repository=plan_repository,
        # S-Pricing.1: cache miss 時才 fallback 到 DEFAULT_MODELS
        pricing_cache=pricing_cache,
    )

    # S-KB-Studio.1: re-embed 需要 record_usage 注入，故必須在 record_usage_use_case 之後
    reembed_chunk_use_case = providers.Factory(
        ReEmbedChunkUseCase,
        document_repo=document_repository,
        kb_repo=kb_repository,
        embedding_service=embedding_service,
        vector_store=vector_store,
        record_usage=record_usage_use_case,
    )

    chunk_context_service = providers.Factory(
        LLMChunkContextService,
        api_key_resolver=providers.Callable(
            lambda factory: factory.resolve_api_key,
            _llm_factory,
        ),
    )

    process_document_use_case = providers.Factory(
        ProcessDocumentUseCase,
        document_repository=document_repository,
        processing_task_repository=processing_task_repository,
        knowledge_base_repository=kb_repository,
        text_splitter_service=text_splitter_service,
        embedding_service=embedding_service,
        vector_store=vector_store,
        language_detection_service=language_detection_service,
        file_parser_service=file_parser_service,
        document_file_storage=document_file_storage_service,
        record_usage_use_case=record_usage_use_case,
        chunk_context_service=chunk_context_service,
        tenant_repository=tenant_repository,
    )

    split_pdf_use_case = providers.Factory(
        SplitPdfUseCase,
        document_repository=document_repository,
        knowledge_base_repository=kb_repository,
        processing_task_repository=processing_task_repository,
        document_file_storage=document_file_storage_service,
    )

    get_processing_task_use_case = providers.Factory(
        GetProcessingTaskUseCase,
        processing_task_repository=processing_task_repository,
    )

    get_document_chunks_use_case = providers.Factory(
        GetDocumentChunksUseCase,
        document_repository=document_repository,
    )

    reprocess_document_use_case = providers.Factory(
        ReprocessDocumentUseCase,
        document_repository=document_repository,
        processing_task_repository=processing_task_repository,
        knowledge_base_repository=kb_repository,
        text_splitter_service=text_splitter_service,
        embedding_service=embedding_service,
        vector_store=vector_store,
        language_detection_service=language_detection_service,
        file_parser_service=file_parser_service,
        document_file_storage=document_file_storage_service,
        # 與 process_document 對齊：reprocess 也記 PDF rename token + 用 context_service 拿 api_key
        record_usage_use_case=record_usage_use_case,
        tenant_repository=tenant_repository,
        chunk_context_service=chunk_context_service,
    )

    classification_service = providers.Factory(
        ClusterClassificationService,
        api_key_resolver=providers.Callable(
            lambda factory: factory.resolve_api_key,
            _llm_factory,
        ),
    )

    get_category_chunks_use_case = providers.Factory(
        GetCategoryChunksUseCase,
        category_repository=chunk_category_repository,
        document_repository=document_repository,
        vector_store=vector_store,
    )

    classify_kb_use_case = providers.Factory(
        ClassifyKbUseCase,
        knowledge_base_repository=kb_repository,
        document_repository=document_repository,
        category_repository=chunk_category_repository,
        vector_store=vector_store,
        classification_service=classification_service,
        record_usage=record_usage_use_case,
    )

    view_document_use_case = providers.Factory(
        ViewDocumentUseCase,
        document_repository=document_repository,
        document_file_storage=document_file_storage_service,
    )

    get_document_quality_stats_use_case = providers.Factory(
        GetDocumentQualityStatsUseCase,
        document_repository=document_repository,
        feedback_repository=feedback_repository,
    )

    query_rag_use_case = providers.Factory(
        QueryRAGUseCase,
        knowledge_base_repository=kb_repository,
        embedding_service=embedding_service,
        vector_store=vector_store,
        llm_service=llm_service,
        api_key_resolver=providers.Callable(
            lambda factory: factory.resolve_api_key,
            _llm_factory,
        ),
        record_usage=record_usage_use_case,
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

    # S-Gov.6b: Conversation Summary + Hybrid Search
    conversation_summary_service = providers.Factory(
        LLMConversationSummaryService,
        llm_service=llm_service,
        embedding_service=embedding_service,
    )

    generate_conversation_summary_use_case = providers.Factory(
        GenerateConversationSummaryUseCase,
        conversation_repository=conversation_repository,
        summary_service=conversation_summary_service,
        vector_store=vector_store,
        record_usage=record_usage_use_case,
    )

    search_conversations_use_case = providers.Factory(
        SearchConversationsUseCase,
        conversation_repository=conversation_repository,
        tenant_repository=tenant_repository,
        embedding_service=embedding_service,
        vector_store=vector_store,
        record_usage=record_usage_use_case,
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

    query_usage_use_case = providers.Factory(
        QueryUsageUseCase,
        usage_repository=usage_repository,
    )

    query_bot_usage_use_case = providers.Factory(
        QueryBotUsageUseCase,
        usage_repository=usage_repository,
    )

    query_daily_usage_use_case = providers.Factory(
        QueryDailyUsageUseCase,
        usage_repository=usage_repository,
    )

    query_monthly_usage_use_case = providers.Factory(
        QueryMonthlyUsageUseCase,
        usage_repository=usage_repository,
    )

    # --- Agent Tools ---

    rag_tool = providers.Factory(
        RAGQueryTool,
        query_rag_use_case=query_rag_use_case,
        top_k=config.provided.rag_top_k,
        score_threshold=config.provided.rag_score_threshold,
    )

    dm_image_query_tool = providers.Factory(
        DmImageQueryTool,
        query_rag_use_case=query_rag_use_case,
        document_repository=document_repository,
        file_storage=document_file_storage_service,
    )

    transfer_to_human_tool = providers.Factory(TransferToHumanTool)

    tool_registry = providers.Singleton(ToolRegistry)

    cached_tool_loader = providers.Singleton(CachedMCPToolLoader)

    # --- Agent Service ---

    customer_team = providers.Factory(
        TeamSupervisor,
        team_name="customer",
        workers=providers.List(
            providers.Factory(FakeRefundWorker),
            providers.Factory(FakeMainWorker),
        ),
    )

    agent_service = providers.Selector(
        providers.Callable(
            lambda cfg: "mock" if cfg.e2e_mode else "real",
            config,
        ),
        mock=providers.Factory(
            MetaSupervisorService,
            teams=providers.Dict(
                customer=customer_team,
            ),
        ),
        real=providers.Factory(
            ReActAgentService,
            llm_service=llm_service,
            rag_tool=rag_tool,
            tool_registry=tool_registry,
            cached_tool_loader=cached_tool_loader,
            dm_image_query_tool=dm_image_query_tool,
            transfer_to_human_tool=transfer_to_human_tool,
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
        encryption_service=encryption_service,
    )

    list_bots_use_case = providers.Factory(
        ListBotsUseCase,
        bot_repository=bot_repository,
    )

    list_all_bots_use_case = providers.Factory(
        ListAllBotsUseCase,
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
        encryption_service=encryption_service,
        ollama_warm_up=ollama_warm_up,
    )

    delete_bot_use_case = providers.Factory(
        DeleteBotUseCase,
        bot_repository=bot_repository,
        cache_service=cache_service,
    )

    upload_bot_icon_use_case = providers.Factory(
        UploadBotIconUseCase,
        bot_repository=bot_repository,
        file_storage_service=file_storage_service,
    )

    # --- Observability: RAG Evaluation ---

    rag_evaluation_use_case = providers.Factory(
        RAGEvaluationUseCase,
        llm_service=llm_service,
    )

    # --- Observability: Diagnostic Rules ---

    get_diagnostic_rules_use_case = providers.Factory(
        GetDiagnosticRulesUseCase,
        diagnostic_rules_config_repository=diagnostic_rules_config_repository,
    )

    update_diagnostic_rules_use_case = providers.Factory(
        UpdateDiagnosticRulesUseCase,
        diagnostic_rules_config_repository=diagnostic_rules_config_repository,
    )

    reset_diagnostic_rules_use_case = providers.Factory(
        ResetDiagnosticRulesUseCase,
        diagnostic_rules_config_repository=diagnostic_rules_config_repository,
    )

    # --- Security: Guard Rules ---

    prompt_guard_service = providers.Factory(
        PromptGuardService,
        guard_rules_repo=guard_rules_config_repository,
        guard_log_repo=guard_log_repository,
        record_usage=record_usage_use_case,
        api_key_resolver=providers.Callable(
            lambda factory: factory.resolve_api_key,
            _llm_factory,
        ),
    )

    get_guard_rules_use_case = providers.Factory(
        GetGuardRulesUseCase,
        repo=guard_rules_config_repository,
    )

    update_guard_rules_use_case = providers.Factory(
        UpdateGuardRulesUseCase,
        repo=guard_rules_config_repository,
    )

    reset_guard_rules_use_case = providers.Factory(
        ResetGuardRulesUseCase,
        repo=guard_rules_config_repository,
    )

    # --- Observability: Log Retention ---

    get_log_retention_policy_use_case = providers.Factory(
        GetLogRetentionPolicyUseCase,
        log_retention_policy_repository=log_retention_policy_repository,
    )

    update_log_retention_policy_use_case = providers.Factory(
        UpdateLogRetentionPolicyUseCase,
        log_retention_policy_repository=log_retention_policy_repository,
    )

    execute_log_cleanup_use_case = providers.Factory(
        ExecuteLogCleanupUseCase,
        log_retention_policy_repository=log_retention_policy_repository,
    )

    # --- Observability: Error Events ---

    report_error_use_case = providers.Factory(
        ReportErrorUseCase,
        error_event_repo=error_event_repository,
    )

    list_error_events_use_case = providers.Factory(
        ListErrorEventsUseCase,
        error_event_repo=error_event_repository,
    )

    get_error_event_use_case = providers.Factory(
        GetErrorEventUseCase,
        error_event_repo=error_event_repository,
    )

    resolve_error_event_use_case = providers.Factory(
        ResolveErrorEventUseCase,
        error_event_repo=error_event_repository,
    )

    # --- Observability: Notification Channels ---

    email_notification_sender = providers.Singleton(
        EmailNotificationSender,
    )

    notification_dispatcher = providers.Singleton(
        NotificationDispatcher,
        senders=providers.Dict({
            "email": email_notification_sender,
        }),
    )

    list_channels_use_case = providers.Factory(
        ListChannelsUseCase,
        channel_repo=notification_channel_repository,
    )

    create_channel_use_case = providers.Factory(
        CreateChannelUseCase,
        channel_repo=notification_channel_repository,
        encryption_service=encryption_service,
    )

    update_channel_use_case = providers.Factory(
        UpdateChannelUseCase,
        channel_repo=notification_channel_repository,
        encryption_service=encryption_service,
    )

    delete_channel_use_case = providers.Factory(
        DeleteChannelUseCase,
        channel_repo=notification_channel_repository,
    )

    test_channel_use_case = providers.Factory(
        SendTestNotificationUseCase,
        channel_repo=notification_channel_repository,
        encryption_service=encryption_service,
        dispatcher=notification_dispatcher,
    )

    dispatch_notification_use_case = providers.Factory(
        DispatchNotificationUseCase,
        channel_repo=notification_channel_repository,
        throttle_service=notification_throttle_service,
        dispatcher=notification_dispatcher,
    )

    # --- Eval Dataset (Prompt Optimizer) ---

    create_eval_dataset_use_case = providers.Factory(
        CreateEvalDatasetUseCase,
        eval_dataset_repository=eval_dataset_repository,
    )

    get_eval_dataset_use_case = providers.Factory(
        GetEvalDatasetUseCase,
        eval_dataset_repository=eval_dataset_repository,
    )

    list_eval_datasets_use_case = providers.Factory(
        ListEvalDatasetsUseCase,
        eval_dataset_repository=eval_dataset_repository,
    )

    update_eval_dataset_use_case = providers.Factory(
        UpdateEvalDatasetUseCase,
        eval_dataset_repository=eval_dataset_repository,
    )

    delete_eval_dataset_use_case = providers.Factory(
        DeleteEvalDatasetUseCase,
        eval_dataset_repository=eval_dataset_repository,
    )

    create_test_case_use_case = providers.Factory(
        CreateTestCaseUseCase,
        eval_dataset_repository=eval_dataset_repository,
    )

    delete_test_case_use_case = providers.Factory(
        DeleteTestCaseUseCase,
        eval_dataset_repository=eval_dataset_repository,
    )

    run_single_eval_use_case = providers.Factory(
        RunSingleEvalUseCase,
        eval_dataset_repository=eval_dataset_repository,
    )

    estimate_cost_use_case = providers.Factory(
        EstimateCostUseCase,
        eval_dataset_repository=eval_dataset_repository,
        bot_repository=bot_repository,
        system_prompt_config_repository=system_prompt_config_repository,
        get_avg_chunk_size=providers.Factory(
            _AvgChunkSizeProvider, session=db_session,
        ),
    )

    # --- Optimization Runs ---

    optimization_run_repository = providers.Factory(
        SQLAlchemyOptimizationRunRepository,
        session=db_session,
    )

    run_validation_eval_use_case = providers.Factory(
        RunValidationEvalUseCase,
        eval_dataset_repository=eval_dataset_repository,
        optimization_run_repository=optimization_run_repository,
    )

    run_manager = providers.Singleton(RunManager)

    start_run_use_case = providers.Factory(
        StartRunUseCase,
        eval_dataset_repository=eval_dataset_repository,
        run_manager=run_manager,
        db_url=providers.Callable(lambda cfg: cfg.database_url, config),
        provider_setting_repository=provider_setting_repository,
        encryption_service=encryption_service,
    )

    list_runs_use_case = providers.Factory(
        ListRunsUseCase,
        optimization_run_repository=optimization_run_repository,
        run_manager=run_manager,
    )

    get_run_use_case = providers.Factory(
        GetRunUseCase,
        optimization_run_repository=optimization_run_repository,
        run_manager=run_manager,
    )

    stop_run_use_case = providers.Factory(
        StopRunUseCase,
        run_manager=run_manager,
    )

    rollback_run_use_case = providers.Factory(
        RollbackRunUseCase,
        optimization_run_repository=optimization_run_repository,
        bot_repository=bot_repository,
        system_prompt_config_repository=system_prompt_config_repository,
    )

    get_run_report_use_case = providers.Factory(
        GetRunReportUseCase,
        optimization_run_repository=optimization_run_repository,
    )

    get_run_diff_use_case = providers.Factory(
        GetRunDiffUseCase,
        optimization_run_repository=optimization_run_repository,
    )

    # --- Memory ---

    visitor_profile_repository = providers.Factory(
        SQLAlchemyVisitorProfileRepository,
        session=db_session,
    )

    memory_fact_repository = providers.Factory(
        SQLAlchemyMemoryFactRepository,
        session=db_session,
    )

    memory_extraction_service = providers.Factory(
        LLMMemoryExtractionService,
        llm_service=llm_service,
    )

    resolve_identity_use_case = providers.Factory(
        ResolveIdentityUseCase,
        visitor_profile_repository=visitor_profile_repository,
    )

    load_memory_use_case = providers.Factory(
        LoadMemoryUseCase,
        memory_fact_repository=memory_fact_repository,
    )

    extract_memory_use_case = providers.Factory(
        ExtractMemoryUseCase,
        memory_fact_repository=memory_fact_repository,
        extraction_service=memory_extraction_service,
    )

    intent_classifier = providers.Factory(
        IntentClassifier,
        llm_service=llm_service,
        record_usage=record_usage_use_case,
    )

    send_message_use_case = providers.Factory(
        SendMessageUseCase,
        agent_service=agent_service,
        conversation_repository=conversation_repository,
        bot_repository=bot_repository,
        history_strategy=history_strategy,
        debug=providers.Callable(lambda cfg: cfg.debug, config),
        system_prompt_config_repository=system_prompt_config_repository,
        trace_session_factory=trace_session_factory,
        rag_evaluation_use_case=rag_evaluation_use_case,
        mcp_registry_repo=mcp_server_repository,
        encryption_service=encryption_service,
        resolve_identity_use_case=resolve_identity_use_case,
        load_memory_use_case=load_memory_use_case,
        extract_memory_use_case=extract_memory_use_case,
        get_diagnostic_rules_uc=get_diagnostic_rules_use_case,
        conversation_lock=conversation_lock,
        intent_classifier=intent_classifier,
        worker_config_repo=worker_config_repository,
        prompt_guard=prompt_guard_service,
        tenant_repository=tenant_repository,
    )

    # --- Platform: Provider Settings ---

    create_provider_setting_use_case = providers.Factory(
        CreateProviderSettingUseCase,
        provider_setting_repository=provider_setting_repository,
        encryption_service=encryption_service,
        cache_service=cache_service,
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

    list_enabled_models_use_case = providers.Factory(
        ListEnabledModelsUseCase,
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

    # --- Platform: MCP Server Registry ---

    create_mcp_server_use_case = providers.Factory(
        CreateMcpServerUseCase,
        mcp_server_repository=mcp_server_repository,
    )

    update_mcp_server_use_case = providers.Factory(
        UpdateMcpServerUseCase,
        mcp_server_repository=mcp_server_repository,
    )

    delete_mcp_server_use_case = providers.Factory(
        DeleteMcpServerUseCase,
        mcp_server_repository=mcp_server_repository,
    )

    discover_mcp_server_use_case = providers.Factory(
        DiscoverMcpServerUseCase,
        mcp_server_repository=mcp_server_repository,
    )

    test_mcp_connection_use_case = providers.Factory(
        TestMcpConnectionUseCase,
    )

    # --- Agent: Built-in Tool Scope Registry ---

    list_built_in_tools_use_case = providers.Factory(
        ListBuiltInToolsUseCase,
        repository=built_in_tool_repository,
    )

    update_built_in_tool_scope_use_case = providers.Factory(
        UpdateBuiltInToolScopeUseCase,
        repository=built_in_tool_repository,
    )

    # --- Platform: System Prompt Config ---

    get_system_prompts_use_case = providers.Factory(
        GetSystemPromptsUseCase,
        system_prompt_config_repository=system_prompt_config_repository,
    )

    update_system_prompts_use_case = providers.Factory(
        UpdateSystemPromptsUseCase,
        system_prompt_config_repository=system_prompt_config_repository,
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
        conversation_repository=conversation_repository,
        cache_service=cache_service,
        cache_ttl=providers.Callable(
            lambda cfg: cfg.cache_bot_ttl, config
        ),
        conversation_lock=conversation_lock,
        record_usage_use_case=record_usage_use_case,
        trace_session_factory=trace_session_factory,
        intent_classifier=intent_classifier,
        worker_config_repo=worker_config_repository,
    )
