from fastapi import APIRouter, Query
from typing import Optional
from app.agents.analyst_agent import AnalystAgent
from app.models.token import TokenScore

router = APIRouter()
_agent = AnalystAgent()


@router.get("/analyze", response_model=list[TokenScore], summary="Score and rank trending tokens")
async def analyze_trending(
    limit: int = Query(default=20, ge=1, le=100),
    tier: Optional[str] = Query(default=None, description="Filter by tier: S/A/B/C"),
):
    scores = await _agent.analyze_trending(limit=limit)
    if tier:
        scores = _agent.get_by_tier(scores, tier.upper())
    return scores


@router.post("/analyze", response_model=list[TokenScore], summary="Analyze specific tokens by ID")
async def analyze_tokens(token_ids: list[str]):
    return await _agent.analyze_tokens(token_ids)


@router.get("/analyze/gems", response_model=list[TokenScore], summary="Find hidden gem tokens")
async def find_gems(limit: int = Query(default=5, ge=1, le=20)):
    return await _agent.find_hidden_gems(limit=limit)
