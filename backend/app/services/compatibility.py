"""Core models and compatibility rules for transfusion forecasting."""
from typing import List, Dict, Optional, Set

# Red-cell compatibility mapping (Recipient ABO+Rh -> Compatible donor ABO+Rh list)
RED_CELL_COMPATIBILITY: Dict[str, List[str]] = {
    "O-": ["O-"],
    "O+": ["O+", "O-"],
    "A-": ["A-", "O-"],
    "A+": ["A+", "A-", "O+", "O-"],
    "B-": ["B-", "O-"],
    "B+": ["B+", "B-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": ["AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"]
}

# Rare/universal blood group conservation penalties
SCARCITY_PENALTY: Dict[str, Dict[str, float]] = {
    # If donor is O- but recipient is not O-, penalize heavily to conserve O-
    "O-": {
        "O-": 0.0,
        "O+": 25.0,
        "A-": 15.0,
        "A+": 30.0,
        "B-": 15.0,
        "B+": 30.0,
        "AB-": 20.0,
        "AB+": 35.0
    },
    # If donor is O+ but recipient is AB+ or A+/B+, minor conservation penalty
    "O+": {
        "O+": 0.0,
        "A+": 10.0,
        "B+": 10.0,
        "AB+": 15.0
    }
}

def is_compatible(recipient_group: str, donor_group: str) -> bool:
    """Check basic red-cell compatibility."""
    valid_donors = RED_CELL_COMPATIBILITY.get(recipient_group, [])
    return donor_group in valid_donors

def is_identical(recipient_group: str, donor_group: str) -> bool:
    """Check ABO+Rh identity."""
    return recipient_group == donor_group

def calculate_phenotype_match_score(recipient_phenotype: Dict[str, str], donor_phenotype: Dict[str, str]) -> float:
    """
    Evaluate extended phenotype match (Rh C/c/E/e, Kell K/k).
    Returns a score 0-25 bonus.
    Negative match for recipient negative antigen is critical to prevent alloimmunisation.
    """
    if not recipient_phenotype or not donor_phenotype:
        return 0.0
    
    score = 0.0
    antigens = ["C", "c", "E", "e", "K", "k"]
    evaluated = 0
    
    for ag in antigens:
        rec_val = recipient_phenotype.get(ag)
        don_val = donor_phenotype.get(ag)
        if rec_val is not None and don_val is not None:
            evaluated += 1
            # If recipient is negative and donor is positive -> bad for alloimmunisation
            if rec_val == "-" and don_val == "+":
                return -50.0  # Incompatible extended phenotype / high risk
            elif rec_val == don_val:
                score += 4.0
    
    return min(25.0, score)

def get_scarcity_penalty(donor_group: str, recipient_group: str) -> float:
    """Get penalty for using scarce donor group (like O-) on non-restricted recipients."""
    donor_penalties = SCARCITY_PENALTY.get(donor_group, {})
    return donor_penalties.get(recipient_group, 0.0)
