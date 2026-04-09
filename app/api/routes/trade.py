from fastapi import APIRouter, HTTPException, Query
from app.agents.trade_agent import TradeAgent
from app.models.trade import (
    QuoteRequest, QuoteResponse,
    SwapBuildRequest, SwapBuildResponse,
    FeeShareSetupRequest, FeeShareSetupResponse,
)

router = APIRouter()
_agent = TradeAgent()


def _require_api_key():
    if not _agent.has_api_key:
        raise HTTPException(
            status_code=503,
            detail="BAGS_API_KEY not configured — set it in environment variables.",
        )


# ─── Quote ────────────────────────────────────────────────────────────────


@router.get(
    "/trade/quote",
    summary="Get swap quote with platform fee",
    description="Returns a real-time swap quote from the Bags API. "
                "Pass the full response to /trade/build to construct the transaction.",
)
async def get_trade_quote(
    input_mint: str = Query(..., description="Input token mint address"),
    output_mint: str = Query(..., description="Output token mint address"),
    amount: int = Query(..., description="Amount in token's smallest unit"),
    slippage_bps: int = Query(None, description="Slippage in basis points (omit for auto)"),
):
    _require_api_key()
    quote = await _agent.get_quote(
        input_mint=input_mint,
        output_mint=output_mint,
        amount=amount,
        slippage_bps=slippage_bps,
    )
    if not quote:
        raise HTTPException(status_code=503, detail="Could not fetch quote from Bags API")
    return quote


# ─── Swap build ───────────────────────────────────────────────────────────


@router.post(
    "/trade/build",
    response_model=SwapBuildResponse,
    summary="Build unsigned swap transaction",
    description="Takes a quote response and user wallet, returns a base58 "
                "VersionedTransaction for the user's wallet to sign and broadcast. "
                "Platform fee is embedded by the Bags API.",
)
async def build_swap(body: SwapBuildRequest):
    _require_api_key()
    result = await _agent.build_swap(
        quote_response=body.quote_response,
        user_public_key=body.user_public_key,
    )
    if not result:
        raise HTTPException(status_code=503, detail="Swap build failed")
    return SwapBuildResponse(
        swap_transaction=result.get("swapTransaction", ""),
        compute_unit_limit=result.get("computeUnitLimit"),
        last_valid_block_height=result.get("lastValidBlockHeight"),
        prioritization_fee_lamports=result.get("prioritizationFeeLamports"),
    )


# ─── Fee-share config ─────────────────────────────────────────────────────


@router.post(
    "/trade/fee-share/setup",
    response_model=FeeShareSetupResponse,
    summary="Set up on-chain fee sharing for a token",
    description="Creates an on-chain fee-sharing configuration. "
                "Returns a base58 transaction the payer must sign and broadcast. "
                "basis_points must sum to 10000 (representing 100%).",
)
async def setup_fee_share(body: FeeShareSetupRequest):
    _require_api_key()
    result = await _agent.setup_fee_share(
        payer=body.payer,
        base_mint=body.base_mint,
        claimers=body.claimers,
        basis_points=body.basis_points,
        tip_wallet=body.tip_wallet,
        tip_lamports=body.tip_lamports,
    )
    if not result:
        raise HTTPException(status_code=503, detail="Fee-share setup failed")
    return FeeShareSetupResponse(
        transaction=result.get("transaction", ""),
        config_address=result.get("configAddress"),
    )


# ─── Status ───────────────────────────────────────────────────────────────


@router.get("/trade/status", summary="Check trade capabilities")
async def trade_status():
    return {
        "api_key_configured": _agent.has_api_key,
        "platform_fee_wallet": bool(_agent._fee_wallet),
        "fee_wallet_address": _agent._fee_wallet or "not set",
        "capabilities": {
            "quote": _agent.has_api_key,
            "swap_build": _agent.has_api_key,
            "fee_share_setup": _agent.has_api_key,
        },
    }
