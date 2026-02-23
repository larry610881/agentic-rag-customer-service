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
    embedding_provider: str = "fake"  # "fake" or "openai"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_vector_size: int = 1536

    # LLM
    llm_provider: str = "fake"  # "fake", "anthropic", or "openai"
    anthropic_api_key: str = ""
    openai_chat_api_key: str = ""
    llm_model: str = ""
    llm_max_tokens: int = 1024

    # RAG
    rag_score_threshold: float = 0.3
    rag_top_k: int = 5

    # LINE
    line_channel_secret: str = ""
    line_channel_access_token: str = ""
    line_default_tenant_id: str = ""
    line_default_kb_id: str = ""

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
