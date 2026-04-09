from fastapi import APIRouter, Query
from app.agents.explain_agent import ExplainAgent
from app.models.simulation import ExplainRequest, ExplainResponse, ChatRequest

router = APIRouter()
_agent = ExplainAgent()


@router.post("/explain", response_model=ExplainResponse, summary="AI explanation for a token")
async def explain_token(req: ExplainRequest):
    return await _agent.explain_token(req)


@router.get("/explain/{token_id}", response_model=ExplainResponse, summary="Quick explain by token ID")
async def explain_by_id(
    token_id: str,
    language: str = Query(default="en", description="en or ta"),
):
    return await _agent.explain_token(ExplainRequest(token_id=token_id, language=language))


@router.post("/chat", summary="AI chat with optional token context")
async def chat(req: ChatRequest):
    reply = await _agent.chat(req.messages, req.token_context)
    return {"reply": reply}
