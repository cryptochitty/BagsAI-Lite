#!/usr/bin/env bash
# One-command local startup for BagsAI Lite
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BagsAI Lite — Local Startup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Setup .env if missing
if [ ! -f .env ]; then
  cp .env.example .env
  echo "[INFO] Created .env from .env.example — add your API keys there."
fi

# Install deps if needed
if ! python -c "import fastapi" 2>/dev/null; then
  echo "[INFO] Installing dependencies..."
  pip install -r requirements.txt -q
fi

# Start FastAPI in background
echo "[INFO] Starting FastAPI backend on http://localhost:8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

# Wait for API to be ready
sleep 2
echo "[INFO] API docs: http://localhost:8000/docs"

# Start Streamlit
echo "[INFO] Starting Streamlit dashboard on http://localhost:8501"
streamlit run frontend/streamlit_app.py --server.port 8501 &
UI_PID=$!

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Backend:   http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Dashboard: http://localhost:8501"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Press Ctrl+C to stop all services"

wait $API_PID $UI_PID
