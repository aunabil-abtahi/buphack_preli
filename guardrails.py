from typing import List
from models import DirectiveInterpretation, OptimizeRequest
from fastapi import HTTPException

def validate_interpretations(interpretations: List[DirectiveInterpretation], request: OptimizeRequest) -> List[DirectiveInterpretation]:
    if len(interpretations) != len(request.operator_notes):
        raise HTTPException(status_code=422, detail="exactly one interpretation per operator note is required")
        
    for i, interp in enumerate(interpretations):
        if interp.note_index != i:
            raise HTTPException(status_code=422, detail="note_index must map to an existing note and return order must be 0..N-1")
            
        if interp.directive_type == "no_op":
            if interp.applies is not False or interp.structured_adjustment is not None:
                raise HTTPException(status_code=422, detail="no_op must use applies=false and structured_adjustment=null")
        else:
            if interp.applies is not True or interp.structured_adjustment is None:
                raise HTTPException(status_code=422, detail="all non-no_op directives must use applies=true and the exact required structured_adjustment shape")
                
            adj = interp.structured_adjustment
            hours = adj.hours
            if not hours:
                raise HTTPException(status_code=422, detail="hours must be unique integers 0-23")
                
            if len(set(hours)) != len(hours) or any(h < 0 or h > 23 for h in hours):
                raise HTTPException(status_code=422, detail="hours must be unique integers 0-23")
                
            if sorted(hours) != hours:
                raise HTTPException(status_code=422, detail="hours must be sorted ascending")
                
            if interp.directive_type == "solar_reduction":
                if adj.factor is None or not (0.0 <= adj.factor <= 1.0):
                    raise HTTPException(status_code=422, detail="solar_reduction factor must be finite and between 0 and 1")
            elif interp.directive_type == "minimum_battery_reserve":
                if adj.minimum_energy_kwh is None or adj.minimum_energy_kwh < 0 or adj.minimum_energy_kwh > request.battery.capacity_kwh:
                    raise HTTPException(status_code=422, detail="minimum_battery_reserve must be finite, non-negative, and <= battery capacity")
            elif interp.directive_type == "max_grid_window":
                if adj.max_grid_kwh is None or adj.max_grid_kwh < 0:
                    raise HTTPException(status_code=422, detail="max_grid_kwh must be finite and non-negative")
                    
    return interpretations
