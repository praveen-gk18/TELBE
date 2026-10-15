"""Eligibility Engine enforcing national blood transfusion guidelines (NBTC India)."""
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, Tuple

class EligibilityEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # Default NBTC guidelines
        self.config = {
            "min_age": 18,
            "max_age": 65,
            "min_weight_kg": 45.0,
            "male_interval_days": 90,    # 3 months
            "female_interval_days": 120, # 4 months
            "max_donations_per_year_male": 4,
            "max_donations_per_year_female": 3,
        }
        if config:
            self.config.update(config)

    def calculate_eligible_from(
        self,
        sex: str,
        last_donation_date: Optional[date],
        active_deferral_until: Optional[date] = None,
        donations_past_year_count: int = 0
    ) -> Tuple[date, str]:
        """
        Calculates the earliest date a donor is legally and clinically eligible to donate.
        Returns (eligible_from_date, reason_string).
        """
        today = date.today()
        candidates = [today]
        reasons = ["Eligible immediately"]

        # Gender interval check
        interval = self.config["male_interval_days"] if sex.upper() == "M" else self.config["female_interval_days"]
        if last_donation_date:
            min_gap_date = last_donation_date + timedelta(days=interval)
            candidates.append(min_gap_date)
            if min_gap_date > today:
                reasons.append(f"Requires {interval}-day gap from last donation on {last_donation_date}")

        # Active deferrals (e.g. tattoo, travel, medication)
        if active_deferral_until and active_deferral_until > today:
            candidates.append(active_deferral_until)
            reasons.append(f"Deferred until {active_deferral_until}")

        # Annual donation cap check
        max_annual = self.config["max_donations_per_year_male"] if sex.upper() == "M" else self.config["max_donations_per_year_female"]
        if donations_past_year_count >= max_annual:
            # Pushed to anniversary of oldest donation in the past year or 90 days
            blocked_until = today + timedelta(days=90)
            candidates.append(blocked_until)
            reasons.append(f"Annual donation limit ({max_annual}) reached")

        eligible_date = max(candidates)
        reason = "; ".join(reasons) if eligible_date > today else "Ready to donate"
        return eligible_date, reason

    def check_eligibility_for_event(
        self,
        donor: Dict[str, Any],
        event_date: date,
        active_deferral_until: Optional[date] = None,
        donations_past_year_count: int = 0
    ) -> Tuple[bool, str, date]:
        """Check if donor will be eligible on a target transfusion/event date."""
        # Age check
        dob = donor.get("dob")
        if dob:
            if isinstance(dob, str):
                dob = date.fromisoformat(dob)
            age = (event_date - dob).days // 365
            if age < self.config["min_age"] or age > self.config["max_age"]:
                return False, f"Age {age} outside permitted window ({self.config['min_age']}-{self.config['max_age']})", event_date

        # Weight check
        weight = donor.get("weight", 0.0)
        if weight < self.config["min_weight_kg"]:
            return False, f"Weight {weight}kg below minimum threshold {self.config['min_weight_kg']}kg", event_date

        # Interval and deferral check
        last_donation = donor.get("last_donation_date")
        if last_donation and isinstance(last_donation, str):
            last_donation = date.fromisoformat(last_donation)

        eligible_from, reason = self.calculate_eligible_from(
            sex=donor.get("sex", "M"),
            last_donation_date=last_donation,
            active_deferral_until=active_deferral_until,
            donations_past_year_count=donations_past_year_count
        )

        if eligible_from > event_date:
            days_away = (eligible_from - event_date).days
            return False, f"Ineligible on event date. Earliest eligible is {eligible_from} ({days_away} days too early)", eligible_from

        return True, "Eligible", eligible_from
