"""
Unit and integration tests for BagsAI Lite.
Run: pytest tests/ -v
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.models.token import TokenRaw, TokenScore
from app.services.scoring_service import score_tokens, _normalize, _volume_growth, _holder_growth
from app.utils.mock_data import get_mock_tokens, get_mock_token_by_id


# ─── Scoring Service Tests ────────────────────────────────────────────────────

class TestNormalize:
    def test_all_same_values(self):
        result = _normalize([5.0, 5.0, 5.0])
        assert result == [0.5, 0.5, 0.5]

    def test_standard_range(self):
        result = _normalize([0.0, 5.0, 10.0])
        assert result[0] == 0.0
        assert result[-1] == 1.0
        assert abs(result[1] - 0.5) < 1e-9

    def test_single_value(self):
        result = _normalize([42.0])
        assert result == [0.5]

    def test_empty(self):
        assert _normalize([]) == []


class TestVolumeGrowth:
    def test_accelerating(self):
        token = TokenRaw(
            id="t1", name="Test", symbol="TST",
            volume_24h=200000, volume_7d=800000,
            holder_count=1000, holder_count_prev=900,
        )
        # weekly run rate = 200k * 7 = 1.4M > 800k → > 1
        assert _volume_growth(token) > 1.0

    def test_zero_7d_volume(self):
        token = TokenRaw(
            id="t1", name="Test", symbol="TST",
            volume_24h=100000, volume_7d=0,
            holder_count=500, holder_count_prev=400,
        )
        assert _volume_growth(token) == 0.0


class TestHolderGrowth:
    def test_positive_growth(self):
        token = TokenRaw(
            id="t1", name="Test", symbol="TST",
            volume_24h=100, volume_7d=700,
            holder_count=1100, holder_count_prev=1000,
        )
        assert abs(_holder_growth(token) - 0.1) < 1e-9

    def test_zero_prev(self):
        token = TokenRaw(
            id="t1", name="Test", symbol="TST",
            volume_24h=100, volume_7d=700,
            holder_count=500, holder_count_prev=0,
        )
        assert _holder_growth(token) == 0.0


class TestScoreTokens:
    def test_returns_sorted_descending(self):
        tokens = get_mock_tokens()
        scores = score_tokens(tokens)
        assert len(scores) == len(tokens)
        for i in range(len(scores) - 1):
            assert scores[i].composite_score >= scores[i + 1].composite_score

    def test_scores_in_range(self):
        tokens = get_mock_tokens()
        scores = score_tokens(tokens)
        for s in scores:
            assert 0 <= s.composite_score <= 100

    def test_tier_assignment(self):
        tokens = get_mock_tokens()
        scores = score_tokens(tokens)
        valid_tiers = {"S", "A", "B", "C"}
        for s in scores:
            assert s.tier in valid_tiers

    def test_recommendation_assignment(self):
        tokens = get_mock_tokens()
        scores = score_tokens(tokens)
        valid_recs = {"BUY", "HOLD", "WATCH", "AVOID"}
        for s in scores:
            assert s.recommendation in valid_recs

    def test_empty_returns_empty(self):
        assert score_tokens([]) == []

    def test_single_token(self):
        tokens = get_mock_tokens()[:1]
        scores = score_tokens(tokens)
        assert len(scores) == 1
        assert 0 <= scores[0].composite_score <= 100


# ─── Mock Data Tests ──────────────────────────────────────────────────────────

class TestMockData:
    def test_get_mock_tokens_returns_list(self):
        tokens = get_mock_tokens()
        assert len(tokens) > 0
        assert all(isinstance(t, TokenRaw) for t in tokens)

    def test_token_has_required_fields(self):
        tokens = get_mock_tokens()
        for t in tokens:
            assert t.id
            assert t.name
            assert t.symbol
            assert t.price_usd >= 0

    def test_get_by_id_found(self):
        token = get_mock_token_by_id("tok_001")
        assert token is not None
        assert token.id == "tok_001"

    def test_get_by_id_not_found(self):
        token = get_mock_token_by_id("nonexistent")
        assert token is None


# ─── FastAPI Endpoint Tests ───────────────────────────────────────────────────

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


class TestHealthEndpoints:
    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "running"

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestTokenEndpoints:
    def test_get_trending(self, client):
        r = client.get("/api/v1/tokens")
        assert r.status_code == 200
        data = r.json()
        assert "tokens" in data
        assert data["total"] > 0

    def test_get_trending_with_limit(self, client):
        r = client.get("/api/v1/tokens?limit=5")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] <= 5

    def test_get_token_by_id(self, client):
        r = client.get("/api/v1/tokens/tok_001")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "tok_001"

    def test_get_token_not_found(self, client):
        r = client.get("/api/v1/tokens/nonexistent_xyz")
        assert r.status_code == 404


class TestAnalyzeEndpoints:
    def test_analyze_trending(self, client):
        r = client.get("/api/v1/analyze")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "composite_score" in data[0]

    def test_analyze_with_tier_filter(self, client):
        r = client.get("/api/v1/analyze?tier=A")
        assert r.status_code == 200
        data = r.json()
        for token in data:
            assert token["tier"] == "A"

    def test_analyze_custom_tokens(self, client):
        r = client.post("/api/v1/analyze", json=["tok_001", "tok_003"])
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2

    def test_find_gems(self, client):
        r = client.get("/api/v1/analyze/gems")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)


class TestSimulateEndpoint:
    def test_run_simulation(self, client):
        r = client.post("/api/v1/simulate", json={
            "token_ids": ["tok_001", "tok_003", "tok_007"],
            "initial_capital": 1000.0,
            "days": 10,
            "strategy": "balanced",
            "rebalance_frequency": 5,
        })
        assert r.status_code == 200
        data = r.json()
        assert "final_value" in data
        assert "total_return_pct" in data
        assert len(data["days"]) == 10

    def test_simulation_strategies(self, client):
        for strategy in ["balanced", "aggressive", "conservative", "equal_weight"]:
            r = client.post("/api/v1/simulate", json={
                "token_ids": ["tok_001", "tok_005"],
                "initial_capital": 500.0,
                "days": 5,
                "strategy": strategy,
                "rebalance_frequency": 2,
            })
            assert r.status_code == 200, f"Failed for strategy: {strategy}"


class TestPortfolioEndpoint:
    def test_build_portfolio(self, client):
        r = client.post("/api/v1/portfolio", json={
            "capital": 5000.0,
            "strategy": "balanced",
            "max_positions": 3,
        })
        assert r.status_code == 200
        data = r.json()
        assert "positions" in data
        assert len(data["positions"]) <= 3

    def test_get_portfolio_after_build(self, client):
        # Build first
        client.post("/api/v1/portfolio", json={
            "capital": 1000.0,
            "strategy": "equal_weight",
            "max_positions": 2,
        })
        r = client.get("/api/v1/portfolio")
        assert r.status_code == 200


class TestExplainEndpoint:
    def test_explain_by_id(self, client):
        r = client.get("/api/v1/explain/tok_001")
        assert r.status_code == 200
        data = r.json()
        assert "summary" in data
        assert "risks" in data
        assert "recommendation" in data

    def test_explain_tamil(self, client):
        r = client.get("/api/v1/explain/tok_007?language=ta")
        assert r.status_code == 200
        data = r.json()
        assert data["language"] == "ta"

    def test_chat_no_key(self, client):
        r = client.post("/api/v1/chat", json={
            "messages": [{"role": "user", "content": "What is the best token right now?"}]
        })
        assert r.status_code == 200
        data = r.json()
        assert "reply" in data
