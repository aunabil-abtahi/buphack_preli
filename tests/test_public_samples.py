import os
import sys
import json
import math
import requests

def validate_interpretations(actual_interps, expected_interps):
    if len(actual_interps) != len(expected_interps):
        return False, f"Expected {len(expected_interps)} interpretations, got {len(actual_interps)}"
    
    for i, (actual, expected) in enumerate(zip(actual_interps, expected_interps)):
        if actual.get("note_index") != i:
            return False, f"note_index out of order at index {i}"
        
        if actual.get("applies") != expected.get("applies"):
            return False, f"Mismatch in 'applies' at note {i}"
            
        if actual.get("directive_type") != expected.get("directive_type"):
            return False, f"Mismatch in 'directive_type' at note {i}"
            
        act_adj = actual.get("structured_adjustment")
        exp_adj = expected.get("structured_adjustment")
        
        if exp_adj is None:
            if act_adj is not None:
                return False, f"Expected null structured_adjustment at note {i}"
        else:
            if act_adj is None:
                return False, f"Expected structured_adjustment at note {i}"
            
            if act_adj.get("hours") != exp_adj.get("hours"):
                return False, f"Mismatch in 'hours' at note {i}"
                
            for key, val in exp_adj.items():
                if key == "hours":
                    continue
                act_val = act_adj.get(key)
                if act_val is None or not math.isclose(val, act_val, abs_tol=0.01):
                    return False, f"Mismatch in adjustment field '{key}' at note {i}"
                    
    return True, "Interpretations match."

def replay_plan(request_data, plan, interpretations):
    if len(plan) != 24:
        return False, "Plan length is not exactly 24"
        
    bat = request_data["battery"]
    current_energy = bat["initial_energy_kwh"]
    
    effective_solar = [h["solar_kwh"] for h in request_data["hours"]]
    min_reserve = [bat["minimum_energy_kwh"] for _ in range(24)]
    max_charge = [bat["max_charge_kwh_per_hour"] for _ in range(24)]
    max_discharge = [bat["max_discharge_kwh_per_hour"] for _ in range(24)]
    max_grid = [float('inf') for _ in range(24)]
    
    for interp in interpretations:
        if not interp.get("applies") or interp.get("directive_type") == "no_op":
            continue
        
        adj = interp.get("structured_adjustment")
        for hr in adj["hours"]:
            d_type = interp.get("directive_type")
            if d_type == "solar_reduction":
                effective_solar[hr] *= adj["factor"]
            elif d_type == "minimum_battery_reserve":
                min_reserve[hr] = max(min_reserve[hr], adj["minimum_energy_kwh"])
            elif d_type == "no_charge_window":
                max_charge[hr] = 0.0
            elif d_type == "no_discharge_window":
                max_discharge[hr] = 0.0
            elif d_type == "max_grid_window":
                max_grid[hr] = min(max_grid[hr], adj["max_grid_kwh"])

    tol = 0.01
    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0

    for h in range(24):
        p = plan[h]
        req = request_data["hours"][h]
        
        if p.get("hour") != h:
            return False, f"Hour index mismatch at {h}"
            
        g = p.get("grid_kwh", 0)
        s = p.get("solar_used_kwh", 0)
        b_action = p.get("battery_action")
        b_val = p.get("battery_kwh", 0)
        e_after = p.get("battery_energy_after_kwh", 0)
        
        total_grid += g
        total_cost += g * req["tariff_bdt_per_kwh"]
        if g > peak_grid:
            peak_grid = g

        if g < -tol or s < -tol or b_val < -tol:
            return False, f"Negative value at hour {h}"
            
        if s > effective_solar[h] + tol:
            return False, f"Solar usage exceeded effective solar at hour {h}"
            
        c_kwh = b_val if b_action == "charge" else 0.0
        d_kwh = b_val if b_action == "discharge" else 0.0
        
        if b_action == "idle" and b_val > tol:
            return False, f"Idle action with non-zero battery_kwh at hour {h}"
            
        expected_e_after = current_energy + c_kwh - d_kwh
        if not math.isclose(e_after, expected_e_after, abs_tol=tol):
            return False, f"Battery state mismatch at hour {h}"
        current_energy = e_after
        
        if e_after < min_reserve[h] - tol:
            return False, f"Battery fell below min reserve at hour {h}"
        if e_after > bat["capacity_kwh"] + tol:
            return False, f"Battery exceeded capacity at hour {h}"
            
        if c_kwh > max_charge[h] + tol:
            return False, f"Max charge exceeded at hour {h}"
        if d_kwh > max_discharge[h] + tol:
            return False, f"Max discharge exceeded at hour {h}"
            
        lhs = g + s + d_kwh
        rhs = req["demand_kwh"] + c_kwh
        if not math.isclose(lhs, rhs, abs_tol=tol):
            return False, f"Energy balance failed at hour {h}"
            
        if g > max_grid[h] + tol:
            return False, f"Max grid limit exceeded at hour {h}"

    if not math.isclose(current_energy, bat["initial_energy_kwh"], abs_tol=tol):
        return False, "Battery neutrality failed at end of day"

    return True, {"total_grid": total_grid, "total_cost": total_cost, "peak_grid": peak_grid}

