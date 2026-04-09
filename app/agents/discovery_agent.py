"""
DiscoveryAgent: fetches real-time creator token data from the Bags REST API.

Real API: https://public-api-v2.bags.fm/api/v1
Auth:     x-api-key header (get key at dev.bags.fm)
Docs:     https://docs.bags.fm

Endpoints used:
  GET  /ping                                      — health check
  GET  /token-launch/creator/v3?tokenMint={mint} — creator + token info
  GET  /token-launch/lifetime-fees?tokenMint={mint} — fees earned (lamports)
  GET  /trade/quote?inputMint=...&outputMint=...&amount=... — real-time price

For trending / volume / holder counts the official Bags API has no public
listing endpoint. We supplement with:
  1. Bitquery Solana GraphQL (if BITQUERY_API_KEY is set)
  2. Known-mint list from .env  (BAGS_TOKEN_MINTS=mint1,mint2,...)
  3. DexScreener API — free, no key required (bags.fm pairs on Solana)
  4. Mock data as final fallback
"""

import asyncio
import logging
from typing import Optional
import httpx

from app.core.config import settings
from app.models.token import TokenRaw
from app.services.cache_service import cache
from app.utils.mock_data import get_mock_tokens, get_mock_token_by_id

logger = logging.getLogger(__name__)

CACHE_KEY_TRENDING = "discovery:trending:{}"
CACHE_KEY_TOKEN = "discovery:token:{}"
CACHE_KEY_HEALTH = "discovery:api_healthy"

# SOL mint (used as the "output" in price quotes)
SOL_MINT = "So11111111111111111111111111111111111111112"

# Lamports per SOL
LAMPORTS = 1_000_000_000

# Free public APIs — no key required
DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"
DEXSCREENER_TOKEN_URL = "https://api.dexscreener.com/latest/dex/tokens/{mint}"
JUPITER_PRICE_URL = "https://price.jup.ag/v6/price"

# Bitquery GraphQL for trending Bags.fm tokens
BITQUERY_GQL = """
query BagsTrending($limit: Int!) {
  Solana {
    DEXTrades(
      where: {
        Trade: { Dex: { ProtocolName: { is: "bags" } } }
      }
      limit: { count: $limit }
      orderBy: { descending: Block_Time }
    ) {
      Trade {
        Buy {
          Currency { MintAddress Name Symbol }
          Amount
          PriceInUSD
        }
        Sell { Amount PriceInUSD }
        Dex { ProtocolName ProtocolFamily }
      }
      Block { Time }
    }
  }
}
"""


