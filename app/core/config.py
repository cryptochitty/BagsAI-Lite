from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "BagsAI Lite"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # Bags API  (https://docs.bags.fm)
    BAGS_API_BASE_URL: str = "https://public-api-v2.bags.fm/api/v1"
    BAGS_API_KEY: Optional[str] = None          # x-api-key header — get from dev.bags.fm
    BAGS_API_TIMEOUT: int = 10
    BAGS_API_RETRIES: int = 3

    # Bitquery (supplements Bags API for trending/volume/holders)
    BITQUERY_API_KEY: Optional[str] = None      # https://bitquery.io

    # Comma-separated Solana mint addresses to track (fallback when no Bitquery)
    BAGS_TOKEN_MINTS: Optional[str] = None

    # Platform fee wallet — earns revenue from fee-sharing on trades
    PLATFORM_FEE_WALLET: Optional[str] = None

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Redis (optional)
    REDIS_URL: Optional[str] = None
    CACHE_TTL: int = 300  # seconds

    # Scoring weights
    VOLUME_WEIGHT: float = 0.4
    HOLDER_WEIGHT: float = 0.3
    ENGAGEMENT_WEIGHT: float = 0.3

    # Simulation defaults
    SIMULATION_INITIAL_CAPITAL: float = 10000.0
    SIMULATION_DAYS: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
