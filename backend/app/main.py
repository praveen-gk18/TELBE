"""FastAPI entrypoint and REST APIs for TELBE / Beyond Emergency Transfusion System."""
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import date, timedelta
import asyncio
import json
import os

from app.privacy.vault import PrivacyVault, AuditLogger
from app.models.datastore import db
from app.services.compatibility import is_compatible, calculate_phenotype_match_score
from app.services.eligibility import EligibilityEngine
from app.services.forecaster import generate_forecast_events
from app.services.matcher import MatcherEngine
from app.services.notifier import NotifierService
from app.services.escalation import EscalationEngine
from app.services.simulation import run_comparative_simulation

# Connection Manager for real-time WebSockets
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# Initialize Core Services
app = FastAPI(
    title="Beyond Emergency - Proactive Thalassemia Transfusion System",
    description="Predictive scheduling, phenotype & compatibility matching, and proactive donor confirmation.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

vault = PrivacyVault()
audit_logger = AuditLogger()
eligibility_engine = EligibilityEngine(db.rules_config)
matcher_engine = MatcherEngine(eligibility_engine)
escalation_engine = EscalationEngine(matcher_engine)

# Seed initial simulated population
db.seed_initial_data(vault, audit_logger)

# Pydantic Schemas
class InvitationAction(BaseModel):
    invite_id: str
    action: str  # ACCEPT, DECLINE, CANCEL
    actor_id: str
    role: str

class MatchRequest(BaseModel):
    event_id: str
    actor_id: str = "COORDINATOR-01"
    role: str = "COORDINATOR"

class RevealPIIRequest(BaseModel):
    entity_id: str
    actor_id: str
    role: str
    reason: str

class RuleUpdateRequest(BaseModel):
    male_interval_days: int
    female_interval_days: int
    min_age: int
    max_age: int
    min_weight_kg: float
    actor_id: str = "ADMIN-01"

# --- API Endpoints ---

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "Beyond Emergency Transfusion System", "timestamp": date.today().isoformat(), "active_clients": len(manager.active_connections)}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive with heartbeat
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "PONG", "timestamp": date.today().isoformat()}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# 1. Events & Forecaster
@app.get("/api/events")
def get_transfusion_events(patient_id: Optional[str] = None):
    """Retrieve upcoming transfusion events with coverage status and timeline risk."""
    events = list(db.events.values())
    if patient_id:
        events = [e for e in events if e["patient_id"] == patient_id]

    events.sort(key=lambda x: x["planned_date"])
    
    enriched = []
    today = date.today()
    for ev in events:
        ev_copy = dict(ev)
        pid = ev["patient_id"]
        p = db.patients.get(pid, {})
        ev_copy["patient_pseudonym"] = p.get("pseudonym", pid)
        ev_copy["blood_group"] = f"{p.get('abo', '')}{p.get('rh', '')}"
        ev_copy["centre_name"] = db.centres.get(ev["centre_id"], {}).get("name", ev["centre_id"])
        
        # Calculate timeline
        days_left = (date.fromisoformat(ev["planned_date"]) - today).days
        coverage_ratio = ev["coverage_count"] / max(1, ev["units_required"])
        ev_copy["timeline"] = NotifierService.get_timeline_status(days_left, coverage_ratio)
        enriched.append(ev_copy)

    return {"events": enriched, "total": len(enriched)}

@app.get("/api/events/{event_id}")
def get_event_detail(event_id: str):
    """Detail view for an event including invited donors and escalation recommendations."""
    if event_id not in db.events:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event = db.events[event_id]
    patient = db.patients.get(event["patient_id"])
    event_invitations = [inv for inv in db.invitations.values() if inv["event_id"] == event_id]
    
    # Check escalation state
    today = date.today()
    escalation_report = escalation_engine.evaluate_escalation(event, event_invitations, today)

    # Enrich invitations
    invites_enriched = []
    for inv in event_invitations:
        donor = db.donors.get(inv["donor_id"], {})
        invites_enriched.append({
            **inv,
            "donor_blood_group": f"{donor.get('abo')}{donor.get('rh')}",
            "donor_sex": donor.get("sex"),
            "distance_km": donor.get("distance_km"),
            "show_up_rate": donor.get("show_up_rate")
        })

    return {
        "event": event,
        "patient": patient,
        "invitations": invites_enriched,
        "escalation": escalation_report
    }

