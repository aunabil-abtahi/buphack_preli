import os
from typing import List
from google import genai
from pydantic import BaseModel
from models import DirectiveInterpretation

class LLMResponse(BaseModel):
    directive_interpretation: List[DirectiveInterpretation]

PROMPT_TEMPLATE = """
You are an expert energy scheduling assistant.
You will interpret each operator note into exactly one structured directive in the same order as provided.

Battery Capacity: {capacity} kWh (use this if notes mention a relative percentage of capacity for reserves)

Supported directive types:
1. solar_reduction: Reduce usable solar. "factor" is the usable fraction remaining (e.g. 80% reduction => factor = 0.2).
2. minimum_battery_reserve: Keep battery energy at or above "minimum_energy_kwh". 
3. no_charge_window: Battery charging is unavailable.
4. no_discharge_window: Battery discharging is unavailable.
5. max_grid_window: Grid import may not exceed "max_grid_kwh".
6. no_op: The note does not affect the current 24-hour energy schedule.

Rules:
- no_op => applies = false, structured_adjustment = null
- every non-no_op => applies = true
- time windows are start-inclusive and end-exclusive (e.g. 1 PM to 3 PM => [13,14])
- all hours must be integers 0-23
- irrelevant notes must become no_op
- never invent unsupported directive types
- never alter base demand, tariff, or battery limits unless a supported directive explicitly allows it

Operator Notes:
{notes}
"""

def interpret_notes(notes: List[str], capacity: float) -> List[DirectiveInterpretation]:
    client = genai.Client()
    
    notes_text = "\n".join([f"{i}. {note}" for i, note in enumerate(notes)])
    prompt = PROMPT_TEMPLATE.format(capacity=capacity, notes=notes_text)
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=LLMResponse,
            temperature=0.0
        ),
    )
    
    return response.parsed.directive_interpretation
