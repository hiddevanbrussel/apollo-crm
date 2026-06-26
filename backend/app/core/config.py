from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+psycopg://apollo:apollo@localhost:5432/apollo_crm"

    # Auth / JWT
    JWT_SECRET: str = "change_me_super_secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # Encryption (Fernet key). When empty a key is derived from JWT_SECRET.
    ENCRYPTION_KEY: str = ""

    # Apollo
    APOLLO_BASE_URL: str = "https://api.apollo.io"
    # Public URL of this CRM (e.g. https://ai.xential.nl). Required for Apollo waterfall webhooks.
    PUBLIC_BASE_URL: str = ""
    # Optional secret token in Apollo webhook URLs. When empty, derived from JWT_SECRET.
    APOLLO_WEBHOOK_SECRET: str = ""
    # Waterfall enrichment queries third-party sources and may share data with Apollo. Off by default.
    APOLLO_WATERFALL_ENABLED: bool = False

    # Prospeo
    PROSPEO_BASE_URL: str = "https://api.prospeo.io"

    # CORS (comma separated string in env; use the cors_origins property for a list)
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8080"

    # Seed
    SEED_ON_START: bool = True
    ADMIN_EMAIL: str = "admin@apollo-crm.com"
    ADMIN_PASSWORD: str = "admin123"
    ADMIN_NAME: str = "Administrator"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
