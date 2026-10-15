import pytest
from datetime import date, timedelta
from app.services.compatibility import is_compatible, is_identical, calculate_phenotype_match_score, get_scarcity_penalty
from app.services.eligibility import EligibilityEngine
from app.services.forecaster import generate_forecast_events, adjust_forecast_by_hemoglobin
from app.services.matcher import MatcherEngine
from app.services.escalation import EscalationEngine

def test_compatibility_rules():
    # O- can only receive O-
    assert is_compatible("O-", "O-") is True
    assert is_compatible("O-", "O+") is False
    assert is_compatible("O-", "A-") is False

    # B+ can receive B+, B-, O+, O-
    assert is_compatible("B+", "B+") is True
    assert is_compatible("B+", "B-") is True
    assert is_compatible("B+", "O+") is True
    assert is_compatible("B+", "O-") is True
    assert is_compatible("B+", "A+") is False

    # AB+ is universal recipient
    assert is_compatible("AB+", "O-") is True
    assert is_compatible("AB+", "AB+") is True

    # Identity check
    assert is_identical("B+", "B+") is True
    assert is_identical("B+", "O+") is False

def test_scarcity_penalty():
    # O- donor used for AB+ recipient should have heavy scarcity penalty
    p_rare = get_scarcity_penalty("O-", "AB+")
    p_exact = get_scarcity_penalty("O-", "O-")
    assert p_rare > 20.0
    assert p_exact == 0.0

def test_phenotype_matching():
    rec = {"C": "+", "c": "-", "E": "-", "e": "+", "K": "-"}
    # Kell positive donor for Kell negative recipient should return penalty
    don_incompatible = {"C": "+", "c": "-", "E": "-", "e": "+", "K": "+"}
    score_bad = calculate_phenotype_match_score(rec, don_incompatible)
    assert score_bad == -50.0

    # Kell negative donor with matching antigens
    don_good = {"C": "+", "c": "-", "E": "-", "e": "+", "K": "-"}
    score_good = calculate_phenotype_match_score(rec, don_good)
    assert score_good > 0.0

def test_eligibility_intervals():
    engine = EligibilityEngine()
    today = date.today()

    # Male requires 90 days
    last_don_m = today - timedelta(days=60)
    elig_date_m, _ = engine.calculate_eligible_from("M", last_don_m)
    assert elig_date_m == last_don_m + timedelta(days=90)
    assert elig_date_m > today

    # Female requires 120 days
    last_don_f = today - timedelta(days=100)
    elig_date_f, _ = engine.calculate_eligible_from("F", last_don_f)
    assert elig_date_f == last_don_f + timedelta(days=120)

    # Active deferral pushes date further
    deferral = today + timedelta(days=15)
    elig_def, _ = engine.calculate_eligible_from("M", today - timedelta(days=100), active_deferral_until=deferral)
    assert elig_def == deferral

def test_forecaster():
    today = date.today()
    events = generate_forecast_events(
        patient_id="PT-0042",
        last_transfusion_date=today - timedelta(days=14),
        interval_days=21,
        units_per_session=2,
        centre_id="CTR-01",
        days_ahead=63
    )
    assert len(events) >= 2
    assert events[0]["units_required"] == 2
    assert events[0]["patient_id"] == "PT-0042"

def test_matcher_ranking():
    matcher = MatcherEngine()
    event = {
        "event_id": "EV-01",
        "planned_date": (date.today() + timedelta(days=10)).isoformat(),
        "units_required": 2
    }
    patient = {
        "patient_id": "PT-0042",
        "abo": "B",
        "rh": "+",
        "phenotype_json": {"K": "-"}
    }
    donors = [
        # Panel member, B+, high reliability
        {
            "donor_id": "DON-01", "abo": "B", "rh": "+", "sex": "M",
            "weight": 70, "distance_km": 5, "travel_radius_km": 20,
            "show_up_rate": 0.95, "last_donation_date": (date.today() - timedelta(days=100)).isoformat(),
            "phenotype_json": {"K": "-"}
        },
        # Compatible O+ donor, non-panel
        {
            "donor_id": "DON-02", "abo": "O", "rh": "+", "sex": "M",
            "weight": 65, "distance_km": 10, "travel_radius_km": 20,
            "show_up_rate": 0.90, "last_donation_date": (date.today() - timedelta(days=100)).isoformat(),
            "phenotype_json": {"K": "-"}
        },
        # Ineligible donor (<90d interval)
        {
            "donor_id": "DON-03", "abo": "B", "rh": "+", "sex": "M",
            "weight": 70, "distance_km": 5, "travel_radius_km": 20,
            "show_up_rate": 0.95, "last_donation_date": (date.today() - timedelta(days=30)).isoformat(),
            "phenotype_json": {"K": "-"}
        }
    ]

    result = matcher.match_for_event(
        event=event,
        patient=patient,
        donor_pool=donors,
        panel_donor_ids=["DON-01"],
        active_commitments={},
        deferrals={},
        donations_past_year={}
    )

    # DON-03 must be filtered out due to interval violation
    assert len(result["primary_donors"]) >= 1
    assert result["primary_donors"][0]["donor_id"] == "DON-01"
    candidate_ids = [c["donor_id"] for c in result["all_ranked_candidates"]]
    assert "DON-03" not in candidate_ids
