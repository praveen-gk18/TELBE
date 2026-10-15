"""Notification and confirmation timeline management."""
from datetime import date, timedelta
from typing import Dict, Any, List

class NotifierService:
    @staticmethod
    def build_invitation_message(event_date: str, centre_name: str, recipient_blood_group: str) -> str:
        """
        Creates privacy-compliant invitation text.
        NEVER discloses patient name, age, or medical diagnosis.
        """
        return (
            f"Transfusion Support Request: A pediatric patient at {centre_name} "
            f"needs {recipient_blood_group} blood around {event_date}. "
            f"Are you available to donate and help save a life?"
        )

    @staticmethod
    def get_timeline_status(days_until_event: int, coverage_ratio: float) -> Dict[str, Any]:
        """
        Evaluates event timeline status according to protocol:
        D-14: Primary invites
        D-10: Reminder / Backup invite on decline
        D-7: Slot confirmation
        D-3: Coverage check -> Escalate if < 100%
        D-1: Final prep reminder
        """
        if days_until_event > 14:
            stage = "EARLY_PLANNING"
            action = "Scheduled for batch invitation at D-14"
        elif days_until_event > 10:
            stage = "PRIMARY_INVITES"
            action = "Primary donor invitations active"
        elif days_until_event > 7:
            stage = "CONFIRMATION_CHECK"
            action = "Sending follow-ups and engaging backups if declined"
        elif days_until_event > 3:
            stage = "PRE_TRANSFUSION_LOCK"
            action = "Final slot confirmations being locked"
        elif days_until_event >= 0:
            if coverage_ratio >= 1.0:
                stage = "READY"
                action = "100% coverage secured, pre-donation reminders dispatched"
            else:
                stage = "ESCALATED_AT_RISK"
                action = "Critical gap inside D-3 window! Escalation activated"
        else:
            stage = "PAST_EVENT"
            action = "Transfusion event completed"

        return {
            "stage": stage,
            "action": action,
            "days_until_event": days_until_event,
            "coverage_ratio": coverage_ratio,
            "is_at_risk": days_until_event <= 3 and coverage_ratio < 1.0
        }
