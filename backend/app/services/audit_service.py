"""Paytm AI ActionMate Cryptographic Audit Ledger & Timeline Service.
Maintains an immutable, append-only SHA-256 chained audit trail of every
merchant request, data retrieval, plan, approval gate, edit, and execution attempt.
Provides cryptographic tamper detection and human-readable timeline generation.
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from ..database import get_connection
from ..schemas import AuditEventSchema

GENESIS_HASH = "GENESIS_BLOCK_0000000000000000000000000000000000000000000000000000000000000000"

# User-facing readable descriptions for actions
ACTION_DESCRIPTIONS = {
    "MERCHANT_REQUEST": "Merchant submitted a sales recovery request.",
    "DATA_RETRIEVAL": "AI retrieved weekly sales data & repeat-purchase trends.",
    "SALES_DROP_ANALYSIS": "AI identified a decline in repeat purchases (plummeted from 41% to 24%).",
    "CAMPAIGN_RECOMMENDED": "AI recommended a re-engagement campaign with Soundbox QR telemetry.",
    "CAMPAIGN_DRAFTED": "Campaign message drafted with Indic dialect synthesis.",
    "APPROVAL_REQUESTED": "Approval requested from merchant owner.",
    "CAMPAIGN_APPROVED": "Merchant approved campaign with cryptographic HMAC signature.",
    "CAMPAIGN_REJECTED": "Merchant rejected campaign strategy.",
    "CAMPAIGN_EDITED_APPROVAL_INVALIDATED": "Campaign message edited by merchant; previous approval invalidated.",
    "CAMPAIGN_CHANGES_REQUESTED": "Merchant requested revisions to promotional terms.",
    "CAMPAIGN_PAUSED": "Campaign paused by merchant.",
    "CAMPAIGN_RESUMED": "Campaign resumed by merchant.",
    "SIMULATED_CAMPAIGN_DISPATCH": "Demo execution started via simulated sandbox adapter (DEMO).",
    "SIMULATED_EXECUTION_VERIFIED": "Execution verified: closed-loop delivery & DND suppression confirmed.",
    "FINANCIAL_ACTION_BLOCKED": "Action blocked: Category C financial mutation attempt strictly prevented.",
    "APPROVAL_INVALIDATED_DRIFT": "Approval invalidated: Pre-execution detected message content drift."
}

class AuditService:
    """Audit Logging, Timeline Formatting, and Cryptographic Verification."""

    @staticmethod
    def calculate_payload_hash(
        prev_hash: str,
        agent_name: str,
        action_type: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Dict[str, Any],
        timestamp_utc: str
    ) -> str:
        """Computes deterministic SHA-256 hash chaining to the previous block."""
        inp_str = json.dumps(tool_input or {}, sort_keys=True)
        out_str = json.dumps(tool_output or {}, sort_keys=True)
        raw = f"{prev_hash}|{agent_name}|{action_type}|{tool_name}|{inp_str}|{out_str}|{timestamp_utc}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    @staticmethod
    def log_audit_event(
        merchant_id: str = "MERCH-001",
        task_id: str = "WF-REC-1042",
        actor_id: str = "system",
        action: str = "SYSTEM_ACTION",
        resource: str = "system",
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
        tool_name: str = "internal",
        tool_input: Optional[Dict[str, Any]] = None,
        tool_output: Optional[Dict[str, Any]] = None,
        duration_ms: int = 120,
        is_simulated: bool = False
    ) -> AuditEventSchema:
        """Appends a new cryptographically chained audit event."""
        conn = get_connection()
        cur = conn.cursor()

        # Retrieve last hash in the chain
        cur.execute("SELECT current_hash FROM audit_trail ORDER BY id DESC LIMIT 1")
        last_row = cur.fetchone()
        prev_hash = last_row["current_hash"] if last_row and last_row["current_hash"] else GENESIS_HASH

        now_utc = datetime.now(timezone.utc).isoformat()
        cur_hash = AuditService.calculate_payload_hash(
            prev_hash=prev_hash,
            agent_name=actor_id,
            action_type=action,
            tool_name=tool_name,
            tool_input=tool_input or {},
            tool_output=tool_output or {},
            timestamp_utc=now_utc
        )

        event_id = f"EVT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{cur_hash[:8]}"

        cur.execute("""
        INSERT INTO audit_trail (
            event_id, merchant_id, task_id, workflow_id, agent_name, actor_id,
            action_type, resource, previous_state, new_state, tool_name,
            tool_input_json, tool_output_json, execution_duration_ms,
            is_simulated, previous_hash, current_hash, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id, merchant_id, task_id, task_id, actor_id, actor_id,
            action, resource, previous_state, new_state, tool_name,
            json.dumps(tool_input or {}), json.dumps(tool_output or {}),
            duration_ms, 1 if is_simulated else 0, prev_hash, cur_hash, now_utc
        ))

        conn.commit()
        conn.close()

        return AuditEventSchema(
            event_id=event_id,
            merchant_id=merchant_id,
            task_id=task_id,
            actor_id=actor_id,
            action=action,
            resource=resource,
            previous_state=previous_state,
            new_state=new_state,
            timestamp=now_utc,
            execution_result="SUCCESS",
            metadata={"tool_name": tool_name, "duration_ms": duration_ms},
            previous_hash=prev_hash,
            current_hash=cur_hash,
            is_simulated=is_simulated
        )

    @staticmethod
    def get_timeline_events(merchant_id: str = "MERCH-001", limit: int = 50) -> List[Dict[str, Any]]:
        """Returns chronological human-readable events with actual timestamps."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT id, event_id, merchant_id, task_id, actor_id, agent_name, action_type,
               resource, tool_name, is_simulated, current_hash, created_at,
               tool_input_json, tool_output_json
        FROM audit_trail
        ORDER BY id DESC
        LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        # Format readable timeline items
        timeline = []
        for r in reversed(rows):
            action = r["action_type"]
            created = r.get("created_at") or datetime.now(timezone.utc).isoformat()
            time_display = created[11:16] if len(created) >= 16 else "10:00"

            readable_desc = ACTION_DESCRIPTIONS.get(
                action,
                f"{r.get('actor_id', 'AI Teammate')} executed {action.replace('_', ' ').lower()}."
            )

            is_sim = bool(r.get("is_simulated", 0)) or "SIMULATE" in action or "DEMO" in action

            timeline.append({
                "id": r["id"],
                "event_id": r.get("event_id") or f"EVT-{r['id']}",
                "timestamp_display": time_display,
                "timestamp_iso": created,
                "formatted_entry": f"{time_display} — {readable_desc}" + (" (SIMULATED)" if is_sim else ""),
                "action_type": action,
                "actor": r.get("actor_id") or r.get("agent_name", "ActionMate"),
                "resource": r.get("resource") or "system",
                "is_simulated": is_sim,
                "hash_short": (r.get("current_hash") or "")[:12] + "..."
            })

        return timeline

    @staticmethod
    def verify_ledger_integrity() -> Dict[str, Any]:
        """Cryptographically verifies the entire SHA-256 hash chain from genesis block."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT id, agent_name, actor_id, action_type, tool_name, tool_input_json,
               tool_output_json, previous_hash, current_hash, created_at
        FROM audit_trail
        ORDER BY id ASC
        """)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return {"valid": True, "blocks_verified": 0, "message": "Audit ledger is currently empty."}

        expected_prev = GENESIS_HASH
        for idx, row in enumerate(rows):
            bid = row["id"]
            prev_hash = row["previous_hash"]
            cur_hash = row["current_hash"]
            actor = row["agent_name"] or row["actor_id"]
            action = row["action_type"]
            tool = row["tool_name"]
            created = row["created_at"]

            try:
                inp = json.loads(row["tool_input_json"] or "{}")
                out = json.loads(row["tool_output_json"] or "{}")
            except Exception:
                inp = {}
                out = {}

            # Check 1: Previous hash link
            if prev_hash != expected_prev:
                return {
                    "valid": False,
                    "tampered_block_id": bid,
                    "error": f"Chain broken at Block #{bid}: stored previous_hash '{prev_hash}' does not match expected '{expected_prev}'."
                }

            # Check 2: Recompute current hash
            recomputed = AuditService.calculate_payload_hash(
                prev_hash=prev_hash,
                agent_name=actor,
                action_type=action,
                tool_name=tool,
                tool_input=inp,
                tool_output=out,
                timestamp_utc=created
            )

            # Fallback check if actor was recorded under actor_id instead of agent_name
            if recomputed != cur_hash and "actor_id" in row.keys() and row["actor_id"] and row["actor_id"] != actor:
                alt_recomputed = AuditService.calculate_payload_hash(
                    prev_hash=prev_hash,
                    agent_name=row["actor_id"],
                    action_type=action,
                    tool_name=tool,
                    tool_input=inp,
                    tool_output=out,
                    timestamp_utc=created
                )
                if alt_recomputed == cur_hash:
                    recomputed = alt_recomputed

            if recomputed != cur_hash:
                return {
                    "valid": False,
                    "tampered_block_id": bid,
                    "error": f"Tampering detected in Block #{bid}: stored hash '{cur_hash}' does not match recomputed payload hash '{recomputed}'."
                }

            expected_prev = cur_hash

        return {
            "valid": True,
            "blocks_verified": len(rows),
            "head_hash": expected_prev,
            "message": f"Cryptographic integrity verified. All {len(rows)} blocks unbroken."
        }
