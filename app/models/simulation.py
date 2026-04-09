from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SimulationRequest(BaseModel):
    token_ids: list[str] = Field(min_length=1)
    initial_capital: float = Field(default=10000.0, gt=0)
    days: int = Field(default=30, ge=1, le=365)
    strategy: str = Field(default="balanced", description="balanced/aggressive/conservative/equal_weight")
    rebalance_frequency: int = Field(default=7, description="Rebalance every N days")


class DailySnapshot(BaseModel):
    day: int
    date: str
    portfolio_value: float
    daily_return_pct: float
    positions: dict[str, float]  # token_id -> value


class SimulationResult(BaseModel):
    strategy: str
    initial_capital: float
    final_value: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    best_day_pct: float
    worst_day_pct: float
    win_rate: float
    days: list[DailySnapshot]
    top_performer: Optional[str] = None
    worst_performer: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ExplainRequest(BaseModel):
    token_id: str
    language: str = Field(default="en", description="en or ta (Tamil)")
    context: Optional[str] = None


class ExplainResponse(BaseModel):
    token_id: str
    token_name: str
    language: str
    summary: str
    risks: list[str]
    recommendation: str
    confidence: float = Field(ge=0, le=1)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(BaseModel):
    role: str = Field(description="user or assistant")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    token_context: Optional[str] = None