# 2. Patients & Caregiver View
@app.get("/api/patients")
def get_patients():
    """List patient care plans (pseudonymized)."""
    return {"patients": list(db.patients.values())}

@app.get("/api/caregiver/{patient_id}")
def get_caregiver_view(patient_id: str):
    """
    Caregiver portal view.
    Zero donor PII is exposed - only confirmation count and peace of mind timeline.
    """
    if patient_id not in db.patients:
        raise HTTPException(status_code=404, detail="Patient not found")

    patient = db.patients[patient_id]
    # Upcoming events
    p_events = [e for e in db.events.values() if e["patient_id"] == patient_id and e["planned_date"] >= date.today().isoformat()]
    p_events.sort(key=lambda x: x["planned_date"])
    
    next_event = p_events[0] if p_events else None
    next_event_summary = None
    if next_event:
        days_left = (date.fromisoformat(next_event["planned_date"]) - date.today()).days
        next_event_summary = {
            "event_id": next_event["event_id"],
            "planned_date": next_event["planned_date"],
            "units_required": next_event["units_required"],
            "coverage_count": next_event["coverage_count"],
            "is_fully_confirmed": next_event["coverage_count"] >= next_event["units_required"],
            "days_away": days_left,
            "status_message": (
                f"Peace of mind: All {next_event['units_required']} compatible donors confirmed!" 
                if next_event["coverage_count"] >= next_event["units_required"] 
                else f"Active matching in progress: {next_event['coverage_count']} of {next_event['units_required']} donors confirmed so far."
            )
        }

    return {
        "patient_id": patient_id,
        "pseudonym": patient["pseudonym"],
        "blood_group": f"{patient['abo']}{patient['rh']}",
        "special_reqs": patient.get("special_reqs"),
        "interval_days": patient["interval_days"],
        "next_event": next_event_summary,
        "upcoming_schedule": p_events[:4]
    }

# 3. Donor Registry & Donor Portal
@app.get("/api/donors")
def get_donors(limit: int = 50):
    """Donor registry list with eligibility indicators."""
    donors_list = list(db.donors.values())[:limit]
    res = []
    for d in donors_list:
        did = d["donor_id"]
        last_don = date.fromisoformat(d["last_donation_date"]) if d.get("last_donation_date") else None
        active_def = db.deferrals.get(did)
        elig_from, reason = eligibility_engine.calculate_eligible_from(d["sex"], last_don, active_def)
        res.append({
            **d,
            "eligible_from": elig_from.isoformat(),
            "is_currently_eligible": elig_from <= date.today(),
            "eligibility_reason": reason
        })
    return {"donors": res, "total": len(db.donors)}

@app.get("/api/donor-portal/{donor_id}")
def get_donor_portal(donor_id: str):
    """
    Donor self-service view.
    Zero patient PII revealed.
    """
    if donor_id not in db.donors:
        raise HTTPException(status_code=404, detail="Donor not found")
    donor = db.donors[donor_id]
    
    # Invitations
    d_invites = [inv for inv in db.invitations.values() if inv["donor_id"] == donor_id]
    enriched_invites = []
    for inv in d_invites:
        ev = db.events.get(inv["event_id"], {})
        centre = db.centres.get(ev.get("centre_id", "CTR-01"), {})
        pat = db.patients.get(ev.get("patient_id", ""), {})
        enriched_invites.append({
            **inv,
            "planned_date": ev.get("planned_date"),
            "centre_name": centre.get("name", "Thalassemia Centre"),
            "blood_group_needed": f"{pat.get('abo')}{pat.get('rh')}",
            "anonymized_message": NotifierService.build_invitation_message(
                ev.get("planned_date", ""), centre.get("name", "Thalassemia Centre"), f"{pat.get('abo')}{pat.get('rh')}"
            )
        })

    # Eligibility
    last_don = date.fromisoformat(donor["last_donation_date"]) if donor.get("last_donation_date") else None
    active_def = db.deferrals.get(donor_id)
    elig_from, reason = eligibility_engine.calculate_eligible_from(donor["sex"], last_don, active_def)

    return {
        "donor": donor,
        "eligible_from": elig_from.isoformat(),
        "is_currently_eligible": elig_from <= date.today(),
        "eligibility_reason": reason,
        "invitations": enriched_invites
    }

