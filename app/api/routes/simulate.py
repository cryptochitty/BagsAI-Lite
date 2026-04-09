from fastapi import APIRouter
from app.agents.simulation_agent import SimulationAgent
from app.models.simulation import SimulationRequest, SimulationResult

router = APIRouter()
_agent = SimulationAgent()


@router.post("/simulate", response_model=SimulationResult, summary="Run investment simulation")
async def run_simulation(req: SimulationRequest):
    return await _agent.run(req)
