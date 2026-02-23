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

    # Embedding
    embedding_provider: str = "fake"  # "fake" | "openai" | "qwen"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_vector_size: int = 1536
    embedding_base_url: str = ""

    # LLM
    # "fake" | "openai" | "anthropic" | "qwen" | "openrouter"
    llm_provider: str = "fake"
    anthropic_api_key: str = ""
    openai_chat_api_key: str = ""
    qwen_api_key: str = ""
    openrouter_api_key: str = ""
    llm_model: str = ""
    llm_max_tokens: int = 1024
    llm_base_url: str = ""

    # RAG
    rag_score_threshold: float = 0.3
    rag_top_k: int = 5

    # LINE
    line_channel_secret: str = ""
    line_channel_access_token: str = ""
    line_default_tenant_id: str = ""
    line_default_kb_id: str = ""

    # LLM Pricing (JSON: {"model": {"input": price_per_1m, "output": price_per_1m}})
    llm_pricing_json: str = "{}"

    # App
    app_env: str = "development"
    app_version: str = "0.1.0"

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
    def llm_pricing(self) -> dict[str, dict[str, float]]:
        try:
            return _json.loads(self.llm_pricing_json)
        except (_json.JSONDecodeError, TypeError):
            return {}

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
