"""In-memory simulated datastore with rich synthetic thalassemia population and donors."""
from datetime import date, timedelta
import random
from typing import Dict, Any, List

class InMemoryDatabase:
    def __init__(self):
        self.centres: Dict[str, Dict[str, Any]] = {}
        self.patients: Dict[str, Dict[str, Any]] = {}
        self.donors: Dict[str, Dict[str, Any]] = {}
        self.events: Dict[str, Dict[str, Any]] = {}
        self.invitations: Dict[str, Dict[str, Any]] = {}
        self.panels: Dict[str, List[str]] = {}  # patient_id -> list of donor_ids
        self.deferrals: Dict[str, date] = {}    # donor_id -> deferral_until
        self.commitments: Dict[str, List[date]] = {} # donor_id -> list of committed dates
        self.rules_config: Dict[str, Any] = {
            "male_interval_days": 90,
            "female_interval_days": 120,
            "min_age": 18,
            "max_age": 65,
            "min_weight_kg": 45.0,
            "planning_horizon_days": 21,
            "backup_ratio": 1
        }

    def seed_initial_data(self, privacy_vault, audit_logger):
        # 1. Centres
        centres_data = [
            {"centre_id": "CTR-01", "name": "Thalassemia Comprehensive Care Centre (Apollo/ICH)", "city": "Chennai", "pincode": "600008"},
            {"centre_id": "CTR-02", "name": "Kanchi Kamakoti CHILDS Trust Hospital Blood Centre", "city": "Chennai", "pincode": "600034"},
            {"centre_id": "CTR-03", "name": "Rotary Blood Bank & Thalassemia Day Care", "city": "Chennai", "pincode": "600010"}
        ]
        for c in centres_data:
            self.centres[c["centre_id"]] = c

        # 2. Patients (Pseudonyms: PT-0042 Aarav, etc.)
        # Real blood group distribution in India: O+ ~37%, B+ ~32%, A+ ~22%, AB+ ~7%, Rh- ~2-3%
        patients_spec = [
            {
                "patient_id": "PT-0042",
                "pseudonym": "PT-0042 (Aarav)",
                "real_name": "Aarav Krishnan",
                "guardian": "Suresh Krishnan",
                "phone": "+91 98401 23456",
                "abo": "B", "rh": "+",
                "phenotype_json": {"C": "+", "c": "-", "E": "-", "e": "+", "K": "-"},
                "centre_id": "CTR-01",
                "interval_days": 21,
                "units_per_session": 2,
                "special_reqs": "Leukoreduced, Packed RBCs <7 days old, Kell negative",
                "last_transfusion_date": (date.today() - timedelta(days=18)).isoformat(),
                "hb_history": [9.1, 9.4, 9.2]
            },
            {
                "patient_id": "PT-0019",
                "pseudonym": "PT-0019 (Diya)",
                "real_name": "Diya Raman",
                "guardian": "Kavitha Raman",
                "phone": "+91 98410 88776",
                "abo": "O", "rh": "+",
                "phenotype_json": {"C": "-", "c": "+", "E": "-", "e": "+", "K": "-"},
                "centre_id": "CTR-01",
                "interval_days": 28,
                "units_per_session": 1,
                "special_reqs": "Leukoreduced, saline washed",
                "last_transfusion_date": (date.today() - timedelta(days=26)).isoformat(),
                "hb_history": [9.5, 9.6, 9.4]
            },
            {
                "patient_id": "PT-0088",
                "pseudonym": "PT-0088 (Kabir)",
                "real_name": "Kabir Sharma",
                "guardian": "Rohit Sharma",
                "phone": "+91 94441 55432",
                "abo": "A", "rh": "+",
                "phenotype_json": {"C": "+", "c": "+", "E": "-", "e": "+", "K": "-"},
                "centre_id": "CTR-02",
                "interval_days": 21,
                "units_per_session": 2,
                "special_reqs": "Leukoreduced",
                "last_transfusion_date": (date.today() - timedelta(days=12)).isoformat(),
                "hb_history": [9.0, 9.1, 9.3]
            },
            {
                "patient_id": "PT-0104",
                "pseudonym": "PT-0104 (Meera)",
                "real_name": "Meera Balaji",
                "guardian": "Anand Balaji",
                "phone": "+91 99620 11223",
                "abo": "O", "rh": "-",
                "phenotype_json": {"C": "-", "c": "+", "E": "-", "e": "+", "K": "-"},
                "centre_id": "CTR-03",
                "interval_days": 24,
                "units_per_session": 1,
                "special_reqs": "Rh-negative rare inventory, CMV negative, Leukoreduced",
                "last_transfusion_date": (date.today() - timedelta(days=22)).isoformat(),
                "hb_history": [8.8, 8.9, 9.0]
            },
            {
                "patient_id": "PT-0145",
                "pseudonym": "PT-0145 (Zayan)",
                "real_name": "Zayan Farhan",
                "guardian": "Shabnam Farhan",
                "phone": "+91 97910 66554",
                "abo": "AB", "rh": "+",
                "phenotype_json": {"C": "+", "c": "-", "E": "+", "e": "-", "K": "-"},
                "centre_id": "CTR-02",
                "interval_days": 21,
                "units_per_session": 2,
                "special_reqs": "Leukoreduced, irradiated",
                "last_transfusion_date": (date.today() - timedelta(days=7)).isoformat(),
                "hb_history": [9.2, 9.3, 9.5]
            }
        ]

        for p in patients_spec:
            pid = p["patient_id"]
            privacy_vault.store_pii(pid, {
                "real_name": p["real_name"],
                "guardian": p["guardian"],
                "phone": p["phone"]
            })
            p_clean = {k: v for k, v in p.items() if k not in ["real_name", "guardian", "phone"]}
            p_clean["status"] = "ACTIVE"
            self.patients[pid] = p_clean
            self.panels[pid] = []

        # 3. Generate 60 realistic donors
        random.seed(42)
        blood_groups = [("O", "+", 0.36), ("B", "+", 0.32), ("A", "+", 0.22), ("AB", "+", 0.06), ("O", "-", 0.02), ("B", "-", 0.01), ("A", "-", 0.01)]
        first_names = ["Karthik", "Sneha", "Vignesh", "Pooja", "Arun", "Divya", "Ganesh", "Swetha", "Manoj", "Ananya", "Rajesh", "Priya", "Sunil", "Lavanya", "Harish"]
        last_names = ["Sundaram", "Nair", "Venkatesh", "Iyer", "Rao", "Menon", "Reddy", "Patel", "Pillai", "Varma"]

        for i in range(1, 61):
            did = f"DON-{i:04d}"
            # Select blood group
            r = random.random()
            cum = 0.0
            abo, rh = "B", "+"
            for b_abo, b_rh, prob in blood_groups:
                cum += prob
                if r <= cum:
                    abo, rh = b_abo, b_rh
                    break

            sex = random.choice(["M", "M", "M", "F"])  # Indian donor pool skew
            weight = random.randint(52, 85)
            age = random.randint(21, 52)
            dob = (date.today() - timedelta(days=age * 365 + random.randint(0, 300))).isoformat()
            
            # Distance from centre
            dist = round(random.uniform(2.5, 22.0), 1)
            radius = random.choice([15.0, 20.0, 25.0])
            show_up_rate = round(random.uniform(0.82, 0.98), 2)

            # Last donation date
            days_ago = random.choice([15, 45, 95, 110, 140, 180, 250, None])
            last_don = (date.today() - timedelta(days=days_ago)).isoformat() if days_ago else None

            fname = random.choice(first_names)
            lname = random.choice(last_names)
            full_name = f"{fname} {lname}"
            phone = f"+91 9{random.randint(100000000, 999999999)}"
            email = f"{fname.lower()}.{lname.lower()}{random.randint(1,99)}@gmail.com"

            privacy_vault.store_pii(did, {
                "name": full_name,
                "phone": phone,
                "email": email
            })

            pheno = {
                "C": random.choice(["+", "-"]),
                "c": "+",
                "E": random.choice(["+", "-"]),
                "e": "+",
                "K": "-" # Kell negative is common (91%+)
            }

            self.donors[did] = {
                "donor_id": did,
                "abo": abo,
                "rh": rh,
                "sex": sex,
                "dob": dob,
                "weight": weight,
                "phenotype_json": pheno,
                "pincode": f"6000{random.randint(10, 99)}",
                "distance_km": dist,
                "travel_radius_km": radius,
                "last_donation_date": last_don,
                "show_up_rate": show_up_rate,
                "recent_invites_count": random.randint(0, 2),
                "status": "ACTIVE"
            }
            self.commitments[did] = []

        # Connect a few dedicated panels
        self.panels["PT-0042"] = ["DON-0002", "DON-0005", "DON-0012"]
        self.panels["PT-0019"] = ["DON-0001", "DON-0008"]
        self.panels["PT-0104"] = ["DON-0018"] # Rare O-

        # 4. Generate forecast events for next 60 days
        for pid, p in self.patients.items():
            last_date = date.fromisoformat(p["last_transfusion_date"])
            interval = p["interval_days"]
            cur = last_date + timedelta(days=interval)
            while cur <= date.today() + timedelta(days=60):
                eid = f"EV-{pid}-{cur.strftime('%Y%m%d')}"
                self.events[eid] = {
                    "event_id": eid,
                    "patient_id": pid,
                    "centre_id": p["centre_id"],
                    "planned_date": cur.isoformat(),
                    "units_required": p["units_per_session"],
                    "status": "PLANNED",
                    "coverage_count": 0
                }
                cur += timedelta(days=interval)

        # 5. Populate some active invitations for immediate upcoming events
        # E.g. PT-0042's next event is in 3 days: (today - 18d + 21d = today + 3d)
        ev_aarav_next = f"EV-PT-0042-{(date.today() + timedelta(days=3)).strftime('%Y%m%d')}"
        if ev_aarav_next in self.events:
            self.events[ev_aarav_next]["status"] = "PARTIALLY_COVERED"
            # 1 accepted, 1 pending, 1 declined -> triggers backup
            inv1 = {
                "invite_id": "INV-0001",
                "event_id": ev_aarav_next,
                "donor_id": "DON-0002",
                "role": "PRIMARY",
                "status": "ACCEPTED",
                "sent_at": (date.today() - timedelta(days=10)).isoformat(),
                "responded_at": (date.today() - timedelta(days=9)).isoformat()
            }
            inv2 = {
                "invite_id": "INV-0002",
                "event_id": ev_aarav_next,
                "donor_id": "DON-0005",
                "role": "PRIMARY",
                "status": "DECLINED",
                "sent_at": (date.today() - timedelta(days=10)).isoformat(),
                "responded_at": (date.today() - timedelta(days=8)).isoformat()
            }
            inv3 = {
                "invite_id": "INV-0003",
                "event_id": ev_aarav_next,
                "donor_id": "DON-0012",
                "role": "BACKUP",
                "status": "INVITED",
                "sent_at": (date.today() - timedelta(days=7)).isoformat(),
                "responded_at": None
            }
            for inv in [inv1, inv2, inv3]:
                self.invitations[inv["invite_id"]] = inv
            self.events[ev_aarav_next]["coverage_count"] = 1

        audit_logger.log(
            actor_id="SYSTEM",
            role="SYSTEM",
            action="INITIALIZE_SEED_DATA",
            entity="DATABASE",
            entity_id="ALL",
            reason="Bootstrapped simulated thalassemia registry and donor pool"
        )

db = InMemoryDatabase()
