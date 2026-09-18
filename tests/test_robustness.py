import sys
import os
import time

# Ensure imports work from parent dir
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import os
import copy

os.environ["GEMINI_API_KEY"] = "mock_key_for_testing"

from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch

client = TestClient(app)

valid_payload = {
  "scenario_id": "test-123",
  "operator_notes": ["No charge between 12 PM and 2 PM."],
  "hours": [
    {"hour": i, "demand_kwh": 50, "solar_kwh": 0, "tariff_bdt_per_kwh": 5.0} for i in range(24)
  ],
  "battery": {
    "capacity_kwh": 200,
    "initial_energy_kwh": 50,
    "max_charge_kwh_per_hour": 50,
    "max_discharge_kwh_per_hour": 50,
    "minimum_energy_kwh": 20
  }
}

def test_malformed_json():
    response = client.post("/optimize-energy", data="{malformed json")
    assert response.status_code == 400

def test_missing_scenario_id():
    payload = copy.deepcopy(valid_payload)
    del payload["scenario_id"]
    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 400

def test_operator_notes_empty():
    payload = copy.deepcopy(valid_payload)
    payload["operator_notes"] = []
    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 400

def test_operator_notes_empty_string():
    payload = copy.deepcopy(valid_payload)
    payload["operator_notes"] = ["  "]
    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 400

def test_operator_notes_too_many():
    payload = copy.deepcopy(valid_payload)
    payload["operator_notes"] = ["Note 1", "Note 2", "Note 3", "Note 4"]
    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 400

def test_missing_hour():
    payload = copy.deepcopy(valid_payload)
    payload["hours"] = payload["hours"][:-1]
    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 400

def test_duplicate_hour():
    payload = copy.deepcopy(valid_payload)
    payload["hours"][-1]["hour"] = 0
    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 400

def test_invalid_hour():
    payload = copy.deepcopy(valid_payload)
    payload["hours"][-1]["hour"] = 24
    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 400

def test_negative_battery_values():
    payload = copy.deepcopy(valid_payload)
    payload["battery"]["capacity_kwh"] = -10
    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 400

def test_battery_initial_above_capacity():
    payload = copy.deepcopy(valid_payload)
    payload["battery"]["initial_energy_kwh"] = 300
    response = client.post("/optimize-energy", json=payload)
    assert response.status_code == 400

@patch("main.interpret_notes")
def test_llm_provider_exception(mock_interpret):
    mock_interpret.side_effect = Exception("API down")
    response = client.post("/optimize-energy", json=valid_payload)
    print("response.json() =", response.json())
    assert response.status_code == 500

@patch("main.solve_energy_schedule")
@patch("main.interpret_notes")
def test_optimizer_failure(mock_interpret, mock_solve):
    from models import DirectiveInterpretation, StructuredAdjustment
    mock_interpret.return_value = [
        DirectiveInterpretation(
            note_index=0,
            applies=False,
            directive_type="no_op",
            explanation="None",
            structured_adjustment=None
        )
    ]
    
    from fastapi import HTTPException
    mock_solve.side_effect = HTTPException(status_code=400, detail="Infeasible")
    response = client.post("/optimize-energy", json=valid_payload)
    print("response.json() =", response.json())
    assert response.status_code == 400

def test_repeated_valid_requests():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
