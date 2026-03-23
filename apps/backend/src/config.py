import json as _json

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "agentic_rag"
    database_url_override: str = ""  # e.g. postgresql+asyncpg://user:pass@host/db?ssl=require

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_url_override: str = ""  # e.g. rediss://default:xxx@xxx.upstash.io:6379

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_rest_port: int = 6333
    qdrant_grpc_port: int = 6334
    qdrant_api_key: str = ""
    qdrant_url: str = ""  # e.g. https://xxx.cloud.qdrant.io:6333

    # JWT
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Shared Provider API Keys (fallback when embedding/llm-specific keys are not set)
    openai_api_key: str = ""
    openai_chat_api_key: str = ""  # legacy alias for openai_api_key
    anthropic_api_key: str = ""
    qwen_api_key: str = ""
    google_api_key: str = ""
    deepseek_api_key: str = ""
    openrouter_api_key: str = ""

    # Embedding — "fake" | "openai" | "google"
    embedding_provider: str = "openai"
    embedding_api_key: str = ""
    embedding_model: str = ""
    embedding_base_url: str = ""
    embedding_vector_size: int = 1536
    embedding_batch_size: int = 50
    embedding_max_retries: int = 5
    embedding_timeout: float = 120.0
    embedding_batch_delay: float = 1.0
    embedding_retry_after_multiplier: float = 1.0
    embedding_min_batch_size: int = 10

    # LLM
    llm_max_tokens: int = 1024

    # E2E testing: E2E_MODE=true → FakeLLM + MetaSupervisor (no real LLM calls)
    e2e_mode: bool = False

    # Request Timeout (global ASGI middleware)
    request_timeout: int = 30  # 一般 API 請求超時（秒）
    stream_request_timeout: int = 180  # SSE streaming 請求超時（秒）

    # Agent Timeout
    agent_llm_request_timeout: int = 120  # 單次 LLM API 請求 HTTP 超時（秒）
    agent_stream_timeout: int = 180  # 整個 Agent 迴圈（含多次工具呼叫）總超時（秒）

    # Conversation History Strategy
    # "full" | "sliding_window" | "summary_recent" | "rag_history"
    history_strategy: str = "sliding_window"
    history_recent_turns: int = 3

    # RAG
    rag_score_threshold: float = 0.3
    rag_top_k: int = 5

    # Document Storage
    storage_backend: str = "local"  # "local" | "gcs"
    gcs_bucket_name: str = ""

    # Text Splitter
    chunk_size: int = 500
    chunk_overlap: int = 100
    chunk_strategy: str = "auto"  # "auto" | "recursive" | "csv_row"

    # LINE
    line_channel_secret: str = ""
    line_channel_access_token: str = ""
    line_default_tenant_id: str = ""
    line_default_kb_id: str = ""

    # LLM Pricing — deprecated: pricing is now DB-driven via ProviderSetting.models
    # Kept for backwards-compat; overridden by DB values when available.
    llm_pricing_json: str = "{}"

    # Encryption
    encryption_master_key: str = ""

    # Bcrypt
    bcrypt_rounds: int = 12

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_global_rpm: int = 1000
    rate_limit_config_cache_ttl: int = 60

    # Cache TTL (seconds)
    cache_bot_ttl: int = 120
    cache_feedback_stats_ttl: int = 60
    cache_summary_ttl: int = 3600
    cache_provider_config_ttl: int = 300

    # Data Retention
    data_retention_months: int = 6
    data_retention_enabled: bool = False

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:5174"  # comma-separated allowed origins

    # App
    app_env: str = "development"
    app_version: str = "0.1.0"

    # Multi-Deploy: comma-separated module list
    # "api" = REST API routers, "websocket" = WebSocket chat, "webhook" = LINE webhook
    enabled_modules: str = "api,websocket,webhook"

    # Logging
    log_level: str = "INFO"
    debug: bool = False

    # Trace logging: 0 = always log, >0 = only when request exceeds this ms
    trace_threshold_ms: int = 0

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_url_override:
            return self.redis_url_override
        return f"redis://{self.redis_host}:{self.redis_port}"

    @property
    def effective_openai_api_key(self) -> str:
        """Prefer openai_api_key; fall back to openai_chat_api_key."""
        return self.openai_api_key or self.openai_chat_api_key

    @property
    def effective_embedding_api_key(self) -> str:
        if self.embedding_api_key:
            return self.embedding_api_key
        if self.embedding_provider == "google":
            return self.google_api_key
        return self.effective_openai_api_key

    @property
    def effective_embedding_model(self) -> str:
        if self.embedding_model:
            return self.embedding_model
        _defaults = {"google": "text-embedding-004", "openai": "text-embedding-3-small"}
        return _defaults.get(self.embedding_provider, "text-embedding-3-small")

    @property
    def effective_embedding_base_url(self) -> str:
        if self.embedding_base_url:
            return self.embedding_base_url
        _defaults = {
            "google": "https://generativelanguage.googleapis.com/v1beta/openai",
            "openai": "https://api.openai.com/v1",
        }
        return _defaults.get(self.embedding_provider, "https://api.openai.com/v1")

    @property
    def enabled_modules_set(self) -> set[str]:
        """Parse enabled_modules CSV into a set."""
        return {m.strip() for m in self.enabled_modules.split(",") if m.strip()}

    @property
    def effective_log_level(self) -> str:
        """DEBUG=true forces DEBUG level; otherwise use LOG_LEVEL."""
        if self.debug:
            return "DEBUG"
        return self.log_level.upper()

    @property
    def llm_pricing(self) -> dict[str, dict[str, float]]:
        try:
            return _json.loads(self.llm_pricing_json)
        except (_json.JSONDecodeError, TypeError):
            return {}

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