class DiscoveryAgent:
    def __init__(self):
        self._base_url = settings.BAGS_API_BASE_URL.rstrip("/")
        self._api_key = settings.BAGS_API_KEY
        self._timeout = settings.BAGS_API_TIMEOUT
        self._retries = settings.BAGS_API_RETRIES
        self._bitquery_key = getattr(settings, "BITQUERY_API_KEY", None)

    # ─── HTTP helpers ──────────────────────────────────────────────────────

    def _headers(self) -> dict:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if self._api_key:
            h["x-api-key"] = self._api_key
        return h

    async def _get(self, path: str, params: Optional[dict] = None) -> Optional[dict]:
        url = f"{self._base_url}{path}"
        for attempt in range(1, self._retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.get(url, headers=self._headers(), params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    # Bags API wraps responses: {"success": true, "response": {...}}
                    if isinstance(data, dict) and "response" in data:
                        return data["response"]
                    return data
            except httpx.HTTPStatusError as e:
                logger.warning(f"Bags API HTTP {e.response.status_code} on {path} (attempt {attempt})")
                if e.response.status_code in (401, 403):
                    logger.error("Bags API key invalid or missing — check BAGS_API_KEY in .env")
                    return None  # no point retrying auth errors
            except (httpx.RequestError, Exception) as e:
                logger.warning(f"Bags API error on {path} attempt {attempt}: {e}")
            if attempt < self._retries:
                await asyncio.sleep(0.5 * attempt)
        return None

    async def _post_bitquery(self, query: str, variables: dict) -> Optional[dict]:
        if not self._bitquery_key:
            return None
        url = "https://streaming.bitquery.io/eap"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._bitquery_key}",
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={"query": query, "variables": variables},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"Bitquery error: {e}")
            return None

    # ─── API health check ─────────────────────────────────────────────────

    async def ping(self) -> bool:
        cached = cache.get(CACHE_KEY_HEALTH)
        if cached is not None:
            return cached
        result = await self._get("/ping")
        healthy = result is not None
        cache.set(CACHE_KEY_HEALTH, healthy, ttl=30)
        return healthy

    # ─── Token creators + metadata ────────────────────────────────────────

    async def fetch_token_creators(self, mint: str) -> Optional[list[dict]]:
        """GET /token-launch/creator/v3 — returns creator wallets, usernames, royalties."""
        return await self._get("/token-launch/creator/v3", params={"tokenMint": mint})

    async def fetch_lifetime_fees(self, mint: str) -> Optional[float]:
        """GET /token-launch/lifetime-fees — returns total fees in lamports → converted to SOL."""
        data = await self._get("/token-launch/lifetime-fees", params={"tokenMint": mint})
        if data is None:
            return None
        # Response may be int (lamports) or {"totalFees": N}
        if isinstance(data, (int, float)):
            return data / LAMPORTS
        if isinstance(data, dict):
            lamports = data.get("totalFees") or data.get("fees") or 0
            return float(lamports) / LAMPORTS
        return None

    async def fetch_price_quote(self, input_mint: str, output_mint: str = SOL_MINT, amount: int = 1_000_000) -> Optional[float]:
        """
        GET /trade/quote — get real-time price via swap quote.
        Returns price in SOL (divide by amount to get per-unit price).
        """
        data = await self._get("/trade/quote", params={
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount,
        })
        if not data:
            return None
        # Response: {outAmount, inAmount, priceImpactPct, ...}
        out = data.get("outAmount") or data.get("outputAmount")
        if out:
            return float(out) / LAMPORTS
        return None

    # ─── Build TokenRaw from real Bags API data ───────────────────────────

    async def _enrich_token(self, mint: str, name: str, symbol: str,
                            price_usd: float = 0.0, volume_24h: float = 0.0,
                            holder_count: int = 0) -> TokenRaw:
        """Fetch creator info + fees and merge into a TokenRaw."""
        creators_data, fees_sol = await asyncio.gather(
            self.fetch_token_creators(mint),
            self.fetch_lifetime_fees(mint),
            return_exceptions=True,
        )

        creator_name = None
        if isinstance(creators_data, list) and creators_data:
            primary = next((c for c in creators_data if c.get("isCreator")), creators_data[0])
            creator_name = primary.get("providerUsername") or primary.get("wallet", "")[:8]

        engagement = 0.0
        if isinstance(fees_sol, float) and fees_sol > 0:
            # Use fees as engagement proxy: log-scaled to 0-1
            import math
            engagement = min(math.log1p(fees_sol) / 10, 1.0)

        return TokenRaw(
            id=mint,
            name=name,
            symbol=symbol,
            creator_address=None,
            creator_name=creator_name,
            price_usd=price_usd,
            volume_24h=volume_24h,
            volume_7d=volume_24h * 7,   # approximation until we have 7d data
            holder_count=holder_count,
            holder_count_prev=max(0, holder_count - 10),
            market_cap=price_usd * 1_000_000,  # rough supply assumption
            engagement_score=engagement,
        )

    # ─── Trending via Bitquery ────────────────────────────────────────────

    async def _fetch_bitquery_trending(self, limit: int) -> list[TokenRaw]:
        data = await self._post_bitquery(BITQUERY_GQL, {"limit": limit * 5})
        if not data:
            return []

        trades = (
            data.get("data", {})
                .get("Solana", {})
                .get("DEXTrades", [])
        )
        if not trades:
            return []

        # Deduplicate by mint, accumulate volume
        seen: dict[str, dict] = {}
        for t in trades:
            buy = t.get("Trade", {}).get("Buy", {})
            currency = buy.get("Currency", {})
            mint = currency.get("MintAddress", "")
            if not mint or mint == SOL_MINT:
                continue

            price = float(buy.get("PriceInUSD") or 0)
            volume = float(buy.get("Amount") or 0) * price

            if mint not in seen:
                seen[mint] = {
                    "mint": mint,
                    "name": currency.get("Name") or "Unknown",
                    "symbol": currency.get("Symbol") or "???",
                    "price_usd": price,
                    "volume_24h": volume,
                    "holder_count": 0,
                }
            else:
                seen[mint]["volume_24h"] += volume
                if price > 0:
                    seen[mint]["price_usd"] = price

        # Sort by volume, take top N, enrich with Bags API
        top = sorted(seen.values(), key=lambda x: x["volume_24h"], reverse=True)[:limit]

        tasks = [
            self._enrich_token(
                mint=item["mint"],
                name=item["name"],
                symbol=item["symbol"],
                price_usd=item["price_usd"],
                volume_24h=item["volume_24h"],
            )
            for item in top
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, TokenRaw)]

    # ─── DexScreener (no API key) ─────────────────────────────────────────

    async def _fetch_dexscreener_trending(self, limit: int) -> list[TokenRaw]:
        """
        Query DexScreener for bags.fm pairs on Solana — no API key required.
        Filters to dexId == 'bags' so we only see Bags.fm-launched tokens.
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    DEXSCREENER_SEARCH_URL,
                    params={"q": "bags"},
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning(f"DexScreener search error: {e}")
            return []

        pairs = data.get("pairs") or []
        # Keep only Solana bags.fm pairs
        bags_pairs = [
            p for p in pairs
            if p.get("chainId") == "solana" and p.get("dexId") == "bags"
        ]
        if not bags_pairs:
            # Wider fallback: any solana pair with bags in the name
            bags_pairs = [p for p in pairs if p.get("chainId") == "solana"]

        # Sort by 24h volume descending
        bags_pairs.sort(key=lambda p: float(p.get("volume", {}).get("h24") or 0), reverse=True)
        bags_pairs = bags_pairs[:limit]

        tokens: list[TokenRaw] = []
        for p in bags_pairs:
            base = p.get("baseToken", {})
            mint = base.get("address", "")
            if not mint:
                continue
            vol24 = float(p.get("volume", {}).get("h24") or 0)
            price_usd = float(p.get("priceUsd") or 0)
            fdv = float(p.get("fdv") or 0)
            liquidity = float((p.get("liquidity") or {}).get("usd") or 0)
            # Use liquidity as market cap proxy if fdv missing
            market_cap = fdv if fdv else liquidity

            tokens.append(TokenRaw(
                id=mint,
                name=base.get("name") or mint[:8],
                symbol=base.get("symbol") or mint[:4].upper(),
                creator_address=None,
                creator_name=None,
                price_usd=price_usd,
                volume_24h=vol24,
                volume_7d=float(p.get("volume", {}).get("h6") or 0) * 28,  # rough 7d approx
                holder_count=0,
                holder_count_prev=0,
                market_cap=market_cap,
                engagement_score=min(vol24 / 1_000_000, 1.0) if vol24 else 0.0,
            ))

        logger.info(f"DexScreener returned {len(tokens)} bags pairs")
        return tokens

    async def _fetch_jupiter_price(self, mint: str) -> Optional[float]:
        """Get real-time USD price from Jupiter Price API — no key required."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(JUPITER_PRICE_URL, params={"ids": mint})
                resp.raise_for_status()
                data = resp.json()
            price = data.get("data", {}).get(mint, {}).get("price")
            return float(price) if price else None
        except Exception as e:
            logger.warning(f"Jupiter price error for {mint}: {e}")
            return None

    # ─── Token mints from env (BAGS_TOKEN_MINTS) ─────────────────────────

    async def _fetch_from_env_mints(self, limit: int) -> list[TokenRaw]:
        """
        If the user sets BAGS_TOKEN_MINTS=mint1,mint2,... in .env,
        fetch real data for those specific tokens.
        """
        mints_env = getattr(settings, "BAGS_TOKEN_MINTS", None) or ""
        if not mints_env:
            return []

        mints = [m.strip() for m in mints_env.split(",") if m.strip()][:limit]
        tasks = [self._enrich_token(mint=m, name=m[:8], symbol=m[:4].upper()) for m in mints]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, TokenRaw)]

    # ─── Public interface ─────────────────────────────────────────────────

    async def fetch_trending(self, limit: int = 20) -> list[TokenRaw]:
        cache_key = CACHE_KEY_TRENDING.format(limit)
        cached = cache.get(cache_key)
        if cached:
            logger.debug("Cache hit: trending tokens")
            return [TokenRaw(**t) for t in cached]

        tokens: list[TokenRaw] = []

        # 1. Try Bitquery for trending (best real-time source)
        if self._bitquery_key:
            logger.info("Fetching trending from Bitquery...")
            tokens = await self._fetch_bitquery_trending(limit)

        # 2. Try env-defined mints via Bags API
        if not tokens and self._api_key:
            logger.info("Fetching from BAGS_TOKEN_MINTS in .env...")
            tokens = await self._fetch_from_env_mints(limit)

        # 3. DexScreener — free, no key required
        if not tokens:
            logger.info("Fetching trending from DexScreener (no key required)...")
            tokens = await self._fetch_dexscreener_trending(limit)

        # 4. Fallback to mock
        if not tokens:
            logger.info("Using mock data — DexScreener also unavailable")
            tokens = get_mock_tokens()[:limit]
            cache.set(cache_key, [t.model_dump() for t in tokens], ttl=60)
            return tokens

        cache.set(cache_key, [t.model_dump() for t in tokens])
        logger.info(f"Fetched {len(tokens)} live trending tokens")
        return tokens

    async def fetch_token(self, token_id: str) -> Optional[TokenRaw]:
        """Fetch a single token. token_id can be a Solana mint address or mock id."""
        cache_key = CACHE_KEY_TOKEN.format(token_id)
        cached = cache.get(cache_key)
        if cached:
            return TokenRaw(**cached)

        # If it looks like a Solana mint (base58, 32-44 chars), use live data
        if len(token_id) >= 32 and not token_id.startswith("tok_"):
            # Try DexScreener first (no key needed) for full metadata
            dex_tokens = []
            try:
                async with httpx.AsyncClient(timeout=8) as client:
                    resp = await client.get(
                        DEXSCREENER_TOKEN_URL.format(mint=token_id),
                        headers={"Accept": "application/json"},
                    )
                    resp.raise_for_status()
                    pairs = (resp.json().get("pairs") or [])
                    if pairs:
                        p = sorted(pairs, key=lambda x: float((x.get("volume") or {}).get("h24") or 0), reverse=True)[0]
                        base = p.get("baseToken", {})
                        dex_tokens = [TokenRaw(
                            id=token_id,
                            name=base.get("name") or token_id[:8],
                            symbol=base.get("symbol") or token_id[:4].upper(),
                            creator_address=None,
                            creator_name=None,
                            price_usd=float(p.get("priceUsd") or 0),
                            volume_24h=float((p.get("volume") or {}).get("h24") or 0),
                            volume_7d=float((p.get("volume") or {}).get("h6") or 0) * 28,
                            holder_count=0,
                            holder_count_prev=0,
                            market_cap=float(p.get("fdv") or 0),
                            engagement_score=0.0,
                        )]
            except Exception as e:
                logger.warning(f"DexScreener token lookup error: {e}")

            if dex_tokens:
                token = dex_tokens[0]
                cache.set(cache_key, token.model_dump())
                return token

            # Bags API enrichment (needs key)
            token = await self._enrich_token(mint=token_id, name=token_id[:8], symbol=token_id[:4].upper())
            if token:
                # Try Bags quote first, Jupiter as free fallback
                price = await self.fetch_price_quote(token_id)
                if not price:
                    price = await self._fetch_jupiter_price(token_id)
                if price:
                    token.price_usd = price
                cache.set(cache_key, token.model_dump())
                return token

        # Mock fallback
        mock = get_mock_token_by_id(token_id)
        if mock:
            cache.set(cache_key, mock.model_dump(), ttl=60)
        return mock

    async def fetch_tokens_batch(self, token_ids: list[str]) -> list[TokenRaw]:
        tasks = [self.fetch_token(tid) for tid in token_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, TokenRaw)]
