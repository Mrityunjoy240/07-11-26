from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "BCREC AI"
    debug: bool = True

    # --- Infrastructure ---
    redis_url: str = "redis://localhost:6379/0"
    redis_session_ttl: int = 1800

    postgres_dsn: str = "postgresql+asyncpg://bcrec:bcrec_dev@localhost:5432/bcrec"
    postgres_pool_size: int = 10
    postgres_max_overflow: int = 20

    sqlite_path: str = "data/conversations.db"

    # --- Observability ---
    otel_service_name: str = "bcrec-ai"
    otel_endpoint: str | None = None

    # --- Pipeline ---
    pipeline_mode: str = "legacy"  # "legacy" | "shadow" | "new"
    pipeline_version: str = "1.0.0"

    # --- LLM ---
    groq_api_key: str = ""

    # --- Feature Flags (all default OFF) ---
    use_redis_sessions: bool = False
    use_postgres_history: bool = False
    use_otel: bool = False


settings = Settings()
