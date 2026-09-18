# GridWise Optimization API

This is an LLM-assisted HTTP API service for the GridWise Smart Campus Energy Optimization challenge. It interprets natural language operator notes into structured directives, validates them, and calculates an optimal 24-hour battery schedule to minimize grid cost.

## Setup & Local Quickstart

### Prerequisites
- Python 3.10+
- A valid Google Gemini API Key (`GEMINI_API_KEY`)

### Installation (Local)
1. Clone the repository and navigate into the root directory.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your Gemini API key:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```
   *(On Windows PowerShell, use `$env:GEMINI_API_KEY="your-api-key-here"`)*
4. Start the service:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

### Docker Fallback (Public API URL Recommended)
1. Build the image:
   ```bash
   docker build -t gridwise-api .
   ```
2. Run the container:
   ```bash
   docker run -d -p 8000:8000 -e GEMINI_API_KEY="your-api-key-here" gridwise-api
   ```

## Endpoints

### `GET /health`
Verifies the service is running.
```bash
curl http://localhost:8000/health
```
**Expected Response:** `{"status": "ok"}`

### `POST /optimize-energy`
Main endpoint for interpreting operator notes and optimizing the 24-hour schedule.
*(Check the public JSON sample cases for complete request/response examples).*

## Architecture Overview
- **LLM/Provider:** Gemini 2.5 Flash via `google-genai` SDK.
- **LLM Role:** Converts unstructured operator notes into standard structured JSON directives (`solar_reduction`, `no_charge_window`, etc.).
- **Guardrails:** Pydantic validators (`app/guardrails.py`) strictly enforce schema, bounds, and ordering.
- **Optimizer:** `PuLP` is used as the linear programming solver. It models the battery state, energy limits, and directives as constraints while minimizing total grid electricity cost.
- **Final Validation:** The generated schedule is independently re-checked against all battery limits, energy equations, and ground-truth directive limits before being returned.

## Testing with Public Samples
Run the included test script to validate the service locally against the provided JSON samples.
```bash
python test_public_samples.py
```
*(Make sure the API is running on port 8000 and you have `requests` installed).*

## Known Limitations
- Network latency to the Gemini API may cause responses to exceed the 30s timeout if the provider is degraded.
- Assumes the time constraints provided in operator notes strictly map to full hour slots as defined by the problem statement.
