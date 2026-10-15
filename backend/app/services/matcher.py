"""Matching & Allocation Engine - ranks and shortlists primary and backup donors."""
from datetime import date, timedelta
from typing import List, Dict, Any, Optional
import math
from app.services.compatibility import is_compatible, is_identical, calculate_phenotype_match_score, get_scarcity_penalty
from app.services.eligibility import EligibilityEngine

class MatcherEngine:
    def __init__(self, eligibility_engine: Optional[EligibilityEngine] = None):
        self.eligibility = eligibility_engine or EligibilityEngine()

    def score_candidate(
        self,
        donor: Dict[str, Any],
        patient: Dict[str, Any],
        event_date: date,
        is_panel_member: bool,
        committed_events_count: int = 0
    ) -> Dict[str, Any]:
        """
        Calculates transparency-backed candidate score:
        + Panel continuity bonus (+35)
        + ABO identical (+30) vs compatible (+15)
        + Extended phenotype compatibility (+0 to +25)
        + Reliability show-up history (+0 to +20)
        + Proximity bonus (+0 to +15 based on travel distance)
        - Recent request load / fatigue penalty (-10 per recent invite)
        - Scarcity penalty (conserve O- / O+)
        """
        recipient_abo = patient["abo"]
        recipient_rh = patient["rh"]
        recipient_group = f"{recipient_abo}{recipient_rh}"

        donor_abo = donor["abo"]
        donor_rh = donor["rh"]
        donor_group = f"{donor_abo}{donor_rh}"

        breakdown = {}
        total_score = 0.0

        # 1. Panel Continuity
        panel_score = 35.0 if is_panel_member else 0.0
        breakdown["panel_continuity"] = panel_score
        total_score += panel_score

        # 2. Blood Group Identity vs Compatibility
        if is_identical(recipient_group, donor_group):
            group_score = 30.0
            breakdown["group_match"] = "Identical (+30)"
        else:
            group_score = 15.0
            breakdown["group_match"] = "Compatible (+15)"
        total_score += group_score

        # 3. Phenotype Matching
        pheno_score = calculate_phenotype_match_score(
            patient.get("phenotype_json", {}),
            donor.get("phenotype_json", {})
        )
        breakdown["phenotype_match"] = round(pheno_score, 1)
        total_score += pheno_score

        # 4. Donor Reliability / Show-up rate
        show_up_rate = donor.get("show_up_rate", 0.90)  # default 90%
        reliability_score = round(show_up_rate * 20.0, 1)
        breakdown["reliability"] = reliability_score
        total_score += reliability_score

        # 5. Proximity / Travel Distance
        donor_dist = donor.get("distance_km", 5.0)
        max_dist = donor.get("travel_radius_km", 15.0)
        if donor_dist <= max_dist:
            dist_score = max(0.0, 15.0 - (donor_dist / max_dist) * 10.0)
        else:
            dist_score = 0.0
        breakdown["proximity"] = round(dist_score, 1)
        total_score += dist_score

        # 6. Fatigue / Load balancing penalty
        recent_invites = donor.get("recent_invites_count", 0) + committed_events_count
        fatigue_penalty = min(25.0, recent_invites * 8.0)
        breakdown["fatigue_penalty"] = -round(fatigue_penalty, 1)
        total_score -= fatigue_penalty

        # 7. Scarcity penalty (e.g. O- donor for A+ patient)
        scarcity = get_scarcity_penalty(donor_group, recipient_group)
        breakdown["scarcity_penalty"] = -round(scarcity, 1)
        total_score -= scarcity

        return {
            "donor_id": donor["donor_id"],
            "donor_group": donor_group,
            "total_score": round(max(0.0, total_score), 2),
            "breakdown": breakdown,
            "is_panel_member": is_panel_member
        }

    def match_for_event(
        self,
        event: Dict[str, Any],
        patient: Dict[str, Any],
        donor_pool: List[Dict[str, Any]],
        panel_donor_ids: List[str],
        active_commitments: Dict[str, List[date]],
        deferrals: Dict[str, date],
        donations_past_year: Dict[str, int],
        backup_ratio: int = 1
    ) -> Dict[str, Any]:
        """
        Runs full candidate filtering & ranking for one Transfusion Event.
        Selects primary donors (units_required) and backup donors (units_required * backup_ratio).
        """
        event_date = date.fromisoformat(event["planned_date"])
        recipient_group = f"{patient['abo']}{patient['rh']}"
        units_required = event.get("units_required", 2)

        candidates = []

        for donor in donor_pool:
            donor_group = f"{donor['abo']}{donor['rh']}"
            donor_id = donor["donor_id"]

            # Filter 1: Basic Red-Cell Compatibility
            if not is_compatible(recipient_group, donor_group):
                continue

            # Filter 2: Clinical Eligibility on event date
            active_def = deferrals.get(donor_id)
            past_year_count = donations_past_year.get(donor_id, 0)
            eligible, reason, eligible_from = self.eligibility.check_eligibility_for_event(
                donor=donor,
                event_date=event_date,
                active_deferral_until=active_def,
                donations_past_year_count=past_year_count
            )
            if not eligible:
                continue

            # Filter 3: Commitment conflicts (already committed within required interval)
            commitments = active_commitments.get(donor_id, [])
            gender_interval = 90 if donor.get("sex", "M").upper() == "M" else 120
            conflict = False
            for c_date in commitments:
                if abs((event_date - c_date).days) < gender_interval:
                    conflict = True
                    break
            if conflict:
                continue

            # Filter 4: Travel radius & Availability
            if donor.get("distance_km", 5.0) > donor.get("travel_radius_km", 20.0):
                continue

            # Donor passed hard filters -> score
            is_panel = donor_id in panel_donor_ids
            score_data = self.score_candidate(
                donor=donor,
                patient=patient,
                event_date=event_date,
                is_panel_member=is_panel,
                committed_events_count=len(commitments)
            )
            candidates.append({**donor, **score_data})

        # Sort candidates by descending total score
        candidates.sort(key=lambda x: x["total_score"], reverse=True)

        primary_donors = candidates[:units_required]
        backup_count = units_required * backup_ratio
        backup_donors = candidates[units_required : units_required + backup_count]

        return {
            "event_id": event["event_id"],
            "patient_id": patient["patient_id"],
            "recipient_group": recipient_group,
            "units_required": units_required,
            "eligible_candidates_count": len(candidates),
            "primary_donors": primary_donors,
            "backup_donors": backup_donors,
            "all_ranked_candidates": candidates
        }
