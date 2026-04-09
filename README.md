# BagsAI Lite — Autonomous Creator Intelligence Platform

A production-ready multi-agent AI system that analyzes creator tokens using the Bags REST API. No blockchain interaction required.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Dashboard (8501)                │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST
┌──────────────────────────▼──────────────────────────────────┐
│                  FastAPI Backend (8000)                      │
│  /tokens  /analyze  /simulate  /portfolio  /explain  /chat  │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
  DiscoveryAgent     AnalystAgent      ExplainAgent
  (Bags API +        (Scoring +        (OpenAI LLM +
   fallback mock)     tiering)          rule-based)
        │                  │
        ▼                  ▼
  SimulationAgent   PortfolioAgent
  (Time-series       (Allocation +
   backtesting)       risk scoring)
        │
        ▼
  Cache Layer (Redis / in-memory)
```

## Quick Start (One Command)

```bash
cd bagsai-lite
cp .env.example .env        # add your API keys
./start.sh                  # starts backend + frontend
```

- **Backend:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Dashboard:** http://localhost:8501

## Docker

```bash
docker-compose up --build
```

## Manual Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Terminal 1: API
uvicorn app.main:app --reload

# Terminal 2: UI
streamlit run frontend/streamlit_app.py
```

---

## Configuration (.env)

| Variable | Default | Description |
|---|---|---|
| `BAGS_API_KEY` | — | Your Bags API key (optional, mock data used without it) |
| `BAGS_API_BASE_URL` | `https://api.bags.fm` | Bags REST API base URL |
| `OPENAI_API_KEY` | — | Enables LLM explanations and AI chat |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model for explanations |
| `REDIS_URL` | — | Redis URL (falls back to in-memory) |
| `CACHE_TTL` | `300` | Cache TTL in seconds |
| `VOLUME_WEIGHT` | `0.4` | Scoring weight for volume growth |
| `HOLDER_WEIGHT` | `0.3` | Scoring weight for holder growth |
| `ENGAGEMENT_WEIGHT` | `0.3` | Scoring weight for engagement |

---

## API Reference

### GET /api/v1/tokens
Returns trending creator tokens.
```
?limit=20
```

### GET /api/v1/analyze
AI-scored and ranked tokens.
```
?limit=20&tier=A
```

### POST /api/v1/analyze
Analyze specific tokens by ID.
```json
["tok_001", "tok_003"]
```

### GET /api/v1/analyze/gems
Hidden gem detector — high score, low market cap.

### POST /api/v1/simulate
Run investment simulation.
```json
{
  "token_ids": ["tok_001", "tok_003"],
  "initial_capital": 10000,
  "days": 30,
  "strategy": "balanced",
  "rebalance_frequency": 7
}
```
Strategies: `balanced` | `aggressive` | `conservative` | `equal_weight`

### POST /api/v1/portfolio
Build a risk-balanced portfolio.
```json
{
  "capital": 5000,
  "strategy": "balanced",
  "max_positions": 5
}
```

### GET /api/v1/explain/{token_id}
AI explanation for a token.
```
?language=en   # or "ta" for Tamil
```

### POST /api/v1/chat
AI chat assistant.
```json
{
  "messages": [{"role": "user", "content": "Which token should I buy?"}],
  "token_context": "optional context string"
}
```

---

## Scoring Formula

```python
score = (
    volume_growth   * 0.4 +   # Accelerating volume
    holder_growth   * 0.3 +   # New holder acquisition
    engagement_score * 0.3    # Community activity
) * 100   # normalized to 0–100
```

**Tiers:**
- **S** ≥ 80 — Exceptional
- **A** ≥ 65 — Strong
- **B** ≥ 45 — Moderate  
- **C** < 45 — Weak

**Hidden Gem:** Score ≥ 55 AND market cap in bottom 30% of dataset.

---

## Multi-Agent System

| Agent | Responsibility |
|---|---|
| `DiscoveryAgent` | Fetches Bags API data with retries + mock fallback |
| `AnalystAgent` | Scores and ranks tokens using composite formula |
| `SimulationAgent` | Backtests investment strategies over synthetic time-series |
| `PortfolioAgent` | Allocates capital with risk balancing |
| `ExplainAgent` | LLM-powered structured explanations (EN + Tamil) |

---

## Testing

```bash
pytest tests/ -v
```

Tests cover:
- Scoring math (normalization, weighting)
- All API endpoints (tokens, analyze, simulate, portfolio, explain, chat)
- Mock data integrity
- Edge cases (empty data, zero values, unknown tokens)

---

## Deployment

### Render
1. Create a **Web Service**, connect repo
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables in Render dashboard

### Frontend (Streamlit Cloud)
1. Deploy `frontend/streamlit_app.py`
2. Set `API_BASE` to your Render backend URL

### Railway / Fly.io
```bash
# Railway
railway up

# Fly
fly launch && fly deploy
```

---

## Fallback Behavior

The system is designed to always work:

| Component | Primary | Fallback |
|---|---|---|
| Token data | Bags REST API | 10 realistic mock tokens |
| Cache | Redis | In-memory TTL cache |
| AI explanations | OpenAI GPT | Rule-based engine |

No hard failures. Demo works without any API keys.
