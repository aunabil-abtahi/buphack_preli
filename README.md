# GridWise Energy Optimizer

## 1. Project Title
GridWise Energy Optimizer (BUPHack Preliminary Submission)

## 2. Problem Overview
The GridWise Energy Optimizer is an intelligent microgrid management system designed to balance energy demand, solar generation, and battery storage across a 24-hour horizon. The system processes complex, unstructured operator notes using an LLM to derive structured operational directives, and then calculates a mathematically optimal energy plan that minimizes overall costs while respecting physical battery limitations and operator constraints.

## 3. Architecture Overview
The system follows a robust, multi-stage pipeline:
- **Operator Notes**: Unstructured natural language inputs expressing operational constraints.
- **Gemini LLM Interpreter**: Parses notes and translates them into a list of structured directives.
- **Deterministic Guardrails**: Validates and sanitizes the LLM output to ensure logical consistency and safety (e.g., verifying hour ranges and allowed directives) without any hallucinations.
- **PuLP Optimizer**: A Mixed-Integer Linear Programming (MILP) model that calculates the lowest-cost grid usage plan while satisfying all physical and directive constraints.
- **Final Replay Validator**: An independent validation layer that replays the generated plan hour-by-hour to guarantee it perfectly adheres to physical battery limits and energy balance.
- **JSON Response**: A structured, compact payload returning the final operational plan, summary metrics, and the exact interpretation of the operator notes.

## 4. Technology Stack
- **Python** (3.9+)
- **FastAPI**: High-performance web framework for the API endpoints.
- **Pydantic**: Strict data validation and settings management.
- **google-genai**: Official Google Gemini SDK for LLM interactions.
- **Gemini model/provider**: `gemini-3.5-flash` model for fast, accurate text interpretation.
- **PuLP**: Linear programming API for mathematical optimization.
- **Docker**: Containerization for reproducible deployments.

## 5. LLM Role
The Gemini LLM is used **strictly as a natural language interpreter**. It reads the unstructured `operator_notes` array and maps them into supported structured directives used by the optimizer. It does not perform mathematical calculations or generate the final schedule; it merely classifies intent and extracts time windows/values to feed into the deterministic optimizer.

## 6. Supported Directives
The system supports the following strict directives:
- `solar_reduction`: Reduces available solar energy by a specified percentage.
- `minimum_battery_reserve`: Enforces a higher minimum battery energy level (kWh) than the hardware default.
- `no_charge_window`: Prevents the battery from charging from the grid during specified hours.
- `no_discharge_window`: Prevents the battery from discharging during specified hours.
- `max_grid_window`: Caps the maximum allowable power draw from the grid during specified hours.
- `no_op`: Used when a note is irrelevant, uninterpretable, or safely ignored.

## 7. Guardrails
Deterministic checks are enforced on the LLM output before it reaches the optimizer:
- **Allowed directive types**: Only the exact strings listed above are accepted.
- **Note mapping**: Every interpretation must map exactly 1:1 to the original operator notes array.
- **Hours**: Extracted hours must strictly fall within `0-23`.
- **Numeric ranges**: Percentages must be `0-100`, values must be positive, etc.
- **Applies semantics**: Validates the `applies` boolean flag logic.
- **No invention**: Rejects hallucinated constraints not present in the original notes.
- **Safe failure**: If a directive fails validation, it defaults to a safe `no_op` rather than crashing the pipeline.

## 8. Optimizer
The `PuLP`-based optimization engine formulates the problem as a linear program:
- **Cost objective**: Minimizes the total cost (BDT) of grid energy over 24 hours.
- **Energy balance**: Ensures that at every hour: `Grid + Solar + Battery_Discharge == Demand + Battery_Charge`.
- **Solar constraints**: Maximizes solar usage (curtailment is allowed but mathematically discouraged).
- **Battery transitions**: Tracks state-of-charge `Energy(t) == Energy(t-1) + Charge(t) - Discharge(t)`.
- **Capacity/minimum limits**: Keeps battery energy strictly between `minimum_energy_kwh` and `capacity_kwh`.
- **Charge/discharge limits**: Enforces `max_charge_kwh_per_hour` and `max_discharge_kwh_per_hour`.
- **End-of-day neutrality**: Requires the battery to end the 24-hour period at exactly the `initial_energy_kwh` to prevent borrowing from tomorrow.
- **Directive-specific constraints**: Dynamically injects constraints based on the validated LLM interpretations.

## 9. Project Structure
```text
.
├── Dockerfile            # Docker configuration for production
├── .env.example          # Template for environment variables
├── .dockerignore         # Docker exclusion list
├── .gitignore            # Git exclusion list
├── README.md             # This documentation
├── main.py               # FastAPI application and routes
├── models.py             # Pydantic data models and validation
├── llm_interpreter.py    # LLM API integration and caching
├── guardrails.py         # Deterministic LLM output validation
├── optimizer.py          # PuLP mathematical optimization model
├── validator.py          # Final output replay validation
├── requirements.txt      # Python dependencies
└── tests/
    └── test_public_samples.py # Test suite against official samples
```

## 10. Prerequisites
- Python 3.9 or higher
- Git
- Docker (optional, for containerized execution)
- A valid Google Gemini API key

## 11. Environment Variables
- `GEMINI_API_KEY`

## 12. Local Setup
```bash
# Clone the repository
git clone https://github.com/aunabil-abtahi/buphack_preli.git
cd buphack_preli

# Create and activate a virtual environment
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Configure environment variables
# (Copy the example file and add your GEMINI_API_KEY)
cp .env.example .env

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8080
```

