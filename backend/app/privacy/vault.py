"""Privacy, RBAC, PII Encryption Vault simulation and DPDP-compliant Audit Logging."""
import hashlib
import base64
from datetime import datetime
from typing import Dict, Any, List, Optional

class PrivacyVault:
    """
    Simulates encrypted PII storage. Real patient & donor names, phones,
    and addresses are never stored in plain text alongside clinical / scheduling tables.
    """
    def __init__(self, salt: str = "telbe_salt_key_2026"):
        self.salt = salt
        self.vault: Dict[str, Dict[str, str]] = {}

    def store_pii(self, entity_id: str, pii_data: Dict[str, str]):
        """Store encrypted PII for an entity (patient or donor)."""
        encrypted = {}
        for k, v in pii_data.items():
            # Simple reversible obfuscation for prototype demo simulating column encryption
            b = v.encode("utf-8")
            encrypted[k] = base64.b64encode(b).decode("utf-8")
        self.vault[entity_id] = encrypted

    def reveal_pii(self, entity_id: str, actor_id: str, role: str, reason: str, audit_logger) -> Optional[Dict[str, str]]:
        """
        Carefully controlled PII reveal.
        Restricted to Coordinator and Admin roles.
        MUST record an immutable audit log entry.
        """
        if role not in ["COORDINATOR", "ADMIN"]:
            audit_logger.log(
                actor_id=actor_id,
                role=role,
                action="UNAUTHORIZED_PII_ACCESS_ATTEMPT",
                entity="PII_VAULT",
                entity_id=entity_id,
                reason=f"Rejected unauthorized role {role}"
            )
            return None

        encrypted = self.vault.get(entity_id)
        if not encrypted:
            return None

        # Decrypt
        decrypted = {}
        for k, v in encrypted.items():
            decrypted[k] = base64.b64decode(v.encode("utf-8")).decode("utf-8")

        audit_logger.log(
            actor_id=actor_id,
            role=role,
            action="PII_REVEAL",
            entity="PII_VAULT",
            entity_id=entity_id,
            reason=reason
        )
        return decrypted

class AuditLogger:
    """Immutable audit trail of all access, matching runs, escalations and edits."""
    def __init__(self):
        self.logs: List[Dict[str, Any]] = []

    def log(self, actor_id: str, role: str, action: str, entity: str, entity_id: str, reason: str = ""):
        entry = {
            "log_id": f"AUD-{len(self.logs) + 1:05d}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "actor_id": actor_id,
            "role": role,
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "reason": reason
        }
        self.logs.append(entry)
        return entry

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        return list(reversed(self.logs[-limit:]))
