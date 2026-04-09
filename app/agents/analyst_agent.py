"""
AnalystAgent: scores and ranks creator tokens.
ML-ready structure for future extensibility.
"""
import logging
from typing import Optional

from app.agents.discovery_agent import DiscoveryAgent
from app.models.token import TokenScore, TokenRaw
from app.services.scoring_service import score_tokens
from app.services.cache_service import cache

logger = logging.getLogger(__name__)

CACHE_KEY_SCORES = "analyst:scores"
CACHE_KEY_GEMS = "analyst:gems"


class AnalystAgent:
    def __init__(self):
        self._discovery = DiscoveryAgent()

    async def analyze_trending(self, limit: int = 20) -> list[TokenScore]:
        cached = cache.get(CACHE_KEY_SCORES)
        if cached:
            logger.debug("Cache hit: token scores")
            return [TokenScore(**s) for s in cached]

        tokens = await self._discovery.fetch_trending(limit=limit)
        scores = score_tokens(tokens)

        cache.set(CACHE_KEY_SCORES, [s.model_dump() for s in scores])
        logger.info(f"Scored {len(scores)} tokens")
        return scores

    async def analyze_tokens(self, token_ids: list[str]) -> list[TokenScore]:
        tokens = await self._discovery.fetch_tokens_batch(token_ids)
        return score_tokens(tokens)

    async def find_hidden_gems(self, limit: int = 5) -> list[TokenScore]:
        cached = cache.get(CACHE_KEY_GEMS)
        if cached:
            return [TokenScore(**s) for s in cached]

        scores = await self.analyze_trending(limit=50)
        gems = [s for s in scores if s.hidden_gem][:limit]

        cache.set(CACHE_KEY_GEMS, [g.model_dump() for g in gems], ttl=180)
        logger.info(f"Found {len(gems)} hidden gems")
        return gems

    def get_top_n(self, scores: list[TokenScore], n: int = 5) -> list[TokenScore]:
        return sorted(scores, key=lambda s: s.composite_score, reverse=True)[:n]

    def get_by_tier(self, scores: list[TokenScore], tier: str) -> list[TokenScore]:
        return [s for s in scores if s.tier == tier]
