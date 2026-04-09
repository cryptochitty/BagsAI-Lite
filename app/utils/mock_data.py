"""
Mock dataset for demo/testing when Bags API is unavailable.
Realistic creator token data with variance for simulation.
"""
import random
from datetime import datetime, timedelta
from app.models.token import TokenRaw


MOCK_TOKENS: list[dict] = [
    {
        "id": "tok_001",
        "name": "PixelDrop",
        "symbol": "PIXEL",
        "creator_address": "0xabc1",
        "creator_name": "PixelArtist_Jay",
        "price_usd": 0.0245,
        "volume_24h": 182000,
        "volume_7d": 940000,
        "holder_count": 3420,
        "holder_count_prev": 2900,
        "market_cap": 245000,
        "engagement_score": 0.82,
        "description": "Digital art creator token with strong community.",
    },
    {
        "id": "tok_002",
        "name": "SoundWave",
        "symbol": "SWAV",
        "creator_address": "0xabc2",
        "creator_name": "BeatMaker_Ravi",
        "price_usd": 0.0089,
        "volume_24h": 67000,
        "volume_7d": 320000,
        "holder_count": 1850,
        "holder_count_prev": 1700,
        "market_cap": 89000,
        "engagement_score": 0.64,
        "description": "Music producer token with growing fanbase.",
    },
    {
        "id": "tok_003",
        "name": "VlogVault",
        "symbol": "VLOG",
        "creator_address": "0xabc3",
        "creator_name": "TravelVlogger_Priya",
        "price_usd": 0.1540,
        "volume_24h": 520000,
        "volume_7d": 2400000,
        "holder_count": 12300,
        "holder_count_prev": 9800,
        "market_cap": 1540000,
        "engagement_score": 0.91,
        "description": "Top travel content creator with massive holder growth.",
    },
    {
        "id": "tok_004",
        "name": "CodeCraft",
        "symbol": "CODE",
        "creator_address": "0xabc4",
        "creator_name": "DevGuru_Mani",
        "price_usd": 0.0672,
        "volume_24h": 95000,
        "volume_7d": 410000,
        "holder_count": 4100,
        "holder_count_prev": 4050,
        "market_cap": 672000,
        "engagement_score": 0.58,
        "description": "Tech educator token, stable but low engagement growth.",
    },
    {
        "id": "tok_005",
        "name": "FitForge",
        "symbol": "FIT",
        "creator_address": "0xabc5",
        "creator_name": "FitnessKing_Arjun",
        "price_usd": 0.0310,
        "volume_24h": 148000,
        "volume_7d": 680000,
        "holder_count": 5600,
        "holder_count_prev": 4900,
        "market_cap": 310000,
        "engagement_score": 0.77,
        "description": "Fitness influencer token with high 7d volume.",
    },
    {
        "id": "tok_006",
        "name": "ChefToken",
        "symbol": "CHEF",
        "creator_address": "0xabc6",
        "creator_name": "MasterChef_Lakshmi",
        "price_usd": 0.0045,
        "volume_24h": 12000,
        "volume_7d": 55000,
        "holder_count": 820,
        "holder_count_prev": 780,
        "market_cap": 45000,
        "engagement_score": 0.43,
        "description": "Early-stage food creator token, low volume.",
    },
    {
        "id": "tok_007",
        "name": "GamingGuild",
        "symbol": "GUILD",
        "creator_address": "0xabc7",
        "creator_name": "StreamerKing_Vikram",
        "price_usd": 0.2100,
        "volume_24h": 890000,
        "volume_7d": 4100000,
        "holder_count": 28000,
        "holder_count_prev": 22000,
        "market_cap": 2100000,
        "engagement_score": 0.95,
        "description": "Largest gaming creator token by holders.",
    },
    {
        "id": "tok_008",
        "name": "MindfulMint",
        "symbol": "MFMNT",
        "creator_address": "0xabc8",
        "creator_name": "Wellness_Ananya",
        "price_usd": 0.0128,
        "volume_24h": 34000,
        "volume_7d": 160000,
        "holder_count": 2100,
        "holder_count_prev": 1900,
        "market_cap": 128000,
        "engagement_score": 0.69,
        "description": "Wellness and meditation creator, steady growth.",
    },
    {
        "id": "tok_009",
        "name": "NightOwl",
        "symbol": "NOWL",
        "creator_address": "0xabc9",
        "creator_name": "NightVlogger_Suresh",
        "price_usd": 0.0019,
        "volume_24h": 8500,
        "volume_7d": 38000,
        "holder_count": 410,
        "holder_count_prev": 350,
        "market_cap": 19000,
        "engagement_score": 0.38,
        "description": "Niche creator, hidden gem potential.",
    },
    {
        "id": "tok_010",
        "name": "StyleSphere",
        "symbol": "STYL",
        "creator_address": "0xabc10",
        "creator_name": "FashionIcon_Kavya",
        "price_usd": 0.0880,
        "volume_24h": 340000,
        "volume_7d": 1500000,
        "holder_count": 9200,
        "holder_count_prev": 7600,
        "market_cap": 880000,
        "engagement_score": 0.88,
        "description": "Fashion creator with accelerating growth.",
    },
]


def get_mock_tokens() -> list[TokenRaw]:
    tokens = []
    for t in MOCK_TOKENS:
        tokens.append(TokenRaw(
            id=t["id"],
            name=t["name"],
            symbol=t["symbol"],
            creator_address=t.get("creator_address"),
            creator_name=t.get("creator_name"),
            price_usd=t["price_usd"],
            volume_24h=t["volume_24h"],
            volume_7d=t["volume_7d"],
            holder_count=t["holder_count"],
            holder_count_prev=t["holder_count_prev"],
            market_cap=t["market_cap"],
            engagement_score=t["engagement_score"],
            description=t.get("description"),
            created_at=datetime.utcnow() - timedelta(days=random.randint(10, 180)),
        ))
    return tokens


def get_mock_token_by_id(token_id: str) -> TokenRaw | None:
    for t in MOCK_TOKENS:
        if t["id"] == token_id:
            return TokenRaw(**{**t, "created_at": datetime.utcnow() - timedelta(days=30)})
    return None


def get_mock_price_history(token_id: str, days: int = 30) -> list[float]:
    """Generate synthetic price history for simulation."""
    base = next((t["price_usd"] for t in MOCK_TOKENS if t["id"] == token_id), 0.01)
    prices = [base]
    for _ in range(days - 1):
        change = random.gauss(0.002, 0.05)  # slight upward bias
        prices.append(max(0.0001, prices[-1] * (1 + change)))
    return prices
