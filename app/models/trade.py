from pydantic import BaseModel, field_validator
from typing import Optional


class QuoteRequest(BaseModel):
    input_mint: str
    output_mint: str
    amount: int                        # in token's smallest unit
    slippage_bps: Optional[int] = None # None = auto


class QuoteResponse(BaseModel):
    request_id: Optional[str] = None
    in_amount: str
    out_amount: str
    min_out_amount: Optional[str] = None
    price_impact_pct: float
    slippage_bps: Optional[int] = None
    platform_fee: Optional[dict] = None
    route_plan: Optional[list] = None


class SwapBuildRequest(BaseModel):
    quote_response: dict   # full quote object from /trade/quote
    user_public_key: str   # user's Solana wallet address


class SwapBuildResponse(BaseModel):
    swap_transaction: str          # base58 serialized VersionedTransaction
    compute_unit_limit: Optional[int] = None
    last_valid_block_height: Optional[int] = None
    prioritization_fee_lamports: Optional[int] = None


class FeeShareSetupRequest(BaseModel):
    payer: str              # wallet paying for setup tx
    base_mint: str          # token mint address
    claimers: list[str]     # wallet addresses to receive fees
    basis_points: list[int] # must sum to 10000
    tip_wallet: Optional[str] = None
    tip_lamports: Optional[int] = None

    @field_validator("basis_points")
    @classmethod
    def bps_must_sum_to_10000(cls, v: list[int]) -> list[int]:
        if sum(v) != 10000:
            raise ValueError(f"basis_points must sum to 10000, got {sum(v)}")
        return v


class FeeShareSetupResponse(BaseModel):
    transaction: str        # base58 serialized tx for user to sign
    config_address: Optional[str] = None
