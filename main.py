import logging
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from models import OptimizeRequest, OptimizeResponse
from llm_interpreter import interpret_notes
from guardrails import validate_interpretations
from optimizer import solve_energy_schedule
from validator import validate_schedule

# Avoid leaking sensitive stack traces
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="GridWise Optimization API")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": "Malformed JSON or structurally invalid request."}
    )

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/optimize-energy", response_model=OptimizeResponse)
def optimize_energy(request: OptimizeRequest):
    try:
        # 1. LLM Interpretation
        try:
            raw_interpretations = interpret_notes(request.operator_notes, request.battery.capacity_kwh)
        except Exception as e:
            logger.error(f"LLM interpretation failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to process operator notes due to provider error.")

        # 2. Guardrails validation
        interpretations = validate_interpretations(raw_interpretations, request)

        # 3. PuLP optimization
        try:
            hourly_plan = solve_energy_schedule(request, interpretations)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Optimization logic failed.")
            raise HTTPException(status_code=500, detail="Optimization solver failed.")

        # 4. Final schedule replay validator
        try:
            validate_schedule(request, interpretations, hourly_plan)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Final validation exception.")
            raise HTTPException(status_code=500, detail="Generated schedule failed validation.")

        # 5. Compute Totals
        total_grid_kwh = sum(p.grid_kwh for p in hourly_plan)
        
        # Sort hours safely to match plan with request
        sorted_plan = sorted(hourly_plan, key=lambda x: x.hour)
        total_cost_bdt = 0.0
        peak_grid_kwh = 0.0
        
        for p in sorted_plan:
            total_cost_bdt += p.grid_kwh * request.hours[p.hour].tariff_bdt_per_kwh
            if p.grid_kwh > peak_grid_kwh:
                peak_grid_kwh = p.grid_kwh

        # 6. Summary
        active_directives = sum(1 for d in interpretations if d.applies)
        plan_summary = f"Optimal schedule completed with total cost {total_cost_bdt:.2f} BDT. Evaluated {len(request.operator_notes)} notes, applied {active_directives} active directives."

        # Return final response
        return OptimizeResponse(
            scenario_id=request.scenario_id,
            directive_interpretation=interpretations,
            hourly_plan=sorted_plan,
            total_grid_kwh=round(total_grid_kwh, 4),
            total_cost_bdt=round(total_cost_bdt, 4),
            peak_grid_kwh=round(peak_grid_kwh, 4),
            plan_summary=plan_summary
        )

    except HTTPException:
        # Pass through expected HTTP exceptions
        raise
    except Exception as e:
        # Generic fallback for completely unexpected errors, returning generic 500 without stack traces
        logger.error("Unexpected error in optimize-energy.")
        raise HTTPException(status_code=500, detail="Internal Server Error")
