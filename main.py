import logging
from fastapi import FastAPI, HTTPException
from models import OptimizeRequest, OptimizeResponse, HourlyPlan
from llm_interpreter import interpret_notes
from guardrails import validate_interpretations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GridWise Optimization API")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/optimize-energy", response_model=OptimizeResponse)
async def optimize_energy(request: OptimizeRequest):
    try:
        # 1. LLM Interpretation
        try:
            raw_interpretations = interpret_notes(request.operator_notes, request.battery.capacity_kwh)
        except Exception as e:
            logger.error(f"LLM interpretation failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to process operator notes.")

        # 2. Guardrails validation
        interpretations = validate_interpretations(raw_interpretations, request)

        # 3. Placeholder for optimization
        # At this stage, we return a controlled placeholder error before optimization is fully integrated
        raise HTTPException(status_code=501, detail="Optimization not yet implemented.")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
