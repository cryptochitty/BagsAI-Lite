"""
Scoring service: normalized composite score for creator tokens.

score = volume_growth * 0.4 + holder_growth * 0.3 + engagement_score * 0.3
"""
from typing import Sequence
from app.models.token import TokenRaw, TokenScore
from app.core.config import settings


def _normalize(values: list[float]) -> list[float]:
    """Min-max normalize to [0, 1]."""
    if not values:
        return values
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _volume_growth(token: TokenRaw) -> float:
    """7d vs 24h * 7 as proxy for growth direction."""
    weekly_run_rate = token.volume_24h * 7
    if token.volume_7d == 0:
        return 0.0
    return weekly_run_rate / token.volume_7d  # > 1 means accelerating


def _holder_growth(token: TokenRaw) -> float:
    if token.holder_count_prev == 0:
        return 0.0
    return (token.holder_count - token.holder_count_prev) / token.holder_count_prev


def _tier(score: float) -> str:
    if score >= 80:
        return "S"
    if score >= 65:
        return "A"
    if score >= 45:
        return "B"
    return "C"


def _recommendation(score: float, hidden_gem: bool) -> str:
    if hidden_gem:
        return "BUY"
    if score >= 75:
        return "BUY"
    if score >= 55:
        return "HOLD"
    if score >= 35:
        return "WATCH"
    return "AVOID"


def score_tokens(tokens: Sequence[TokenRaw]) -> list[TokenScore]:
    if not tokens:
        return []

    raw_vol = [_volume_growth(t) for t in tokens]
    raw_hold = [_holder_growth(t) for t in tokens]
    raw_eng = [t.engagement_score for t in tokens]
    raw_mcap = [t.market_cap for t in tokens]

    norm_vol = _normalize(raw_vol)
    norm_hold = _normalize(raw_hold)
    norm_eng = _normalize(raw_eng)
    norm_mcap = _normalize(raw_mcap)

    w = settings
    scored = []
    for i, token in enumerate(tokens):
        composite = (
            norm_vol[i] * w.VOLUME_WEIGHT
            + norm_hold[i] * w.HOLDER_WEIGHT
            + norm_eng[i] * w.ENGAGEMENT_WEIGHT
        ) * 100

        # Hidden gem: high score but low market cap (bottom 30%)
        mcap_threshold = sorted(raw_mcap)[int(len(raw_mcap) * 0.3)]
        hidden_gem = composite >= 55 and token.market_cap <= mcap_threshold

        scored.append(TokenScore(
            token_id=token.id,
            name=token.name,
            symbol=token.symbol,
            creator_name=token.creator_name,
            price_usd=token.price_usd,
            market_cap=token.market_cap,
            volume_24h=token.volume_24h,
            holder_count=token.holder_count,
            volume_growth=round(norm_vol[i], 4),
            holder_growth=round(norm_hold[i], 4),
            engagement_score=round(norm_eng[i], 4),
            composite_score=round(composite, 2),
            tier=_tier(composite),
            hidden_gem=hidden_gem,
            recommendation=_recommendation(composite, hidden_gem),
        ))

    return sorted(scored, key=lambda s: s.composite_score, reverse=True)
