"""
SimulationAgent: runs investment simulations over historical/synthetic price data.
"""
import logging
import math
import random
from datetime import datetime, timedelta
from typing import Sequence

from app.agents.discovery_agent import DiscoveryAgent
from app.agents.analyst_agent import AnalystAgent
from app.models.simulation import SimulationRequest, SimulationResult, DailySnapshot
from app.utils.mock_data import get_mock_price_history

logger = logging.getLogger(__name__)


def _allocations(
    token_ids: list[str],
    scores: dict[str, float],
    strategy: str,
) -> dict[str, float]:
    """Return allocation percentages that sum to 1.0."""
    if strategy == "equal_weight":
        w = 1.0 / len(token_ids)
        return {tid: w for tid in token_ids}

    if strategy == "aggressive":
        # Overweight top performer
        total_score = sum(scores.values()) or 1
        return {tid: (scores.get(tid, 0) / total_score) for tid in token_ids}

    if strategy == "conservative":
        # Inverse-score weighting (prefer lower volatility / lower score)
        inv = {tid: 1.0 / max(scores.get(tid, 1), 1) for tid in token_ids}
        total = sum(inv.values()) or 1
        return {tid: inv[tid] / total for tid in token_ids}

    # balanced: square-root of scores to reduce concentration
    sqrt_scores = {tid: math.sqrt(max(scores.get(tid, 0), 0.01)) for tid in token_ids}
    total = sum(sqrt_scores.values()) or 1
    return {tid: sqrt_scores[tid] / total for tid in token_ids}


class SimulationAgent:
    def __init__(self):
        self._discovery = DiscoveryAgent()
        self._analyst = AnalystAgent()

    async def run(self, req: SimulationRequest) -> SimulationResult:
        # Fetch scores for allocation weights
        scored = await self._analyst.analyze_tokens(req.token_ids)
        score_map = {s.token_id: s.composite_score for s in scored}

        allocs = _allocations(req.token_ids, score_map, req.strategy)
        logger.info(f"Running {req.strategy} simulation over {req.days} days with {len(req.token_ids)} tokens")

        # Build price histories per token
        price_histories: dict[str, list[float]] = {}
        for tid in req.token_ids:
            price_histories[tid] = get_mock_price_history(tid, req.days)

        # Initial portfolio
        portfolio_values: list[float] = []
        daily_snaps: list[DailySnapshot] = []
        portfolio_value = req.initial_capital

        position_values: dict[str, float] = {
            tid: portfolio_value * allocs.get(tid, 0) for tid in req.token_ids
        }

        for day in range(req.days):
            date_str = (datetime.utcnow() - timedelta(days=req.days - day)).strftime("%Y-%m-%d")
            new_values: dict[str, float] = {}

            for tid in req.token_ids:
                prices = price_histories[tid]
                if day == 0:
                    new_values[tid] = position_values[tid]
                else:
                    prev_price = prices[day - 1]
                    curr_price = prices[day]
                    growth = (curr_price / prev_price) if prev_price > 0 else 1.0
                    new_values[tid] = position_values[tid] * growth

            # Rebalance
            if day > 0 and day % req.rebalance_frequency == 0:
                total = sum(new_values.values())
                new_values = {tid: total * allocs.get(tid, 0) for tid in req.token_ids}

            total_val = sum(new_values.values())
            daily_return = (total_val / portfolio_value - 1) * 100 if portfolio_value else 0

            daily_snaps.append(DailySnapshot(
                day=day,
                date=date_str,
                portfolio_value=round(total_val, 2),
                daily_return_pct=round(daily_return, 4),
                positions={tid: round(v, 2) for tid, v in new_values.items()},
            ))

            portfolio_value = total_val
            position_values = new_values
            portfolio_values.append(total_val)

        final_value = portfolio_values[-1]
        total_return_pct = (final_value / req.initial_capital - 1) * 100

        # Max drawdown
        peak = portfolio_values[0]
        max_dd = 0.0
        for v in portfolio_values:
            peak = max(peak, v)
            dd = (peak - v) / peak * 100
            max_dd = max(max_dd, dd)

        # Daily returns for Sharpe
        daily_rets = [
            (portfolio_values[i] / portfolio_values[i - 1] - 1)
            for i in range(1, len(portfolio_values))
        ]
        avg_ret = sum(daily_rets) / len(daily_rets) if daily_rets else 0
        std_ret = math.sqrt(sum((r - avg_ret) ** 2 for r in daily_rets) / len(daily_rets)) if len(daily_rets) > 1 else 0.001
        sharpe = (avg_ret / std_ret) * math.sqrt(252) if std_ret else 0

        best_day = max(daily_rets, default=0) * 100
        worst_day = min(daily_rets, default=0) * 100
        win_rate = sum(1 for r in daily_rets if r > 0) / len(daily_rets) if daily_rets else 0

        # Per-token performance
        token_perf = {
            tid: price_histories[tid][-1] / price_histories[tid][0] - 1
            for tid in req.token_ids
            if price_histories[tid][0] > 0
        }
        top = max(token_perf, key=token_perf.get) if token_perf else None
        worst = min(token_perf, key=token_perf.get) if token_perf else None

        return SimulationResult(
            strategy=req.strategy,
            initial_capital=req.initial_capital,
            final_value=round(final_value, 2),
            total_return_pct=round(total_return_pct, 2),
            max_drawdown_pct=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 3),
            best_day_pct=round(best_day, 2),
            worst_day_pct=round(worst_day, 2),
            win_rate=round(win_rate, 3),
            days=daily_snaps,
            top_performer=top,
            worst_performer=worst,
        )