# 4. Matching & Candidate Ranking Console
@app.post("/api/match")
def run_match_for_event(req: MatchRequest):
    """
    Coordinator Matching Console API.
    Runs clinical compatibility, eligibility filters, and ranking algorithms.
    """
    if req.event_id not in db.events:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event = db.events[req.event_id]
    patient = db.patients[event["patient_id"]]
    panel = db.panels.get(patient["patient_id"], [])

    result = matcher_engine.match_for_event(
        event=event,
        patient=patient,
        donor_pool=list(db.donors.values()),
        panel_donor_ids=panel,
        active_commitments=db.commitments,
        deferrals=db.deferrals,
        donations_past_year={},
        backup_ratio=db.rules_config.get("backup_ratio", 1)
    )

    audit_logger.log(
        actor_id=req.actor_id,
        role=req.role,
        action="RUN_MATCHING_ALGORITHM",
        entity="EVENT",
        entity_id=req.event_id,
        reason=f"Matched for {patient['pseudonym']} - {len(result['primary_donors'])} primary, {len(result['backup_donors'])} backup"
    )

    return result

@app.post("/api/dispatch-invites")
async def dispatch_invites(event_id: str, primary_donor_ids: List[str], backup_donor_ids: List[str]):
    """Creates invitation records for selected primary and backup candidates."""
    if event_id not in db.events:
        raise HTTPException(status_code=404, detail="Event not found")

    new_invites = []
    for did in primary_donor_ids:
        inv_id = f"INV-{len(db.invitations) + 1:04d}"
        inv = {
            "invite_id": inv_id,
            "event_id": event_id,
            "donor_id": did,
            "role": "PRIMARY",
            "status": "INVITED",
            "sent_at": date.today().isoformat(),
            "responded_at": None
        }
        db.invitations[inv_id] = inv
        new_invites.append(inv)

    for did in backup_donor_ids:
        inv_id = f"INV-{len(db.invitations) + 1:04d}"
        inv = {
            "invite_id": inv_id,
            "event_id": event_id,
            "donor_id": did,
            "role": "BACKUP",
            "status": "INVITED",
            "sent_at": date.today().isoformat(),
            "responded_at": None
        }
        db.invitations[inv_id] = inv
        new_invites.append(inv)

    db.events[event_id]["status"] = "INVITES_SENT"
    
    audit_logger.log(
        actor_id="COORDINATOR-01",
        role="COORDINATOR",
        action="DISPATCH_INVITATIONS",
        entity="EVENT",
        entity_id=event_id,
        reason=f"Dispatched {len(primary_donor_ids)} primary and {len(backup_donor_ids)} backup invitations"
    )

    # Broadcast event to all open webpages instantly
    await manager.broadcast({
        "type": "INVITATIONS_DISPATCHED",
        "event_id": event_id,
        "count": len(new_invites)
    })

    return {"status": "success", "invitations": new_invites}