## 13. Exact Run Command
```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

## 14. GET /health Example
```bash
curl -s http://localhost:8080/health
```
**Expected Response:**
```json
{"status": "ok"}
```

## 15. POST /optimize-energy Example
**Compact Request:**
```bash
curl -X POST http://localhost:8080/optimize-energy \
  -H "Content-Type: application/json" \
  -d '{
  "scenario_id": "TEST-01",
  "operator_notes": ["No charge window from 1 PM to 3 PM."],
  "battery": {
    "capacity_kwh": 500.0,
    "initial_energy_kwh": 100.0,
    "minimum_energy_kwh": 50.0,
    "max_charge_kwh_per_hour": 150.0,
    "max_discharge_kwh_per_hour": 150.0
  },
  "hours": [
    {"hour": 0, "demand_kwh": 100.0, "solar_kwh": 50.0, "tariff_bdt_per_kwh": 5.0}
  ]
}'
```
*(Note: A full valid request must contain exactly 24 elements in the `hours` array.)*

**Response Fields Explained:**
- `scenario_id`: Echoes the exact ID from the request.
- `directive_interpretation`: A 1:1 mapped list of how the system interpreted the `operator_notes`.
- `hourly_plan`: The hour-by-hour calculated operations (grid draw, battery charge/discharge).
- `total_grid_kwh`: Total energy drawn from the grid over 24 hours.
- `total_cost_bdt`: The optimized total cost.
- `peak_grid_kwh`: The maximum grid draw occurring in a single hour.
- `plan_summary`: A human-readable text summary of the results.

## 16. Public Sample Validation
You can run the official public sample test suite to verify the optimizer's logic locally.

```bash
python -m pytest tests/test_public_samples.py -v
```
**What a passing run means:**
A passing run indicates that the local optimizer correctly processed all provided official sample inputs. It validates that the LLM successfully interpreted the notes, the guardrails accepted the outputs, the optimizer found a mathematically feasible solution that is strictly cheaper (or equal) to a baseline "no-battery" scenario, and the replay validator successfully verified all physical battery constraints.

## 17. Docker
The repository includes a complete Docker configuration for containerized execution.

**Build the image:**
```bash
docker build -t gridwise:local .
```

**Run the container:**
*(Make sure to pass your API key as a runtime environment variable)*
```bash
docker run --rm -p 8080:8080 -e GEMINI_API_KEY=YOUR_API_KEY_HERE gridwise:local
```

**Verify health:**
```bash
curl -s http://localhost:8080/health
```

**Fallback Registry Image:**
*(Replace with actual registry URL if a pre-built image is provided via GitHub Container Registry or Docker Hub)*
`ghcr.io/aunabil-abtahi/buphack_preli:latest`

## 18. Deployment
The API is designed to be easily deployed to PaaS providers (e.g., Railway, Render). When deployed, the platform binds a dynamic port via the `$PORT` variable and injects the `GEMINI_API_KEY` from its UI dashboard. Both required endpoints (`/health` and `/optimize-energy`) are exposed directly at the root of the public base URL without authentication, ensuring automated judges can access them immediately.

## 19. Error Handling
- Invalid JSON payloads or missing fields result in a `422 Unprocessable Entity` with strict Pydantic validation details.
- Logical failures (e.g., missing exactly 24 hours, or battery physics impossibilities) result in standard HTTP `400 Bad Request` codes.
- Unexpected internal crashes, optimizer failures, or LLM quota limits (`429`) are caught by a global middleware which returns a sanitized `500 Internal Server Error`, guaranteeing that raw stack traces are never leaked to the client.

## 20. Security / Secret Handling
- **.env ignored**: The `.env` file is completely excluded via `.gitignore` and `.dockerignore`.
- **No baked-in secrets**: The `Dockerfile` does not copy environment variables during build time.
- **No API keys in logs/responses**: The global error middleware strips sensitive context, and API keys are never echoed back in JSON responses or raw stack traces.
- **Runtime environment variables**: Secrets are exclusively passed at runtime via the environment.

## 21. Dependencies / External Tools
- [FastAPI](https://fastapi.tiangolo.com/) - High-performance web framework
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [PuLP](https://coin-or.github.io/pulp/) - Linear Programming API
- [Google GenAI SDK](https://github.com/google/generative-ai-python) - LLM API client

## 22. Known Limitations
- The optimizer currently takes up to ~5-15 seconds per request depending on Gemini API latency.
- **Strict 24-hour limit**: The system does not support optimizing for time horizons less than or greater than 24 continuous hours.
- If the Gemini API hits rate limits (e.g., free tier `429 RESOURCE_EXHAUSTED`), the system cannot fallback to an offline model and will return a sanitized 500 error.

## 23. API Response Fields
The `/optimize-energy` endpoint returns the following structured JSON response:
- `scenario_id` (string)
- `directive_interpretation` (list of objects)
- `hourly_plan` (list of 24 objects)
- `total_grid_kwh` (float)
- `total_cost_bdt` (float)
- `peak_grid_kwh` (float)
- `plan_summary` (string)

## 24. Submission Checklist
- [x] Public endpoint deployed
- [x] `/health` endpoint returns 200 OK
- [x] `/optimize-energy` endpoint fully implemented
- [x] Private repo during event
- [x] Public repo after deadline according to rules
- [x] Complete self-contained README
- [x] Docker configuration included
- [ ] 3-minute presentation video (To be completed by team)
