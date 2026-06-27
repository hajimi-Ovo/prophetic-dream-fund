"""
Application configuration using pydantic-settings.

All settings can be overridden via environment variables.
"""


from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database — defaults to PostgreSQL for Docker / production.
    # Override with DATABASE_URL=sqlite+aiosqlite:///./fund_app.db for local dev.
    DATABASE_URL: str = "postgresql+asyncpg://fund:fund123@localhost:5432/fund_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Application
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_DEBUG: bool = False

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:80",
    ]


# Singleton settings instance
settings = Settings()
