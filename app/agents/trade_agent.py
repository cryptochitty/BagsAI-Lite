"""
TradeAgent: wraps Bags API trade and fee-share endpoints.

Endpoints used:
  GET  /trade/quote          — get swap quote with platform fee
  POST /trade/swap           — build unsigned VersionedTransaction (base58)
  POST /fee-share/config     — set up fee-sharing config for a token

All endpoints require BAGS_API_KEY (x-api-key header).
The swap/fee-share transactions are returned unsigned — the frontend
(user's wallet) signs and broadcasts them on-chain.
"""

import logging
from typing import Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

SOL_MINT = "So11111111111111111111111111111111111111112"


class TradeAgent:
    def __init__(self):
        self._base_url = settings.BAGS_API_BASE_URL.rstrip("/")
        self._api_key = settings.BAGS_API_KEY
        self._timeout = settings.BAGS_API_TIMEOUT
        self._fee_wallet = getattr(settings, "PLATFORM_FEE_WALLET", None)

    def _headers(self) -> dict:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if self._api_key:
            h["x-api-key"] = self._api_key
        return h

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    # ─── Quote ────────────────────────────────────────────────────────────

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: Optional[int] = None,
    ) -> Optional[dict]:
        """GET /trade/quote — returns raw quote dict for use in swap build."""
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount,
            "slippageMode": "manual" if slippage_bps is not None else "auto",
        }
        if slippage_bps is not None:
            params["slippageBps"] = slippage_bps

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base_url}/trade/quote",
                    headers=self._headers(),
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", data)
        except httpx.HTTPStatusError as e:
            logger.warning(f"Quote HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            logger.warning(f"Quote error: {e}")
        return None

    # ─── Swap (build unsigned tx) ─────────────────────────────────────────

    async def build_swap(
        self,
        quote_response: dict,
        user_public_key: str,
    ) -> Optional[dict]:
        """
        POST /trade/swap — returns a base58 serialized VersionedTransaction.
        The frontend wallet signs and submits it on-chain.
        Platform fee is embedded automatically via the Bags API.
        """
        payload = {
            "quoteResponse": quote_response,
            "userPublicKey": user_public_key,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/trade/swap",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", data)
        except httpx.HTTPStatusError as e:
            logger.warning(f"Swap build HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            logger.warning(f"Swap build error: {e}")
        return None

    # ─── Fee-share config ─────────────────────────────────────────────────

    async def setup_fee_share(
        self,
        payer: str,
        base_mint: str,
        claimers: list[str],
        basis_points: list[int],
        tip_wallet: Optional[str] = None,
        tip_lamports: Optional[int] = None,
    ) -> Optional[dict]:
        """
        POST /fee-share/config — creates an on-chain fee-sharing config.
        Returns a base58 transaction for the payer to sign and broadcast.

        basis_points must sum to 10000 (100%).
        Example: claimers=["walletA"], basis_points=[10000] → 100% to walletA.
        """
        payload: dict = {
            "payer": payer,
            "baseMint": base_mint,
            "claimersArray": claimers,
            "basisPointsArray": basis_points,
        }
        if tip_wallet:
            payload["tipWallet"] = tip_wallet
        if tip_lamports:
            payload["tipLamports"] = tip_lamports

        # Inject platform partner wallet if configured
        if self._fee_wallet:
            payload["partner"] = self._fee_wallet

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/fee-share/config",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("response", data)
        except httpx.HTTPStatusError as e:
            logger.warning(f"Fee-share config HTTP {e.response.status_code}: {e.response.text[:200]}")
        except Exception as e:
            logger.warning(f"Fee-share config error: {e}")
        return None
