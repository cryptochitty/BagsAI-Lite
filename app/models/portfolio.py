from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class PortfolioPosition(BaseModel):
    token_id: str
    symbol: str
    name: str
    allocation_pct: float = Field(ge=0, le=100)
    entry_price: float
    current_price: float
    quantity: float
    value_usd: float
    pnl_usd: float
    pnl_pct: float
    risk_tier: str  # LOW / MED / HIGH


class PortfolioState(BaseModel):
    total_value: float
    cash_usd: float
    invested_usd: float
    total_pnl: float
    total_pnl_pct: float
    positions: list[PortfolioPosition]
    risk_score: float = Field(description="0-10 portfolio risk score")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AllocationRequest(BaseModel):
    capital: float = Field(gt=0, description="Total capital in USD")
    token_ids: Optional[list[str]] = None
    strategy: str = Field(default="balanced", description="balanced/aggressive/conservative")
    max_positions: int = Field(default=5, ge=1, le=20)
