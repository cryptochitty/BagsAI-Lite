"""
ExplainAgent: generates structured LLM explanations for token scores.
Falls back to rule-based explanations if no LLM API key is configured.
"""
import logging
from typing import Optional

from app.agents.discovery_agent import DiscoveryAgent
from app.agents.analyst_agent import AnalystAgent
from app.models.simulation import ExplainRequest, ExplainResponse, ChatMessage
from app.core.config import settings
from app.services.cache_service import cache

logger = logging.getLogger(__name__)

TAMIL_PROMPT = "Respond in Tamil language (தமிழ்)."

SYSTEM_PROMPT = """You are BagsAI, an expert AI analyst for creator economy tokens on the Bags platform.
You analyze creator tokens and provide clear, structured investment insights.
Be concise, factual, and helpful. Always provide a JSON response with: summary, risks (list), recommendation."""


class ExplainAgent:
    def __init__(self):
        self._discovery = DiscoveryAgent()
        self._analyst = AnalystAgent()
        self._client = None
        self._init_llm()

    def _init_llm(self):
        if not settings.OPENAI_API_KEY:
            logger.info("No OPENAI_API_KEY — using rule-based explanations")
            return
        try:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI client initialized")
        except ImportError:
            logger.warning("openai package not installed")

    async def explain_token(self, req: ExplainRequest) -> ExplainResponse:
        cache_key = f"explain:{req.token_id}:{req.language}"
        cached = cache.get(cache_key)
        if cached:
            return ExplainResponse(**cached)

        # Gather context
        token = await self._discovery.fetch_token(req.token_id)
        if not token:
            return ExplainResponse(
                token_id=req.token_id,
                token_name="Unknown",
                language=req.language,
                summary="Token not found.",
                risks=["Token data unavailable"],
                recommendation="AVOID",
                confidence=0.0,
            )

        scores = await self._analyst.analyze_tokens([req.token_id])
        score = scores[0] if scores else None

        if self._client and settings.OPENAI_API_KEY:
            result = await self._llm_explain(token, score, req.language)
        else:
            result = self._rule_based_explain(token, score, req.language)

        cache.set(cache_key, result.model_dump(), ttl=600)
        return result

    async def _llm_explain(self, token, score, language: str) -> ExplainResponse:
        try:
            lang_instruction = TAMIL_PROMPT if language == "ta" else ""
            context = f"""
Token: {token.name} ({token.symbol})
Creator: {token.creator_name}
Price: ${token.price_usd}
Market Cap: ${token.market_cap:,.0f}
24h Volume: ${token.volume_24h:,.0f}
Holders: {token.holder_count} (prev: {token.holder_count_prev})
Engagement: {token.engagement_score}
Description: {token.description or 'N/A'}
"""
            if score:
                context += f"""
Composite Score: {score.composite_score}/100
Tier: {score.tier}
Volume Growth: {score.volume_growth:.2%}
Holder Growth: {score.holder_growth:.2%}
Hidden Gem: {score.hidden_gem}
Current Recommendation: {score.recommendation}
"""

            prompt = f"{lang_instruction}\nAnalyze this creator token and return JSON with keys: summary, risks (array of strings), recommendation.\n\n{context}"

            response = await self._client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=600,
                temperature=0.3,
            )

            import json
            data = json.loads(response.choices[0].message.content)
            return ExplainResponse(
                token_id=token.id,
                token_name=token.name,
                language=language,
                summary=data.get("summary", ""),
                risks=data.get("risks", []),
                recommendation=data.get("recommendation", score.recommendation if score else "HOLD"),
                confidence=0.85,
            )
        except Exception as e:
            logger.error(f"LLM explain failed: {e}, falling back to rule-based")
            return self._rule_based_explain(token, score, language)

    def _rule_based_explain(self, token, score, language: str) -> ExplainResponse:
        name = token.name
        sc = score.composite_score if score else 50
        rec = score.recommendation if score else "HOLD"
        tier = score.tier if score else "B"

        summary = (
            f"{name} is a Tier-{tier} creator token with a composite score of {sc:.1f}/100. "
            f"Holder count is {token.holder_count:,} with recent 24h volume of ${token.volume_24h:,.0f}. "
        )
        if score and score.hidden_gem:
            summary += "This token shows hidden gem characteristics with high engagement relative to market cap."

        risks = []
        if token.market_cap < 100000:
            risks.append("Very low market cap — high liquidity risk")
        if score and score.holder_growth < 0.1:
            risks.append("Slow holder growth — limited new demand signal")
        if score and score.volume_growth < 0.3:
            risks.append("Volume decelerating week-over-week")
        if token.engagement_score < 0.5:
            risks.append("Below-average community engagement")
        if not risks:
            risks.append("Standard market volatility risks apply")

        if language == "ta":
            summary = f"{name} ஒரு Tier-{tier} படைப்பாளர் டோக்கன், மதிப்பெண் {sc:.1f}/100. "
            summary += f"வைத்திருப்பவர்கள்: {token.holder_count:,}, 24h வால்யூம்: ${token.volume_24h:,.0f}."
            risks_ta = [
                r.replace("Very low market cap", "மிகவும் குறைந்த மார்க்கெட் கேப்")
                 .replace("Slow holder growth", "மெதுவான வைத்திருப்பவர் வளர்ச்சி")
                 .replace("Volume decelerating", "வால்யூம் குறைகிறது")
                 .replace("Below-average community engagement", "சராசரிக்கும் குறைவான சமூக ஈடுபாடு")
                 .replace("Standard market volatility risks apply", "சாதாரண சந்தை ஏற்ற இறக்க அபாயங்கள்")
                for r in risks
            ]
            risks = risks_ta

        return ExplainResponse(
            token_id=token.id,
            token_name=token.name,
            language=language,
            summary=summary,
            risks=risks,
            recommendation=rec,
            confidence=0.70,
        )

    async def chat(self, messages: list[ChatMessage], token_context: Optional[str] = None) -> str:
        if not self._client:
            return (
                "AI chat requires an OpenAI API key. "
                "Set OPENAI_API_KEY in your .env file. "
                "For now, use the /analyze and /explain endpoints for insights."
            )
        try:
            system = SYSTEM_PROMPT
            if token_context:
                system += f"\n\nCurrent token context:\n{token_context}"

            msgs = [{"role": "system", "content": system}]
            msgs += [{"role": m.role, "content": m.content} for m in messages]

            response = await self._client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=msgs,
                max_tokens=500,
                temperature=0.5,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return f"Chat error: {str(e)}"
