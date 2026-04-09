"""
BagsAI Lite – Streamlit Dashboard
Connects to the FastAPI backend via REST.
"""
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# ─── Config ──────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(
    page_title="BagsAI Lite",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Helpers ─────────────────────────────────────────────────────────────────

def api_get(path: str, params: dict = None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to backend. Make sure the API server is running: `uvicorn app.main:app`")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, body: dict):
    try:
        r = requests.post(f"{API_BASE}{path}", json=body, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to backend.")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def tier_badge(tier: str) -> str:
    colors = {"S": "🟣", "A": "🟢", "B": "🟡", "C": "🔴"}
    return f"{colors.get(tier, '⚪')} {tier}"


def rec_badge(rec: str) -> str:
    badges = {"BUY": "✅ BUY", "HOLD": "🔵 HOLD", "WATCH": "👀 WATCH", "AVOID": "❌ AVOID"}
    return badges.get(rec, rec)


# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("💼 BagsAI Lite")
    st.caption("Autonomous Creator Intelligence Platform")
    st.divider()
    page = st.radio(
        "Navigate",
        ["📊 Dashboard", "🔍 Analyze", "📈 Simulate", "💰 Portfolio", "🤖 AI Chat"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption(f"API: `{API_BASE}`")

# ─── DASHBOARD ───────────────────────────────────────────────────────────────
if page == "📊 Dashboard":
    st.title("📊 Creator Token Dashboard")
    st.caption(f"Live data · {datetime.now().strftime('%H:%M:%S')}")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        limit = st.slider("Tokens to display", 5, 50, 20)
    with col2:
        tier_filter = st.selectbox("Filter by Tier", ["All", "S", "A", "B", "C"])
    with col3:
        show_gems = st.checkbox("Hidden Gems Only", False)

    if show_gems:
        data = api_get("/analyze/gems", {"limit": 20})
    else:
        params = {"limit": limit}
        if tier_filter != "All":
            params["tier"] = tier_filter
        data = api_get("/analyze", params)

    if data:
        df = pd.DataFrame(data)

        # KPI metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Tokens", len(df))
        m2.metric("Avg Score", f"{df['composite_score'].mean():.1f}")
        m3.metric("Hidden Gems", int(df['hidden_gem'].sum()))
        m4.metric("BUY signals", int((df['recommendation'] == 'BUY').sum()))

        st.divider()

        # Score chart
        st.subheader("Token Scores")
        fig = px.bar(
            df.sort_values("composite_score", ascending=True).tail(15),
            x="composite_score",
            y="name",
            color="tier",
            color_discrete_map={"S": "#9b59b6", "A": "#2ecc71", "B": "#f1c40f", "C": "#e74c3c"},
            orientation="h",
            labels={"composite_score": "Score", "name": "Token"},
            height=420,
        )
        fig.update_layout(showlegend=True, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)

        # Table
        st.subheader("Token Details")
        display_cols = ["name", "symbol", "price_usd", "volume_24h", "holder_count",
                        "composite_score", "tier", "recommendation", "hidden_gem"]
        display_df = df[display_cols].copy()
        display_df["tier"] = display_df["tier"].apply(tier_badge)
        display_df["recommendation"] = display_df["recommendation"].apply(rec_badge)
        display_df["hidden_gem"] = display_df["hidden_gem"].apply(lambda x: "💎" if x else "")
        display_df.columns = ["Name", "Symbol", "Price $", "Vol 24h", "Holders",
                              "Score", "Tier", "Signal", "Gem"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Explain button
        st.divider()
        st.subheader("Quick Explain")
        token_names = df["name"].tolist()
        sel = st.selectbox("Select token to explain", token_names)
        lang = st.radio("Language", ["English", "Tamil"], horizontal=True)
        lang_code = "ta" if lang == "Tamil" else "en"

        if st.button("🔍 Explain with AI"):
            tid = df[df["name"] == sel]["token_id"].values[0]
            with st.spinner("Generating AI explanation..."):
                result = api_get(f"/explain/{tid}", {"language": lang_code})
            if result:
                st.success(f"**{rec_badge(result['recommendation'])}** — Confidence: {result['confidence']:.0%}")
                st.write(result["summary"])
                if result["risks"]:
                    st.warning("**Risks:**\n" + "\n".join(f"- {r}" for r in result["risks"]))

# ─── ANALYZE ─────────────────────────────────────────────────────────────────
elif page == "🔍 Analyze":
    st.title("🔍 Deep Token Analysis")

    tab1, tab2 = st.tabs(["Trending Analysis", "Custom Token IDs"])

    with tab1:
        if st.button("Run Full Analysis"):
            with st.spinner("Scoring tokens..."):
                data = api_get("/analyze", {"limit": 50})
            if data:
                df = pd.DataFrame(data)

                # Scatter: volume vs holders, colored by score
                fig = px.scatter(
                    df,
                    x="volume_24h",
                    y="holder_count",
                    size="composite_score",
                    color="composite_score",
                    hover_name="name",
                    text="symbol",
                    color_continuous_scale="Viridis",
                    title="Volume vs Holders (bubble = score)",
                )
                st.plotly_chart(fig, use_container_width=True)

                # Score breakdown
                st.subheader("Score Components")
                comp_df = df[["name", "volume_growth", "holder_growth", "engagement_score"]].copy()
                comp_df = comp_df.melt(id_vars="name", var_name="Component", value_name="Value")
                fig2 = px.bar(comp_df, x="name", y="Value", color="Component", barmode="group",
                              height=400, title="Score Component Breakdown")
                fig2.update_xaxes(tickangle=45)
                st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        token_input = st.text_area(
            "Enter token IDs (one per line)",
            placeholder="tok_001\ntok_003\ntok_007",
            height=120,
        )
        if st.button("Analyze These Tokens"):
            ids = [t.strip() for t in token_input.splitlines() if t.strip()]
            if ids:
                with st.spinner("Analyzing..."):
                    data = api_post("/analyze", ids)
                if data:
                    st.dataframe(pd.DataFrame(data), use_container_width=True)
            else:
                st.warning("Enter at least one token ID")

# ─── SIMULATE ────────────────────────────────────────────────────────────────
elif page == "📈 Simulate":
    st.title("📈 Investment Simulation")

    col1, col2 = st.columns(2)
    with col1:
        capital = st.number_input("Initial Capital ($)", min_value=100.0, value=10000.0, step=500.0)
        days = st.slider("Simulation Days", 7, 180, 30)
        strategy = st.selectbox("Strategy", ["balanced", "aggressive", "conservative", "equal_weight"])
    with col2:
        rebalance = st.slider("Rebalance Every (days)", 1, 30, 7)
        default_tokens = "tok_001,tok_003,tok_005,tok_007,tok_010"
        token_ids_str = st.text_input("Token IDs (comma-separated)", value=default_tokens)

    token_ids = [t.strip() for t in token_ids_str.split(",") if t.strip()]

    if st.button("🚀 Run Simulation", type="primary"):
        with st.spinner(f"Simulating {days} days with {strategy} strategy..."):
            result = api_post("/simulate", {
                "token_ids": token_ids,
                "initial_capital": capital,
                "days": days,
                "strategy": strategy,
                "rebalance_frequency": rebalance,
            })

        if result:
            # KPI row
            r1, r2, r3, r4, r5 = st.columns(5)
            ret = result["total_return_pct"]
            r1.metric("Final Value", f"${result['final_value']:,.0f}", f"{ret:+.1f}%")
            r2.metric("Max Drawdown", f"{result['max_drawdown_pct']:.1f}%")
            r3.metric("Sharpe Ratio", f"{result['sharpe_ratio']:.2f}")
            r4.metric("Win Rate", f"{result['win_rate']:.0%}")
            r5.metric("Best Day", f"{result['best_day_pct']:+.1f}%")

            # Portfolio curve
            days_data = result["days"]
            df_days = pd.DataFrame(days_data)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_days["date"],
                y=df_days["portfolio_value"],
                mode="lines",
                name="Portfolio Value",
                line=dict(color="#2ecc71", width=2),
                fill="tozeroy",
                fillcolor="rgba(46,204,113,0.1)",
            ))
            fig.add_hline(y=capital, line_dash="dash", line_color="gray", annotation_text="Initial Capital")
            fig.update_layout(
                title=f"{strategy.title()} Strategy — {days} Day Simulation",
                xaxis_title="Date",
                yaxis_title="Portfolio Value ($)",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Daily returns distribution
            daily_rets = df_days["daily_return_pct"].tolist()
            fig2 = px.histogram(
                x=daily_rets,
                nbins=20,
                title="Daily Returns Distribution",
                labels={"x": "Daily Return (%)"},
                color_discrete_sequence=["#3498db"],
            )
            st.plotly_chart(fig2, use_container_width=True)

            if result.get("top_performer"):
                st.success(f"Top Performer: **{result['top_performer']}**")
            if result.get("worst_performer"):
                st.error(f"Worst Performer: **{result['worst_performer']}**")

# ─── PORTFOLIO ───────────────────────────────────────────────────────────────
elif page == "💰 Portfolio":
    st.title("💰 Portfolio Manager")

    with st.expander("Build New Portfolio", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            pcapital = st.number_input("Capital ($)", min_value=100.0, value=5000.0)
            pstrategy = st.selectbox("Strategy", ["balanced", "aggressive", "conservative", "equal_weight"])
        with col2:
            max_pos = st.slider("Max Positions", 2, 10, 5)
            token_ids_input = st.text_input("Token IDs (optional, comma-sep)", value="")
        with col3:
            st.write("")
            st.write("")
            build = st.button("Build Portfolio", type="primary")

    if build:
        body = {"capital": pcapital, "strategy": pstrategy, "max_positions": max_pos}
        if token_ids_input.strip():
            body["token_ids"] = [t.strip() for t in token_ids_input.split(",") if t.strip()]
        with st.spinner("Building portfolio..."):
            state = api_post("/portfolio", body)
        if state:
            st.session_state["portfolio"] = state

    # Load existing
    if "portfolio" not in st.session_state:
        existing = api_get("/portfolio")
        if existing:
            st.session_state["portfolio"] = existing

    if "portfolio" in st.session_state:
        state = st.session_state["portfolio"]

        # KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Value", f"${state['total_value']:,.0f}")
        k2.metric("Invested", f"${state['invested_usd']:,.0f}")
        k3.metric("PnL", f"${state['total_pnl']:+,.0f}", f"{state['total_pnl_pct']:+.1f}%")
        k4.metric("Risk Score", f"{state['risk_score']:.1f}/10")

        positions = state["positions"]
        if positions:
            df_pos = pd.DataFrame(positions)

            # Pie chart
            fig = px.pie(
                df_pos,
                values="value_usd",
                names="symbol",
                title="Portfolio Allocation",
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            col_a, col_b = st.columns([1, 1])
            with col_a:
                st.plotly_chart(fig, use_container_width=True)

            # PnL bar
            with col_b:
                fig2 = px.bar(
                    df_pos,
                    x="symbol",
                    y="pnl_pct",
                    color="pnl_pct",
                    color_continuous_scale=["#e74c3c", "#f1c40f", "#2ecc71"],
                    title="PnL % by Token",
                )
                st.plotly_chart(fig2, use_container_width=True)

            # Table
            st.dataframe(
                df_pos[["name", "symbol", "allocation_pct", "entry_price", "current_price",
                         "quantity", "value_usd", "pnl_usd", "pnl_pct", "risk_tier"]],
                use_container_width=True,
                hide_index=True,
            )

# ─── AI CHAT ─────────────────────────────────────────────────────────────────
elif page == "🤖 AI Chat":
    st.title("🤖 BagsAI Chat")
    st.caption("Ask questions about creator tokens, strategies, or get insights.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Display history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input("Ask BagsAI anything...")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                messages = [{"role": m["role"], "content": m["content"]}
                            for m in st.session_state.chat_history]
                result = api_post("/chat", {"messages": messages})
            reply = result.get("reply", "No response.") if result else "Error connecting to API."
            st.write(reply)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})

    if st.session_state.chat_history and st.button("Clear Chat"):
        st.session_state.chat_history = []
        st.rerun()
