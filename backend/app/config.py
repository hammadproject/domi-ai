from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = ""
    redis_url: str = ""
    rentcast_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    llm_model: str = "gemini-3.1-flash-lite"
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    llm_daily_call_limit: int = 200

    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: str = ""

    # Mortgage assumptions (estimates only, no live-rates API)
    default_interest_rate: float = 6.75  # percent
    property_tax_rate_default: float = 1.8  # percent of price per year
    home_insurance_annual_default: float = 1800.0
    pmi_rate_default: float = 0.7  # percent of loan per year

    rate_limit_per_minute: int = 30
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
