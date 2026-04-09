"""
PortfolioAgent: manages portfolio state and risk-balanced allocation.
"""
import logging
from datetime import datetime

from app.agents.analyst_agent import AnalystAgent
from app.models.token import TokenScore
from app.models.portfolio import PortfolioPosition, PortfolioState, AllocationRequest
from app.services.cache_service import cache
from app.utils.mock_data import get_mock_price_history

logger = logging.getLogger(__name__)

CACHE_KEY_PORTFOLIO = "portfolio:state"


def _risk_tier(score: float) -> str:
    if score >= 75:
        return "HIGH"
    if score >= 50:
        return "MED"
    return "LOW"


def _portfolio_risk_score(positions: list[PortfolioPosition]) -> float:
    """Weighted risk score 0-10."""
    if not positions:
        return 0.0
    weights = {"HIGH": 8.0, "MED": 5.0, "LOW": 2.0}
    total_alloc = sum(p.allocation_pct for p in positions)
    if not total_alloc:
        return 0.0
    weighted = sum(
        weights.get(p.risk_tier, 5.0) * (p.allocation_pct / total_alloc)
        for p in positions
    )
    return round(weighted, 2)


class PortfolioAgent:
    def __init__(self):
        self._analyst = AnalystAgent()

    async def build_portfolio(self, req: AllocationRequest) -> PortfolioState:
        if req.token_ids:
            scores = await self._analyst.analyze_tokens(req.token_ids)
        else:
            scores = await self._analyst.analyze_trending(limit=20)

        # Select top N by composite score
        top = sorted(scores, key=lambda s: s.composite_score, reverse=True)[:req.max_positions]

        positions = self._allocate(top, req.capital, req.strategy)
        state = PortfolioState(
            total_value=req.capital,
            cash_usd=0.0,
            invested_usd=req.capital,
            total_pnl=0.0,
            total_pnl_pct=0.0,
            positions=positions,
            risk_score=_portfolio_risk_score(positions),
        )
        cache.set(CACHE_KEY_PORTFOLIO, state.model_dump())
        return state

    def _allocate(
        self, scores: list[TokenScore], capital: float, strategy: str
    ) -> list[PortfolioPosition]:
        if not scores:
            return []

        total_score = sum(s.composite_score for s in scores) or 1

        positions = []
        for s in scores:
            if strategy == "equal_weight":
                alloc_pct = 100.0 / len(scores)
            elif strategy == "aggressive":
                alloc_pct = (s.composite_score / total_score) * 100
            elif strategy == "conservative":
                inv = 1.0 / max(s.composite_score, 1)
                inv_total = sum(1.0 / max(x.composite_score, 1) for x in scores)
                alloc_pct = (inv / inv_total) * 100
            else:  # balanced
                import math
                sqrt_total = sum(math.sqrt(x.composite_score) for x in scores) or 1
                alloc_pct = (math.sqrt(s.composite_score) / sqrt_total) * 100

            value = capital * (alloc_pct / 100)
            quantity = value / s.price_usd if s.price_usd else 0

            # Synthetic PnL: simulate slight mark-to-market variation
            import random
            price_now = s.price_usd * (1 + random.uniform(-0.05, 0.15))
            current_value = quantity * price_now
            pnl = current_value - value

            positions.append(PortfolioPosition(
                token_id=s.token_id,
                symbol=s.symbol,
                name=s.name,
                allocation_pct=round(alloc_pct, 2),
                entry_price=s.price_usd,
                current_price=round(price_now, 6),
                quantity=round(quantity, 2),
                value_usd=round(current_value, 2),
                pnl_usd=round(pnl, 2),
                pnl_pct=round((pnl / value) * 100, 2) if value else 0,
                risk_tier=_risk_tier(s.composite_score),
            ))

        return positions

    async def get_state(self) -> PortfolioState | None:
        cached = cache.get(CACHE_KEY_PORTFOLIO)
        if cached:
            return PortfolioState(**cached)
        return None
