from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Literal

class HourInput(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    demand_kwh: float = Field(..., ge=0.0)
    solar_kwh: float = Field(..., ge=0.0)
    tariff_bdt_per_kwh: float = Field(..., ge=0.0)

class BatteryInput(BaseModel):
    capacity_kwh: float = Field(..., ge=0.0)
    initial_energy_kwh: float = Field(..., ge=0.0)
    minimum_energy_kwh: float = Field(..., ge=0.0)
    max_charge_kwh_per_hour: float = Field(..., ge=0.0)
    max_discharge_kwh_per_hour: float = Field(..., ge=0.0)

    @model_validator(mode='after')
    def check_battery_limits(self):
        if self.initial_energy_kwh > self.capacity_kwh:
            raise ValueError('initial_energy_kwh cannot exceed capacity_kwh')
        if self.minimum_energy_kwh > self.capacity_kwh:
            raise ValueError('minimum_energy_kwh cannot exceed capacity_kwh')
        return self

class OptimizeRequest(BaseModel):
    scenario_id: str = Field(..., min_length=1)
    operator_notes: List[str] = Field(..., min_length=1, max_length=3)
    hours: List[HourInput] = Field(..., min_length=24, max_length=24)
    battery: BatteryInput

    @field_validator('operator_notes')
    @classmethod
    def check_operator_notes_not_empty(cls, v):
        for note in v:
            if not note.strip():
                raise ValueError("operator_notes cannot contain empty strings")
        return v

    @field_validator('hours')
    @classmethod
    def check_hours_unique_and_sequential(cls, v):
        hours = [h.hour for h in v]
        if len(set(hours)) != 24:
            raise ValueError("hours must contain exactly 24 unique entries")
        if sorted(hours) != list(range(24)):
            raise ValueError("hours must contain all integers from 0 to 23")
        return v

class StructuredAdjustment(BaseModel):
    hours: List[int]
    factor: Optional[float] = None
    minimum_energy_kwh: Optional[float] = None
    max_grid_kwh: Optional[float] = None

class DirectiveInterpretation(BaseModel):
    note_index: int
    applies: bool
    directive_type: Literal[
        "solar_reduction", 
        "minimum_battery_reserve", 
        "no_charge_window", 
        "no_discharge_window", 
        "max_grid_window", 
        "no_op"
    ]
    structured_adjustment: Optional[StructuredAdjustment]
    explanation: str

class HourlyPlan(BaseModel):
    hour: int
    grid_kwh: float
    solar_used_kwh: float
    battery_action: Literal["charge", "discharge", "idle"]
    battery_kwh: float
    battery_energy_after_kwh: float

class OptimizeResponse(BaseModel):
    scenario_id: str
    directive_interpretation: List[DirectiveInterpretation]
    hourly_plan: List[HourlyPlan]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str
