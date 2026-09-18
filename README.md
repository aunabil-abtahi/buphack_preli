# GridWise Energy Optimization Challenge

This repository contains the solution for the GridWise Energy Optimization challenge. It provides an HTTP API service that accepts energy scheduling requests, interprets natural language operator notes into structured constraints using an LLM, applies deterministic guardrails, and uses a Mixed-Integer Linear Programming (MILP) solver to minimize grid electricity costs.

## Architecture

1. **API Layer**: FastAPI handles incoming requests and parses them into Pydantic models.
2. **LLM Interpretation**: `google-genai` with `gemini-3.5-flash` is used to translate unstructured operator notes into structured directives.
3. **Deterministic Guardrails**: The LLM output is validated to ensure validity, correct schema, valid hour constraints, and valid directive types.
4. **Optimization**: PuLP with the CBC solver determines the optimal 24-hour schedule (grid import, battery charge/discharge) to minimize energy cost, adhering to battery limits, effective solar caps, and any valid LLM-extracted directives.
5. **Validation/Replay**: The final schedule is replayed deterministically prior to returning to ensure complete compliance with physical and challenge rules.

## Requirements & Environment Variables

- Python 3.9+
- `GEMINI_API_KEY`: Required to access the Google Gemini API.

## Setup & Quickstart

Clone the repository and navigate into the directory:

```bash
git clone https://github.com/<YOUR_USERNAME>/buphack_preli.git
cd buphack_preli
```

Create and activate a virtual environment:
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate
```

Install the required dependencies:
```bash
pip install -r requirements.txt
```

Set the required environment variables. You can create a `.env` file in the root directory (do not commit this):
```env
GEMINI_API_KEY=your_actual_api_key_here
```

## Running the Service

Start the FastAPI service using Uvicorn on port 8080:

```bash
uvicorn main:app --env-file .env --port 8080
```
*(If running through Docker, follow the instructions in the Docker section below).*

## Testing Endpoints

### 1. Health Test
Verify the service is running:
```bash
curl http://localhost:8080/health
```
**Expected Response:**
```json
{"status":"ok"}
```

### 2. Optimize Energy Sample Test
```bash
curl -X POST http://localhost:8080/optimize-energy \
-H "Content-Type: application/json" \
-d '{
  "scenario_id": "test-123",
  "operator_notes": ["Battery charging is disabled between 12 PM and 2 PM."],
  "hours": [
    {"hour": 0, "demand_kwh": 50, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0},
    {"hour": 1, "demand_kwh": 40, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0},
    {"hour": 2, "demand_kwh": 40, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0},
    {"hour": 3, "demand_kwh": 40, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0},
    {"hour": 4, "demand_kwh": 40, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0},
    {"hour": 5, "demand_kwh": 40, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0},
    {"hour": 6, "demand_kwh": 50, "solar_kwh": 10, "tariff_bdt_per_kwh": 6.0},
    {"hour": 7, "demand_kwh": 60, "solar_kwh": 20, "tariff_bdt_per_kwh": 6.0},
    {"hour": 8, "demand_kwh": 70, "solar_kwh": 40, "tariff_bdt_per_kwh": 7.0},
    {"hour": 9, "demand_kwh": 80, "solar_kwh": 60, "tariff_bdt_per_kwh": 7.0},
    {"hour": 10, "demand_kwh": 90, "solar_kwh": 80, "tariff_bdt_per_kwh": 8.0},
    {"hour": 11, "demand_kwh": 90, "solar_kwh": 90, "tariff_bdt_per_kwh": 8.0},
    {"hour": 12, "demand_kwh": 80, "solar_kwh": 100, "tariff_bdt_per_kwh": 8.0},
    {"hour": 13, "demand_kwh": 80, "solar_kwh": 90, "tariff_bdt_per_kwh": 8.0},
    {"hour": 14, "demand_kwh": 90, "solar_kwh": 80, "tariff_bdt_per_kwh": 8.0},
    {"hour": 15, "demand_kwh": 100, "solar_kwh": 60, "tariff_bdt_per_kwh": 8.0},
    {"hour": 16, "demand_kwh": 110, "solar_kwh": 40, "tariff_bdt_per_kwh": 9.0},
    {"hour": 17, "demand_kwh": 120, "solar_kwh": 20, "tariff_bdt_per_kwh": 9.0},
    {"hour": 18, "demand_kwh": 130, "solar_kwh": 0, "tariff_bdt_per_kwh": 10.0},
    {"hour": 19, "demand_kwh": 120, "solar_kwh": 0, "tariff_bdt_per_kwh": 10.0},
    {"hour": 20, "demand_kwh": 100, "solar_kwh": 0, "tariff_bdt_per_kwh": 9.0},
    {"hour": 21, "demand_kwh": 80, "solar_kwh": 0, "tariff_bdt_per_kwh": 7.0},
    {"hour": 22, "demand_kwh": 60, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0},
    {"hour": 23, "demand_kwh": 50, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0}
  ],
  "battery": {
    "capacity_kwh": 200,
    "initial_energy_kwh": 50,
    "max_charge_kwh_per_hour": 50,
    "max_discharge_kwh_per_hour": 50,
    "minimum_energy_kwh": 20
  }
}'
```

You can also run the comprehensive public test suite:
```bash
python tests/test_public_samples.py
```

## Docker Fallback

A Dockerfile is provided as a fallback execution environment. To build and run:

1. Build the image:
```bash
docker build -t gridwise-solution .
```

2. Run the container:
```bash
docker run -d -p 8080:8080 -e GEMINI_API_KEY="your_actual_api_key_here" gridwise-solution
```

## Known Limitations
- The system relies on the Gemini API (`gemini-3.5-flash`), which requires internet access. If the API rate-limits the connection, an internal exponential backoff retry handles it up to 5 times.
- The CBC MILP solver operates optimally within the standard absolute tolerance (0.01) required by the problem statement.
