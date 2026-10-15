"""Forecasting engine generating future transfusion events from care plans."""
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

def generate_forecast_events(
    patient_id: str,
    last_transfusion_date: date,
    interval_days: int,
    units_per_session: int,
    centre_id: str,
    days_ahead: int = 90
) -> List[Dict[str, Any]]:
    """
    Projects recurring transfusion dates across the planning horizon.
    Generates structured TransfusionEvent candidate dictionaries.
    """
    events = []
    current_date = last_transfusion_date + timedelta(days=interval_days)
    end_date = date.today() + timedelta(days=days_ahead)

    event_counter = 1
    while current_date <= end_date:
        events.append({
            "event_id": f"EV-{patient_id}-{current_date.strftime('%Y%m%d')}",
            "patient_id": patient_id,
            "centre_id": centre_id,
            "planned_date": current_date.isoformat(),
            "units_required": units_per_session,
            "status": "PLANNED",
            "coverage_count": 0,
            "sequence_number": event_counter
        })
        event_counter += 1
        current_date += timedelta(days=interval_days)

    return events

def adjust_forecast_by_hemoglobin(
    base_interval: int,
    recent_pre_tx_hb: List[float],
    target_hb: float = 9.5
) -> int:
    """
    Adjusts standard interval if pre-transfusion Hb trends drop below 9.0-9.5 g/dL.
    Thalassemia major clinical management: maintaining pre-transfusion Hb around 9.5-10.0 g/dL.
    """
    if not recent_pre_tx_hb:
        return base_interval

    avg_hb = sum(recent_pre_tx_hb) / len(recent_pre_tx_hb)
    if avg_hb < 8.5:
        # Rapid drop, shorten interval by 3-4 days
        return max(14, base_interval - 4)
    elif avg_hb < target_hb:
        return max(14, base_interval - 2)
    elif avg_hb > 10.5:
        return min(35, base_interval + 2)
    return base_interval
