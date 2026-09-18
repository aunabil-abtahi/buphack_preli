from optimizer import solve_energy_schedule
from models import OptimizeRequest, HourInput, BatteryInput, DirectiveInterpretation, StructuredAdjustment
import math

def run_test():
    # 1. Create a dummy scenario
    hours = []
    for h in range(24):
        hours.append(HourInput(
            hour=h,
            demand_kwh=100.0,
            solar_kwh=50.0,
            tariff_bdt_per_kwh=10.0 if h < 12 else 20.0 # cheaper in first half
        ))
        
    battery = BatteryInput(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=20.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0
    )
    
    request = OptimizeRequest(
        scenario_id="TEST-01",
        operator_notes=["Do not charge from 2 PM to 4 PM"],
        hours=hours,
        battery=battery
    )
    
    # 2. Dummy directive interpretation
    interpretations = [
        DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type="no_charge_window",
            structured_adjustment=StructuredAdjustment(hours=[14, 15]),
            explanation="Test directive"
        )
    ]
    
    # 3. Solve
    print("Solving energy schedule...")
    plans = solve_energy_schedule(request, interpretations)
    
    print(f"Returned {len(plans)} hourly plan entries.")
    assert len(plans) == 24, "Did not return exactly 24 entries"
    
    # 4. Verify hour 23 battery energy equals initial energy
    last_energy = plans[23].battery_energy_after_kwh
    print(f"End of day battery energy: {last_energy} (Expected: {battery.initial_energy_kwh})")
    assert math.isclose(last_energy, battery.initial_energy_kwh, abs_tol=0.01), "End of day energy mismatch"
    
    # Check no charge window
    for h in [14, 15]:
        assert plans[h].battery_action != "charge", f"Battery charged during no_charge_window at hour {h}"
        
    print("Test passed successfully!")

if __name__ == "__main__":
    run_test()
