"""Escalation Engine - handles dropouts, D-3 coverage deficits and coordinator alerts."""
from datetime import date
from typing import Dict, Any, List, Optional

class EscalationEngine:
    def __init__(self, matcher_engine=None):
        self.matcher = matcher_engine

    def evaluate_escalation(
        self,
        event: Dict[str, Any],
        invitations: List[Dict[str, Any]],
        today: date
    ) -> Optional[Dict[str, Any]]:
        """
        Triggers tiered escalation if:
        1. Days until event <= 3 and confirmed_count < units_required
        2. A confirmed donor cancels
        3. No-show on the day of donation
        """
        event_date = date.fromisoformat(event["planned_date"])
        days_left = (event_date - today).days
        units_required = event.get("units_required", 2)
        
        confirmed_count = sum(1 for inv in invitations if inv.get("status") in ["ACCEPTED", "CONFIRMED"])
        declined_count = sum(1 for inv in invitations if inv.get("status") == "DECLINED")
        cancelled_count = sum(1 for inv in invitations if inv.get("status") == "CANCELLED")

        # Condition 1: D-3 Coverage Deficit
        if days_left <= 3 and confirmed_count < units_required:
            shortage = units_required - confirmed_count
            level = 1 if days_left == 3 else (2 if days_left in [1, 2] else 3)
            return {
                "event_id": event["event_id"],
                "trigger": f"COVERAGE_GAP_D_{days_left}",
                "level": level,
                "urgency": "HIGH" if level >= 2 else "MEDIUM",
                "units_short": shortage,
                "recommended_actions": [
                    "1. Auto-dispatch urgent invites to designated backup donors",
                    "2. Widen donor travel radius by +15 km",
                    "3. Open matching to compatible ABO groups (e.g. O+ for B+)",
                    "4. Coordinator manual notification alert",
                    "5. Cross-check regional Blood Bank buffer inventory"
                ]
            }

        # Condition 2: Recent Cancellation
        if cancelled_count > 0 and confirmed_count < units_required:
            return {
                "event_id": event["event_id"],
                "trigger": "DONOR_CANCELLED",
                "level": 2,
                "urgency": "HIGH",
                "units_short": units_required - confirmed_count,
                "recommended_actions": [
                    "Activate immediate replacement from ranked backup queue",
                    "Alert coordinator to oversee confirmation"
                ]
            }

        return None
