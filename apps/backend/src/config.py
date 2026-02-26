import json as _json

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "agentic_rag"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_rest_port: int = 6333
    qdrant_grpc_port: int = 6334

    # JWT
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # Shared Provider API Keys (fallback when embedding/llm-specific keys are not set)
    openai_api_key: str = ""
    openai_chat_api_key: str = ""  # legacy alias for openai_api_key
    anthropic_api_key: str = ""
    qwen_api_key: str = ""
    google_api_key: str = ""
    openrouter_api_key: str = ""

    # Embedding (independent from LLM)
    embedding_provider: str = "fake"  # "fake" | "openai" | "qwen" | "google"
    embedding_api_key: str = ""  # dedicated key; falls back to provider key
    embedding_model: str = "text-embedding-3-small"
    embedding_vector_size: int = 1536
    embedding_base_url: str = ""
    embedding_batch_size: int = 50
    embedding_max_retries: int = 5
    embedding_timeout: float = 120.0
    # seconds between batches (rate limit protection)
    embedding_batch_delay: float = 1.0

    # LLM (independent from Embedding)
    # "fake" | "openai" | "anthropic" | "qwen" | "google" | "openrouter"
    llm_provider: str = "fake"
    llm_api_key: str = ""  # dedicated key; falls back to provider key
    llm_model: str = ""
    llm_max_tokens: int = 1024
    llm_base_url: str = ""

    # Conversation History Strategy
    # "full" | "sliding_window" | "summary_recent" | "rag_history"
    history_strategy: str = "sliding_window"
    history_recent_turns: int = 3

    # RAG
    rag_score_threshold: float = 0.3
    rag_top_k: int = 5

    # Text Splitter
    chunk_size: int = 500
    chunk_overlap: int = 100
    chunk_strategy: str = "auto"  # "auto" | "recursive" | "csv_row"

    # LINE
    line_channel_secret: str = ""
    line_channel_access_token: str = ""
    line_default_tenant_id: str = ""
    line_default_kb_id: str = ""

    # LLM Pricing (JSON: {"model": {"input": price_per_1m, "output": price_per_1m}})
    llm_pricing_json: str = "{}"

    # Encryption
    encryption_master_key: str = ""

    # Cache TTL (seconds)
    cache_bot_ttl: int = 120
    cache_feedback_stats_ttl: int = 60
    cache_summary_ttl: int = 3600
    cache_provider_config_ttl: int = 300

    # Data Retention
    data_retention_months: int = 6
    data_retention_enabled: bool = False

    # App
    app_env: str = "development"
    app_version: str = "0.1.0"

    # Multi-Deploy: comma-separated module list
    # "api" = REST API routers, "websocket" = WebSocket chat, "webhook" = LINE webhook
    enabled_modules: str = "api,websocket,webhook"

    # Logging
    log_level: str = "INFO"
    debug: bool = False

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}"

    @property
    def effective_openai_api_key(self) -> str:
        """Prefer openai_api_key; fall back to openai_chat_api_key."""
        return self.openai_api_key or self.openai_chat_api_key

    @property
    def effective_embedding_api_key(self) -> str:
        """Resolve embedding API key: dedicated > provider-specific > legacy."""
        if self.embedding_api_key:
            return self.embedding_api_key
        if self.embedding_provider == "qwen":
            return self.qwen_api_key
        if self.embedding_provider == "google":
            return self.google_api_key
        if self.embedding_provider == "openai":
            return self.effective_openai_api_key
        return ""

    @property
    def effective_llm_api_key(self) -> str:
        """Resolve LLM API key: dedicated > provider-specific > legacy."""
        if self.llm_api_key:
            return self.llm_api_key
        if self.llm_provider == "qwen":
            return self.qwen_api_key
        if self.llm_provider == "google":
            return self.google_api_key
        if self.llm_provider == "openai":
            return self.effective_openai_api_key
        if self.llm_provider == "anthropic":
            return self.anthropic_api_key
        if self.llm_provider == "openrouter":
            return self.openrouter_api_key
        return ""

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
