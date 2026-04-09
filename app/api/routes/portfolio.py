from fastapi import APIRouter, HTTPException
from app.agents.portfolio_agent import PortfolioAgent
from app.models.portfolio import AllocationRequest, PortfolioState

router = APIRouter()
_agent = PortfolioAgent()


@router.post("/portfolio", response_model=PortfolioState, summary="Build and return a portfolio")
async def build_portfolio(req: AllocationRequest):
    return await _agent.build_portfolio(req)


@router.get("/portfolio", response_model=PortfolioState, summary="Get current portfolio state")
async def get_portfolio():
    state = await _agent.get_state()
    if not state:
        raise HTTPException(
            status_code=404,
            detail="No portfolio found. POST /portfolio first to build one."
        )
    return state
