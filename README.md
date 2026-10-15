# TELBE: Proactive Thalassemia Transfusion System

> **Core Idea:** *If a transfusion can be predicted, finding donors for it should be planned ahead and not become an emergency.*

This project implements an end-to-end prototype and evaluation platform for predictive, proactive blood donor scheduling designed specifically for recurrent pediatric transfusion recipients (such as children with Thalassemia Major).

---

## 🌟 Key Features & Implemented Architecture

### 1. Clinical Engines & Forecaster
- **Module 1 & 3: Patient Care Plan & Schedule Forecaster**
  - Generates recurring transfusion dates up to 90 days in advance based on clinical intervals (14–35 days) and units required.
  - Adaptive forecasting factoring in pre-transfusion hemoglobin trend drops (<9.0 g/dL).
- **Module 4: Red-Cell Compatibility & Phenotype Engine**
  - Complete ABO & Rh red-cell compatibility mapping.
  - Extended phenotype matching (Rh C/c/E/e and Kell K/k) to minimize alloimmunization risks in chronically transfused patients.
  - Scarcity penalty to conserve scarce donor blood groups (e.g. O- / O+) for patients who strictly require them.
- **Module 5: Eligibility Engine**
  - Configurable national guidelines (NBTC India).
  - Enforces gender-based donation intervals (90 days for men, 120 days for women), age limits (18–65), minimum body weight (45 kg), and self-declared temporary deferrals.
- **Module 6: Matching & Allocation Console**
  - Transparent scoring algorithm ranking candidates by panel continuity (+35), identical ABO (+30), phenotype bonus (+25), historical reliability/show-up rate (+20), and proximity (+15), while subtracting donor fatigue penalties.
  - Primary (required units) and Backup reserve allocations.
- **Module 7 & 8: Notification Timeline & Escalation Engine**
  - Structured confirmation timeline (D-14, D-10, D-7, D-3 lock, D-1).
  - Automatic escalation triggers if coverage is below 100% inside the 72-hour (D-3) safety window.

### 2. Privacy & Consent (DPDP Act 2023 Aligned)
- **Module 9: Pseudonymisation & Encrypted PII Vault**
  - Clinical databases store only pseudonyms (`PT-0042`, `DON-0002`). Real names, phone numbers, and addresses reside in an isolated encrypted vault.
  - Donors never see patient identities or diagnoses; caregivers never see donor contact details.
  - Controlled PII reveal for coordinators with mandatory access-reason logging.
  - Immutable audit trail capturing every matching query, rule change, and invite response.

### 3. Five-Persona Interactive UI
1. **Coordinator Console:** Live color-coded schedule (🟢 Covered, 🟡 Partial, 🔴 At Risk), one-click candidate matching, and score breakdown modal.
2. **Caregiver View:** Reassurance portal displaying confirmation progress ("2 of 2 donors confirmed") and upcoming calendar without exposing donor PII.
3. **Donor Portal:** Anonymized transfusion requests, clear national eligibility countdown, and simulated accept/decline workflow.
4. **Simulation & Evaluation:** Live head-to-head evaluation comparing the **Reactive Baseline** (1–2 days before) against the **Proactive Engine** across a 6-month synthetic cohort.
5. **Admin Panel:** Live tuning of national clinical intervals and audit log inspection.

---

## 🚀 Running the Application

### 1. Requirements
- Python 3.10+
- FastAPI, Uvicorn, Pydantic, Pytest

```bash
pip install fastapi uvicorn pydantic python-multipart pytest
```

### 2. Start the Server
```bash
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open your browser at `http://localhost:8000`.

### 3. Run Unit Tests
```bash
PYTHONPATH=backend pytest backend/tests
```

---

## 📊 Comparative Simulation Results (6 Months, 50 Patients)

| Metric | Reactive Baseline (scramble) | Proactive Engine (ours) | Impact |
|---|---|---|---|
| **% Confirmed &ge; 72h (T-3) Ahead** | 0.0% | **94% - 100%** | **No last-minute panic** |
| **Avg. Confirmation Lead Time** | ~1.0 day | **~9.5 days** | **+8.5 days earlier** |
| **Last-minute searches (<48h)** | High (~98%) | **< 2%** | **~98% reduction** |
| **Eligibility violations (<90d interval)** | Common during scrambles | **0** | **100% safety compliance** |
