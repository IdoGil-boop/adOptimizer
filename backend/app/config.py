"""Application configuration and settings."""

from functools import lru_cache
from typing import List, Union

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
        env_parse_none_str="null"
    )

    # Environment
    ENVIRONMENT: str = Field(default="development")

    # Database
    DATABASE_URL: PostgresDsn = Field(
        default="postgresql://adsoptimizer:dev_password_change_in_prod@localhost:5432/adsoptimizer"
    )

    # Redis
    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379/0")

    # Google Ads API
    GOOGLE_ADS_DEVELOPER_TOKEN: str = Field(default="")
    GOOGLE_ADS_CLIENT_ID: str = Field(default="")
    GOOGLE_ADS_CLIENT_SECRET: str = Field(default="")
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: str = Field(default="")

    # OAuth2 & Security
    TOKEN_ENCRYPTION_KEY: str = Field(default="")
    SECRET_KEY: str = Field(default="")
    OAUTH_REDIRECT_URI: str = Field(default="http://localhost:8000/oauth/google-ads/callback")

    # OpenAI
    OPENAI_API_KEY: str = Field(default="")

    # Feature Flags
    FEATURE_FLAG_APPLY_SUGGESTIONS: bool = Field(default=False)

    # CORS (stored as comma-separated string in .env)
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8000"
    )

    # Scoring Thresholds
    MIN_IMPRESSIONS_FOR_SCORING: int = Field(default=100)
    MIN_CLICKS_FOR_SCORING: int = Field(default=10)

    # Sync Schedule
    SYNC_SCHEDULE_HOUR: int = Field(default=2)
    SYNC_SCHEDULE_MINUTE: int = Field(default=0)

    # Google Ads OAuth Scopes
    GOOGLE_ADS_OAUTH_SCOPE: str = "https://www.googleapis.com/auth/adwords"

    @property
    def database_url_str(self) -> str:
        """Get database URL as string."""
        return str(self.DATABASE_URL)

    @property
    def redis_url_str(self) -> str:
        """Get Redis URL as string."""
        return str(self.REDIS_URL)

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT == "production"

    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