# 5. Invitation Response Workflow (Donor / Coordinator interaction)
@app.post("/api/invitations/respond")
async def respond_to_invitation(req: InvitationAction):
    """Handles donor accept / decline / coordinator override."""
    if req.invite_id not in db.invitations:
        raise HTTPException(status_code=404, detail="Invitation not found")

    inv = db.invitations[req.invite_id]
    event = db.events.get(inv["event_id"])
    today_str = date.today().isoformat()

    old_status = inv["status"]
    if req.action == "ACCEPT":
        inv["status"] = "ACCEPTED"
        inv["responded_at"] = today_str
        if event:
            confirmed = sum(1 for i in db.invitations.values() if i["event_id"] == inv["event_id"] and i["status"] in ["ACCEPTED", "CONFIRMED"])
            event["coverage_count"] = confirmed
            if confirmed >= event["units_required"]:
                event["status"] = "FULLY_COVERED"
            else:
                event["status"] = "PARTIALLY_COVERED"

    elif req.action == "DECLINE":
        inv["status"] = "DECLINED"
        inv["responded_at"] = today_str

    elif req.action == "CANCEL":
        inv["status"] = "CANCELLED"
        inv["responded_at"] = today_str
        if event:
            confirmed = sum(1 for i in db.invitations.values() if i["event_id"] == inv["event_id"] and i["status"] in ["ACCEPTED", "CONFIRMED"])
            event["coverage_count"] = confirmed
            event["status"] = "PARTIALLY_COVERED"

    audit_logger.log(
        actor_id=req.actor_id,
        role=req.role,
        action=f"INVITATION_{req.action}",
        entity="INVITATION",
        entity_id=req.invite_id,
        reason=f"Changed status from {old_status} to {inv['status']}"
    )

    # Broadcast status change across caregiver, donor, and coordinator pages
    await manager.broadcast({
        "type": "INVITATION_UPDATED",
        "invite_id": req.invite_id,
        "action": req.action,
        "event_id": inv["event_id"],
        "coverage_count": event.get("coverage_count") if event else 0
    })

    return {"status": "success", "invitation": inv, "event": event}

# 6. Privacy Vault & Audit Logs
@app.post("/api/privacy/reveal-pii")
def reveal_pii(req: RevealPIIRequest):
    """Restricted DPDP-compliant PII access with strict audit recording."""
    data = vault.reveal_pii(
        entity_id=req.entity_id,
        actor_id=req.actor_id,
        role=req.role,
        reason=req.reason,
        audit_logger=audit_logger
    )
    if data is None:
        raise HTTPException(status_code=403, detail="Unauthorized or entity not found. Attempt logged.")
    return {"entity_id": req.entity_id, "pii": data}

@app.get("/api/privacy/audit-logs")
def get_audit_logs(limit: int = 50):
    """Retrieve immutable audit logs."""
    return {"logs": audit_logger.get_logs(limit)}

# 7. Rules Configuration (Admin)
@app.get("/api/admin/rules")
def get_rules():
    return db.rules_config

@app.post("/api/admin/rules")
def update_rules(req: RuleUpdateRequest):
    db.rules_config.update({
        "male_interval_days": req.male_interval_days,
        "female_interval_days": req.female_interval_days,
        "min_age": req.min_age,
        "max_age": req.max_age,
        "min_weight_kg": req.min_weight_kg
    })
    eligibility_engine.config = db.rules_config
    audit_logger.log(
        actor_id=req.actor_id,
        role="ADMIN",
        action="UPDATE_ELIGIBILITY_RULES",
        entity="RULES_CONFIG",
        entity_id="GLOBAL",
        reason="Updated clinical threshold parameters"
    )
    return {"status": "updated", "rules": db.rules_config}

# 8. Simulation & Evaluation API
@app.get("/api/simulation/evaluate")
def run_simulation_api(months: int = 6):
    """Runs 6-month synthetic population time-stepped simulation comparing Reactive vs Proactive."""
    results = run_comparative_simulation(months=months)
    return results

# Serve UI Static Assets
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "..", "frontend", "static")
PAGES_DIR = os.path.join(BASE_DIR, "..", "frontend", "pages")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/coordinator")
def serve_coordinator():
    return FileResponse(os.path.join(PAGES_DIR, "coordinator.html"))

@app.get("/caregiver")
def serve_caregiver():
    return FileResponse(os.path.join(PAGES_DIR, "caregiver.html"))

@app.get("/donor")
def serve_donor():
    return FileResponse(os.path.join(PAGES_DIR, "donor.html"))

@app.get("/simulation")
def serve_simulation():
    return FileResponse(os.path.join(PAGES_DIR, "simulation.html"))

@app.get("/admin")
def serve_admin():
    return FileResponse(os.path.join(PAGES_DIR, "admin.html"))