def run_all_tests():
    data_file = "public_cases.json"
    if not os.path.exists(data_file):
        data_file = "../public_cases.json"
    if not os.path.exists(data_file):
        print("Error: public_cases.json not found")
        return
        
    with open(data_file, "r") as f:
        cases = json.load(f)["cases"]
        
    api_url = "http://localhost:8080/optimize-energy"
    
    print(f"{'Case ID':<15} | {'Interpretation':<15} | {'Schedule':<10} | {'Ret Cost':<10} | {'Ref Cost':<10} | {'Overall':<10} | {'Reason'}")
    print("-" * 100)
    
    total_elapsed_time = 0.0
    successful_calls = 0

    for case in cases:
        case_id = case["id"]
        req_data = case["input"]
        expected = case["expected_output"]
        
        try:
            import time
            time.sleep(2)
            start_time = time.time()
            resp = requests.post(api_url, json=req_data, timeout=60)
            elapsed = time.time() - start_time
            
            if resp.status_code != 200:
                print(f"{case_id:<15} | FAIL            | FAIL       | N/A        | {expected['total_cost_bdt']:<10} | FAIL       | HTTP {resp.status_code}: {resp.text}")
                continue
            
            total_elapsed_time += elapsed
            successful_calls += 1
            
            data = resp.json()
            
            if data.get("scenario_id") != req_data["scenario_id"]:
                print(f"{case_id:<15} | FAIL            | N/A        | N/A        | {expected['total_cost_bdt']:<10} | FAIL       | scenario_id mismatch")
                continue
                
            # Test interpretation
            i_pass, i_msg = validate_interpretations(data.get("directive_interpretation", []), expected.get("directive_interpretation", []))
            
            # Test schedule
            s_pass, s_result = replay_plan(req_data, data.get("hourly_plan", []), data.get("directive_interpretation", []))
            
            if not s_pass:
                print(f"{case_id:<15} | {'PASS' if i_pass else 'FAIL':<15} | FAIL       | N/A        | {expected['total_cost_bdt']:<10} | FAIL       | {s_result}")
                continue
                
            # Verify totals
            calc_cost = s_result["total_cost"]
            ret_cost = data.get("total_cost_bdt")
            ref_cost = expected["total_cost_bdt"]
            
            cost_match = math.isclose(calc_cost, ret_cost, abs_tol=0.01)
            optimal_match = math.isclose(ret_cost, ref_cost, abs_tol=0.01)
            
            overall = "PASS" if (i_pass and s_pass and cost_match and optimal_match) else "FAIL"
            reason = i_msg if not i_pass else ("Cost mismatch" if not cost_match else ("Suboptimal" if not optimal_match else "OK"))
            
            print(f"{case_id:<15} | {'PASS' if i_pass else 'FAIL':<15} | {'PASS' if s_pass else 'FAIL':<10} | {ret_cost:<10.2f} | {ref_cost:<10.2f} | {overall:<10} | {reason}")
            
        except Exception as e:
            print(f"{case_id:<15} | ERROR           | ERROR      | N/A        | {expected['total_cost_bdt']:<10} | FAIL       | Exception: {e}")

    if successful_calls > 0:
        avg_time = total_elapsed_time / successful_calls
        print(f"\nAverage local response time: {avg_time:.2f} seconds")

if __name__ == "__main__":
    run_all_tests()
