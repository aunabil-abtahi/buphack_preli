from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpStatusOptimal, value
from models import OptimizeRequest, DirectiveInterpretation, HourlyPlan
from typing import List
from fastapi import HTTPException

def solve_energy_schedule(request_data: OptimizeRequest, interpreted_directives: List[DirectiveInterpretation]) -> List[HourlyPlan]:
    prob = LpProblem("GridWise_Optimization", LpMinimize)
    
    bat = request_data.battery
    n_hours = 24
    
    # 1. Effective solar & Directive setup
    effective_solar = [h.solar_kwh for h in request_data.hours]
    min_reserve = [bat.minimum_energy_kwh for _ in range(n_hours)]
    max_charge = [bat.max_charge_kwh_per_hour for _ in range(n_hours)]
    max_discharge = [bat.max_discharge_kwh_per_hour for _ in range(n_hours)]
    max_grid = [None for _ in range(n_hours)]
    
    for interp in interpreted_directives:
        if not interp.applies or interp.directive_type == "no_op":
            continue
            
        adj = interp.structured_adjustment
        for hr in adj.hours:
            if interp.directive_type == "solar_reduction":
                effective_solar[hr] *= adj.factor
            elif interp.directive_type == "minimum_battery_reserve":
                min_reserve[hr] = max(min_reserve[hr], adj.minimum_energy_kwh)
            elif interp.directive_type == "no_charge_window":
                max_charge[hr] = 0.0
            elif interp.directive_type == "no_discharge_window":
                max_discharge[hr] = 0.0
            elif interp.directive_type == "max_grid_window":
                if max_grid[hr] is None:
                    max_grid[hr] = adj.max_grid_kwh
                else:
                    max_grid[hr] = min(max_grid[hr], adj.max_grid_kwh)

    # 2. Variables
    grid_vars = []
    solar_vars = []
    charge_vars = []
    discharge_vars = []
    battery_vars = []
    
    for h in range(n_hours):
        grid_vars.append(LpVariable(f"grid_{h}", lowBound=0))
        solar_vars.append(LpVariable(f"solar_used_{h}", lowBound=0, upBound=effective_solar[h]))
        charge_vars.append(LpVariable(f"charge_{h}", lowBound=0, upBound=max_charge[h]))
        discharge_vars.append(LpVariable(f"discharge_{h}", lowBound=0, upBound=max_discharge[h]))
        battery_vars.append(LpVariable(f"battery_after_{h}", lowBound=min_reserve[h], upBound=bat.capacity_kwh))

    # 8. Max grid window constraint
    for h in range(n_hours):
        if max_grid[h] is not None:
            prob += grid_vars[h] <= max_grid[h], f"Max_Grid_{h}"

    # 3. Energy balance & 4. Battery state transition
    for h in range(n_hours):
        prob += (grid_vars[h] + solar_vars[h] + discharge_vars[h] == request_data.hours[h].demand_kwh + charge_vars[h], f"Energy_Balance_{h}")
        
        if h == 0:
            prob += (battery_vars[h] == bat.initial_energy_kwh + charge_vars[h] - discharge_vars[h], f"Battery_State_{h}")
        else:
            prob += (battery_vars[h] == battery_vars[h-1] + charge_vars[h] - discharge_vars[h], f"Battery_State_{h}")

    # 9. End-of-day neutrality
    prob += (battery_vars[n_hours - 1] == bat.initial_energy_kwh, "End_Of_Day_Neutrality")

    # 10. Objective
    prob += lpSum([grid_vars[h] * request_data.hours[h].tariff_bdt_per_kwh for h in range(n_hours)])

    # Solve
    prob.solve()

    # 11. Solver result validation
    if prob.status != LpStatusOptimal:
        raise HTTPException(status_code=400, detail="Optimization failed: Infeasible or unbounded constraints.")

    # 12. Output mapping
    hourly_plans = []
    tol = 1e-4
    
    for h in range(n_hours):
        g_val = max(0.0, value(grid_vars[h]))
        s_val = max(0.0, value(solar_vars[h]))
        c_val = max(0.0, value(charge_vars[h]))
        d_val = max(0.0, value(discharge_vars[h]))
        b_val = max(0.0, value(battery_vars[h]))

        # Net out any simultaneous charge/discharge (should be 0 due to LP cost, but to be safe)
        net_charge = c_val - d_val
        
        if net_charge > tol:
            action = "charge"
            action_kwh = net_charge
        elif net_charge < -tol:
            action = "discharge"
            action_kwh = -net_charge
        else:
            action = "idle"
            action_kwh = 0.0

        hourly_plans.append(HourlyPlan(
            hour=h,
            grid_kwh=round(g_val, 4),
            solar_used_kwh=round(s_val, 4),
            battery_action=action,
            battery_kwh=round(action_kwh, 4),
            battery_energy_after_kwh=round(b_val, 4)
        ))

    return hourly_plans
