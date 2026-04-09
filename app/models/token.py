from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TokenRaw(BaseModel):
    id: str
    name: str
    symbol: str
    creator_address: Optional[str] = None
    creator_name: Optional[str] = None
    price_usd: float = 0.0
    volume_24h: float = 0.0
    volume_7d: float = 0.0
    holder_count: int = 0
    holder_count_prev: int = 0
    market_cap: float = 0.0
    engagement_score: float = 0.0
    created_at: Optional[datetime] = None
    image_url: Optional[str] = None
    description: Optional[str] = None


class TokenScore(BaseModel):
    token_id: str
    name: str
    symbol: str
    creator_name: Optional[str] = None
    price_usd: float
    market_cap: float
    volume_24h: float
    holder_count: int

    # Computed scores
    volume_growth: float = Field(description="Normalized volume growth 0-1")
    holder_growth: float = Field(description="Normalized holder growth 0-1")
    engagement_score: float = Field(description="Normalized engagement 0-1")
    composite_score: float = Field(description="Final weighted score 0-100")

    # Classification
    tier: str = Field(description="S/A/B/C tier")
    hidden_gem: bool = Field(default=False, description="True if high score + low market cap")
    recommendation: str = Field(description="BUY/HOLD/WATCH/AVOID")


class TokenTrend(BaseModel):
    token_id: str
    name: str
    symbol: str
    price_usd: float
    volume_24h: float
    holder_count: int
    composite_score: float
    tier: str
    recommendation: str
    hidden_gem: bool


class TrendingResponse(BaseModel):
    tokens: list[TokenTrend]
    total: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    source: str = "bags_api"
