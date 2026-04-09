from fastapi import APIRouter, Query, HTTPException
from app.agents.discovery_agent import DiscoveryAgent
from app.models.token import TrendingResponse, TokenTrend
from datetime import datetime, timezone

router = APIRouter()
_agent = DiscoveryAgent()


@router.get("/tokens", response_model=TrendingResponse, summary="Get trending creator tokens")
async def get_trending_tokens(limit: int = Query(default=20, ge=1, le=100)):
    tokens = await _agent.fetch_trending(limit=limit)
    is_live = any(len(t.id) >= 32 for t in tokens)
    trends = [
        TokenTrend(
            token_id=t.id,
            name=t.name,
            symbol=t.symbol,
            price_usd=t.price_usd,
            volume_24h=t.volume_24h,
            holder_count=t.holder_count,
            composite_score=0.0,
            tier="N/A",
            recommendation="N/A",
            hidden_gem=False,
        )
        for t in tokens
    ]
    return TrendingResponse(
        tokens=trends,
        total=len(trends),
        generated_at=datetime.now(timezone.utc),
        source="live" if is_live else "mock",
    )


@router.get("/tokens/ping", summary="Check Bags API connectivity")
async def ping_bags_api():
    healthy = await _agent.ping()
    return {
        "bags_api": "reachable" if healthy else "unreachable",
        "base_url": _agent._base_url,
        "authenticated": bool(_agent._api_key),
        "bitquery": bool(_agent._bitquery_key),
    }


@router.get("/tokens/{token_id}", summary="Get a single token by ID or mint address")
async def get_token(token_id: str):
    token = await _agent.fetch_token(token_id)
    if not token:
        raise HTTPException(status_code=404, detail=f"Token {token_id} not found")
    return token


@router.get("/tokens/{mint}/creators", summary="Get creator info for a token mint")
async def get_token_creators(mint: str):
    """Calls Bags API GET /token-launch/creator/v3 directly."""
    data = await _agent.fetch_token_creators(mint)
    if data is None:
        raise HTTPException(status_code=503, detail="Bags API unavailable or key missing")
    return {"mint": mint, "creators": data}


@router.get("/tokens/{mint}/fees", summary="Get lifetime fees for a token mint")
async def get_token_fees(mint: str):
    """Calls Bags API GET /token-launch/lifetime-fees directly."""
    fees_sol = await _agent.fetch_lifetime_fees(mint)
    if fees_sol is None:
        raise HTTPException(status_code=503, detail="Bags API unavailable or key missing")
    return {"mint": mint, "lifetime_fees_sol": fees_sol}


@router.get("/tokens/{mint}/price", summary="Get real-time price via Bags trade quote")
async def get_token_price(mint: str, amount: int = Query(default=1_000_000, description="Amount in token units")):
    """Calls Bags API GET /trade/quote to get real-time price."""
    price_sol = await _agent.fetch_price_quote(mint, amount=amount)
    if price_sol is None:
        raise HTTPException(status_code=503, detail="Price quote unavailable")
    return {"mint": mint, "price_sol": price_sol, "amount": amount}
