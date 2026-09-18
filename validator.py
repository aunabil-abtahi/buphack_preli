from typing import List
from models import OptimizeRequest, DirectiveInterpretation, HourlyPlan
from fastapi import HTTPException
import math

def validate_schedule(request: OptimizeRequest, directives: List[DirectiveInterpretation], plan: List[HourlyPlan]):
    # 1. & 2. 24 entries, unique 0-23
    if len(plan) != 24:
        raise HTTPException(status_code=422, detail="hourly_plan must contain exactly 24 entries.")
    
    hours_seen = set()
    for h_entry in plan:
        hours_seen.add(h_entry.hour)
    if hours_seen != set(range(24)):
        raise HTTPException(status_code=422, detail="Hours must be unique and exactly 0 through 23.")
        
    # Sort plan to process chronologically just in case
    plan = sorted(plan, key=lambda x: x.hour)
    
    bat = request.battery
    current_energy = bat.initial_energy_kwh
    tol = 0.01

    # Arrays for bounds
    effective_solar = [h.solar_kwh for h in request.hours]
    min_reserve = [bat.minimum_energy_kwh for _ in range(24)]
    max_charge = [bat.max_charge_kwh_per_hour for _ in range(24)]
    max_discharge = [bat.max_discharge_kwh_per_hour for _ in range(24)]
    max_grid = [float('inf') for _ in range(24)]
    
    # 4. Recompute directives
    for d in directives:
        if not d.applies or d.directive_type == "no_op":
            continue
        
        adj = d.structured_adjustment
        for hr in adj.hours:
            if d.directive_type == "solar_reduction":
                effective_solar[hr] *= adj.factor
            elif d.directive_type == "minimum_battery_reserve":
                min_reserve[hr] = max(min_reserve[hr], adj.minimum_energy_kwh)
            elif d.directive_type == "no_charge_window":
                max_charge[hr] = 0.0
            elif d.directive_type == "no_discharge_window":
                max_discharge[hr] = 0.0
            elif d.directive_type == "max_grid_window":
                max_grid[hr] = min(max_grid[hr], adj.max_grid_kwh)
                
    for h in range(24):
        p = plan[h]
        req = request.hours[h]
        
        # 3. Finite and non-negative
        if p.grid_kwh < -tol or p.solar_used_kwh < -tol or p.battery_kwh < -tol:
            raise HTTPException(status_code=422, detail=f"Numeric values must be non-negative at hour {h}.")
        
        # 5. Solar usage <= effective solar
        if p.solar_used_kwh > effective_solar[h] + tol:
            raise HTTPException(status_code=422, detail=f"Solar usage exceeded effective solar at hour {h}.")
            
        # 6. Recompute battery state
        charge_kwh = 0.0
        discharge_kwh = 0.0
        if p.battery_action == "charge":
            charge_kwh = p.battery_kwh
            expected_energy_after = current_energy + charge_kwh
        elif p.battery_action == "discharge":
            discharge_kwh = p.battery_kwh
            expected_energy_after = current_energy - discharge_kwh
        elif p.battery_action == "idle":
            if p.battery_kwh > tol:
                raise HTTPException(status_code=422, detail=f"Idle action must have battery_kwh = 0 at hour {h}.")
            expected_energy_after = current_energy
        else:
            raise HTTPException(status_code=422, detail=f"Invalid battery action at hour {h}.")
            
        # 7. Verify battery_energy_after_kwh matches
        if not math.isclose(p.battery_energy_after_kwh, expected_energy_after, abs_tol=tol):
            raise HTTPException(status_code=422, detail=f"Battery state transition mismatch at hour {h}. Expected {expected_energy_after}, got {p.battery_energy_after_kwh}")
        current_energy = p.battery_energy_after_kwh
            
        # 8. Battery bounds
        if p.battery_energy_after_kwh < min_reserve[h] - tol:
            raise HTTPException(status_code=422, detail=f"Battery energy fell below minimum reserve at hour {h}.")
        if p.battery_energy_after_kwh > bat.capacity_kwh + tol:
            raise HTTPException(status_code=422, detail=f"Battery energy exceeded capacity at hour {h}.")
            
        # 9. & 10. Rate limits
        if charge_kwh > max_charge[h] + tol:
            raise HTTPException(status_code=422, detail=f"Max charge rate exceeded at hour {h}.")
        if discharge_kwh > max_discharge[h] + tol:
            raise HTTPException(status_code=422, detail=f"Max discharge rate exceeded at hour {h}.")
            
        # 11. Energy balance
        lhs = p.grid_kwh + p.solar_used_kwh + discharge_kwh
        rhs = req.demand_kwh + charge_kwh
        if not math.isclose(lhs, rhs, abs_tol=tol):
            raise HTTPException(status_code=422, detail=f"Energy balance failed at hour {h}: supply={lhs}, demand={rhs}.")
            
        # 15. Max grid window
        if p.grid_kwh > max_grid[h] + tol:
            raise HTTPException(status_code=422, detail=f"Max grid limit exceeded at hour {h}.")
            
    # 16. End of day neutrality
    if not math.isclose(current_energy, bat.initial_energy_kwh, abs_tol=tol):
        raise HTTPException(status_code=422, detail=f"Battery did not return to initial energy state. Expected {bat.initial_energy_kwh}, got {current_energy}")
