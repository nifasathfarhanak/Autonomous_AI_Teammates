"""Paytm AI ActionMate Governance, Permission Control & Approval Engine.
Implements:
1. 3-Category Action Risk Policy:
   - CATEGORY A: Automatic (read-only queries, calculations, draft preparation)
   - CATEGORY B: Human Approval Required (customer communications, campaign dispatches)
   - CATEGORY C: Human-Only / Financial Operation (refunds, bank/settlement changes - strictly blocked for AI)
2. Strict Backend Precondition Enforcement:
   - Verification of existence, correct merchant, authorized approver, zero content drift, non-paused, non-duplicate
3. Human-in-the-Loop Approval Workflows:
   - Approve, Reject, Edit (auto-invalidates prior approval), Request Changes, Pause, Resume
"""

import time
import json
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from ..database import get_connection
from ..schemas import (
    ApprovalRequestSchema,
    ApprovalRecordSchema,
    PolicyEvaluationSchema
)

# =====================================================================
# 1. Action Risk Policy Definitions
# =====================================================================

CATEGORY_A = "CATEGORY_A"  # Automatic: read lookups, analytics, drafts
CATEGORY_B = "CATEGORY_B"  # Human Approval Required: customer outreach, execution
CATEGORY_C = "CATEGORY_C"  # Human-Only / Blocked: refunds, financial mutations

# Mapping of all actions/tools to Risk Policy Categories
ACTION_RISK_MAP = {
    # Category A: Automatic lookups & calculations
    "get_merchant_profile": CATEGORY_A,
    "get_sales_summary": CATEGORY_A,
    "get_weekly_sales": CATEGORY_A,
    "compare_sales_periods": CATEGORY_A,
    "get_repeat_purchase_trend": CATEGORY_A,
    "get_customer_segment": CATEGORY_A,
    "get_customer_segments": CATEGORY_A,
    "get_customer_purchase_history": CATEGORY_A,
    "get_product_performance": CATEGORY_A,
    "get_business_insights": CATEGORY_A,
    "get_campaign_history": CATEGORY_A,
    "recommend_campaign": CATEGORY_A,
    "analyse_customer_segment": CATEGORY_A,
    "calculate_campaign_audience": CATEGORY_A,
    "preview_campaign": CATEGORY_A,
    "validate_campaign_recipients": CATEGORY_A,
    "create_campaign_draft": CATEGORY_A,
    "generate_campaign_message": CATEGORY_A,
    "submit_campaign_for_approval": CATEGORY_A,
    "verify_campaign_execution": CATEGORY_A,
    "calculate_operational_kpis": CATEGORY_A,
    "generate_task_report": CATEGORY_A,
    "escalate_task_to_human": CATEGORY_A,

    # Category B: Human Approval Required
    "execute_demo_campaign": CATEGORY_B,
    "retry_campaign_execution": CATEGORY_B,
    "broadcast_soundbox_voice": CATEGORY_B,
    "send_customer_message": CATEGORY_B,
    "launch_marketing_campaign": CATEGORY_B,

    # Category C: Human-Only / Financial Operations (Strictly Blocked for Autonomous AI)
    "issue_refund": CATEGORY_C,
    "process_customer_refund": CATEGORY_C,
    "modify_bank_account": CATEGORY_C,
    "change_settlement_schedule": CATEGORY_C,
    "grant_admin_privileges": CATEGORY_C,
    "update_merchant_kyc": CATEGORY_C,
    "alter_payment_gateway_keys": CATEGORY_C,
    "withdraw_merchant_funds": CATEGORY_C
}

AUTHORIZED_APPROVERS = {
    "USER-001": {"name": "Ramesh Sharma", "role": "MERCHANT_OWNER", "merchant_id": "MERCH-001"},
    "USER-002": {"name": "Pooja Sharma", "role": "FINANCE_DIRECTOR", "merchant_id": "MERCH-001"},
    "Ramesh Sharma (Merchant Owner)": {"name": "Ramesh Sharma", "role": "MERCHANT_OWNER", "merchant_id": "MERCH-001"}
}

HMAC_SECRET = b"PAYTM_ACTIONMATE_GOVERNANCE_SECRET_KEY_2026"

class PolicyViolationError(Exception):
    """Raised when an operation violates the Action Risk Policy."""
    pass

class ApprovalPreconditionError(Exception):
    """Raised when one of the 6 backend execution preconditions fails."""
    pass

class ContentDriftError(ApprovalPreconditionError):
    """Raised when campaign message content has drifted after approval."""
    pass

# =====================================================================
# 2. Governance & Policy Engine Service
# =====================================================================

class GovernanceService:
    """Central authority for Action Risk Policies, Approvals, and Execution Gates."""

    @staticmethod
    def calculate_content_hash(
        campaign_name: str,
        body_en: str,
        body_hi: str,
        offer_details: Optional[Dict[str, Any]] = None,
        target_segment: str = "DECLINING_FREQUENCY"
    ) -> str:
        """Calculates a deterministic SHA-256 fingerprint of campaign content."""
        offer_str = json.dumps(offer_details or {}, sort_keys=True)
        raw = f"{campaign_name}|{body_en.strip()}|{body_hi.strip()}|{offer_str}|{target_segment}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()

    @staticmethod
    def evaluate_action_policy(
        action_name: str,
        caller: str = "ActionMate AI Teammate",
        has_approval: bool = False
    ) -> PolicyEvaluationSchema:
        """Evaluates an action against the 3-category Risk Policy."""
        category = ACTION_RISK_MAP.get(action_name, CATEGORY_A)

        if category == CATEGORY_C:
            return PolicyEvaluationSchema(
                action_name=action_name,
                category=CATEGORY_C,
                allowed=False,
                requires_human_approval=True,
                is_financial_mutation=True,
                reason=(
                    f"FINANCIAL_ACTION_BLOCKED: Action '{action_name}' is classified as CATEGORY C "
                    f"(Human-Only / Financial Operation). Autonomous teammates are strictly prohibited "
                    f"from modifying bank details, altering settlement schedules, or executing refunds."
                )
            )

        if category == CATEGORY_B:
            if not has_approval:
                return PolicyEvaluationSchema(
                    action_name=action_name,
                    category=CATEGORY_B,
                    allowed=False,
                    requires_human_approval=True,
                    is_financial_mutation=False,
                    reason=(
                        f"HUMAN_APPROVAL_REQUIRED: Action '{action_name}' is classified as CATEGORY B "
                        f"(Customer Outreach / Outbound Action). Merchant approval is strictly required."
                    )
                )
            else:
                return PolicyEvaluationSchema(
                    action_name=action_name,
                    category=CATEGORY_B,
                    allowed=True,
                    requires_human_approval=True,
                    is_financial_mutation=False,
                    reason=f"Action '{action_name}' approved by authorized merchant."
                )

        # Category A: Automatic
        return PolicyEvaluationSchema(
            action_name=action_name,
            category=CATEGORY_A,
            allowed=True,
            requires_human_approval=False,
            is_financial_mutation=False,
            reason=f"Action '{action_name}' is classified as CATEGORY A (Automatic). Permitted without human gate."
        )

    # -----------------------------------------------------------------
    # Approval Request Formulation & Retrieval
    # -----------------------------------------------------------------

    @staticmethod
    def get_approval_request(campaign_id: str = "CAMP-REC-1042") -> Optional[ApprovalRequestSchema]:
        """Builds comprehensive approval request view for the merchant dashboard."""
        from .campaign_service import CampaignService
        draft = CampaignService.get_campaign_draft(campaign_id)
        if not draft:
            rec = CampaignService.recommend_campaign_for_sales_drop("MERCH-001")
            draft = CampaignService.create_campaign_draft({
                "campaign_id": campaign_id,
                "merchant_id": "MERCH-001",
                "campaign_name": rec.campaign_name,
                "business_objective": rec.business_objective,
                "reason_for_recommendation": rec.reason_for_recommendation,
                "target_customer_segment": "DECLINING_FREQUENCY",
                "offer_configured": True,
                "offer_details": rec.offer_details
            })

        # Calculate live audience breakdown
        aud = CampaignService.evaluate_campaign_audience(draft.merchant_id, draft.target_customer_segment)

        # Live content fingerprint
        en_msg = draft.messages.get("en", "")
        hi_msg = draft.messages.get("hi", "")
        chash = GovernanceService.calculate_content_hash(
            draft.campaign_name, en_msg, hi_msg, draft.offer_details, draft.target_customer_segment
        )
        from .sales_intelligence_service import get_merchant_profile
        merchant_name = get_merchant_profile(draft.merchant_id).store_name

        return ApprovalRequestSchema(
            approval_id=f"APPR-REQ-{campaign_id}",
            task_id="WF-REC-1042",
            campaign_id=campaign_id,
            merchant_id=draft.merchant_id,
            merchant_name=merchant_name,
            campaign_name=draft.campaign_name,
            campaign_purpose=draft.business_objective,
            reason_for_recommendation=draft.reason_for_recommendation,
            target_audience=f"{draft.target_customer_segment} ({aud.eligible_count} eligible, {aud.excluded_count} excluded)",
            customer_count=aud.eligible_count,
            promotional_message=draft.messages or {},
            campaign_settings={
                "max_liability_budget_inr": (draft.offer_details or {}).get("max_liability_cap_inr", 3600.0),
                "discount_code": (draft.offer_details or {}).get("discount_code", "GROCERY50"),
                "discount_amount_inr": (draft.offer_details or {}).get("discount_amount_inr", 50.0),
                "min_order_inr": (draft.offer_details or {}).get("min_order_inr", 499.0),
                "channels": ["SMS", "WhatsApp", "Paytm Soundbox Voice Announcement"]
            },
            execution_mode="SIMULATED_DEMO",
            risks_and_assumptions=draft.risks_and_assumptions,
            ai_recommendation={
                "strategy": "Grocery repeat-basket recovery",
                "target_cohort": "Regular neighborhood grocery shoppers",
                "soundbox_integration": "Audio banner broadcast & QR code telemetry"
            },
            current_status=draft.status,
            message_version=1,
            content_hash=chash,
            created_at=draft.created_at,
            is_demo=True
        )

    # -----------------------------------------------------------------
    # Approval Decisions: Approve, Reject, Edit, Request Changes, Pause
    # -----------------------------------------------------------------

    @staticmethod
    def approve_campaign(
        campaign_id: str,
        approver_id: str = "USER-001",
        max_budget_authorized: float = 3600.0,
        comments: str = "Approved by merchant owner for weekend run."
    ) -> ApprovalRecordSchema:
        """Approves campaign with cryptographic HMAC signature and records content hash."""
        from .campaign_service import CampaignService
        from .audit_service import AuditService

        # Precondition: Validate Approver
        approver_info = AUTHORIZED_APPROVERS.get(approver_id)
        if not approver_info:
            raise PolicyViolationError(
                f"UNAUTHORIZED_APPROVER: User '{approver_id}' is not an authorized approver for merchant 'MERCH-001'."
            )

        draft = CampaignService.get_campaign_draft(campaign_id)
        if not draft:
            raise ApprovalPreconditionError(f"Campaign '{campaign_id}' not found.")

        # Compute content fingerprint
        en_msg = draft.messages.get("en", "")
        hi_msg = draft.messages.get("hi", "")
        chash = GovernanceService.calculate_content_hash(
            draft.campaign_name, en_msg, hi_msg, draft.offer_details, draft.target_customer_segment
        )

        # Generate HMAC-SHA256 signature
        now_utc = datetime.now(timezone.utc).isoformat()
        payload = f"{campaign_id}|MERCH-001|{approver_id}|{max_budget_authorized}|{chash}|{now_utc}"
        sig = hmac.new(HMAC_SECRET, payload.encode('utf-8'), hashlib.sha256).hexdigest()

        approval_id = f"APPR-GOV-{campaign_id}-{int(time.time() * 1000000)}"

        conn = get_connection()
        cur = conn.cursor()

        # Invalidate any prior active approvals for this campaign
        cur.execute("""
        UPDATE approvals
        SET approval_status = 'SUPERSEDED'
        WHERE (campaign_id = ? OR workflow_id = ?) AND approval_status = 'VALID'
        """, (campaign_id, campaign_id))

        # Insert new valid approval
        cur.execute("""
        INSERT INTO approvals (
            id, workflow_id, task_id, campaign_id, merchant_id, approver_id,
            decision, approved_by, max_budget_authorized_inr, message_override,
            message_version, content_hash, reason_or_comments, approval_status,
            auth_signature, decided_at
        ) VALUES (?, ?, 'WF-REC-1042', ?, 'MERCH-001', ?, 'APPROVED', ?, ?, ?, 1, ?, ?, 'VALID', ?, ?)
        """, (
            approval_id, campaign_id, campaign_id, approver_id, approver_info["name"],
            max_budget_authorized, en_msg, chash, comments, sig, now_utc
        ))

        # Transition campaign draft state to APPROVED
        cur.execute("UPDATE campaign_drafts SET status = 'APPROVED', updated_at = ? WHERE campaign_id = ?", (now_utc, campaign_id))
        conn.commit()
        conn.close()

        # Append to audit ledger
        AuditService.log_audit_event(
            merchant_id="MERCH-001",
            task_id="WF-REC-1042",
            actor_id=approver_info["name"],
            action="CAMPAIGN_APPROVED",
            resource=f"campaign:{campaign_id}",
            previous_state=draft.status,
            new_state="APPROVED",
            tool_name="approve_campaign",
            tool_input={"budget": max_budget_authorized, "comments": comments},
            tool_output={"approval_id": approval_id, "signature": sig, "content_hash": chash}
        )

        return ApprovalRecordSchema(
            approval_id=approval_id,
            task_id="WF-REC-1042",
            campaign_id=campaign_id,
            merchant_id="MERCH-001",
            approver_id=approver_id,
            decision="APPROVED",
            timestamp=now_utc,
            message_version=1,
            content_hash=chash,
            reason_or_comments=comments,
            approval_status="VALID",
            max_budget_authorized_inr=max_budget_authorized,
            auth_signature=sig
        )

    @staticmethod
    def reject_campaign(
        campaign_id: str,
        approver_id: str = "USER-001",
        reason: str = "Merchant declined campaign strategy."
    ) -> Dict[str, Any]:
        """Rejects campaign, updates status to REJECTED, and blocks execution."""
        from .campaign_service import CampaignService
        from .audit_service import AuditService

        approver_info = AUTHORIZED_APPROVERS.get(approver_id)
        if not approver_info:
            raise PolicyViolationError(f"User '{approver_id}' is not authorized to reject campaigns.")

        draft = CampaignService.get_campaign_draft(campaign_id)
        prev_state = draft.status if draft else "PENDING_APPROVAL"
        now_utc = datetime.now(timezone.utc).isoformat()
        approval_id = f"APPR-REJ-{campaign_id}-{int(time.time() * 1000000)}"

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO approvals (
            id, workflow_id, task_id, campaign_id, merchant_id, approver_id,
            decision, approved_by, max_budget_authorized_inr, message_override,
            message_version, content_hash, reason_or_comments, approval_status,
            auth_signature, decided_at
        ) VALUES (?, ?, 'WF-REC-1042', ?, 'MERCH-001', ?, 'REJECTED', ?, 0.0, '', 1, '', ?, 'VALID', 'REJECTED_BY_MERCHANT', ?)
        """, (approval_id, campaign_id, campaign_id, approver_id, approver_info["name"], reason, now_utc))

        cur.execute("UPDATE campaign_drafts SET status = 'REJECTED', updated_at = ? WHERE campaign_id = ?", (now_utc, campaign_id))
        conn.commit()
        conn.close()

        AuditService.log_audit_event(
            merchant_id="MERCH-001",
            task_id="WF-REC-1042",
            actor_id=approver_info["name"],
            action="CAMPAIGN_REJECTED",
            resource=f"campaign:{campaign_id}",
            previous_state=prev_state,
            new_state="REJECTED",
            tool_name="reject_campaign",
            tool_input={"reason": reason},
            tool_output={"status": "REJECTED"}
        )

        return {"approval_id": approval_id, "status": "REJECTED", "reason": reason}

    @staticmethod
    def edit_campaign(
        campaign_id: str,
        editor_id: str = "USER-001",
        new_en_message: Optional[str] = None,
        new_hi_message: Optional[str] = None,
        new_offer_details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Edits campaign message or offer. STRICTLY INVALIDATES previous approval and requires fresh sign-off."""
        from .campaign_service import CampaignService
        from .audit_service import AuditService

        draft = CampaignService.get_campaign_draft(campaign_id)
        if not draft:
            raise ApprovalPreconditionError(f"Campaign '{campaign_id}' not found.")

        now_utc = datetime.now(timezone.utc).isoformat()
        messages = draft.messages or {}
        if new_en_message:
            messages["en"] = new_en_message
        if new_hi_message:
            messages["hi"] = new_hi_message

        offer = new_offer_details if new_offer_details is not None else draft.offer_details

        conn = get_connection()
        cur = conn.cursor()

        # Invalidate any previously valid approvals for this campaign
        cur.execute("""
        UPDATE approvals
        SET approval_status = 'INVALIDATED',
            reason_or_comments = 'Approval invalidated due to message/offer modification by merchant'
        WHERE (campaign_id = ? OR workflow_id = ?) AND approval_status = 'VALID'
        """, (campaign_id, campaign_id))

        # Revert campaign status to PENDING_APPROVAL and increment version
        cur.execute("""
        UPDATE campaign_drafts
        SET messages_json = ?, offer_json = ?, status = 'PENDING_APPROVAL', updated_at = ?
        WHERE campaign_id = ?
        """, (json.dumps(messages), json.dumps(offer), now_utc, campaign_id))

        conn.commit()
        conn.close()

        AuditService.log_audit_event(
            merchant_id="MERCH-001",
            task_id="WF-REC-1042",
            actor_id=editor_id,
            action="CAMPAIGN_EDITED_APPROVAL_INVALIDATED",
            resource=f"campaign:{campaign_id}",
            previous_state=draft.status,
            new_state="PENDING_APPROVAL",
            tool_name="edit_campaign",
            tool_input={"new_en_message": new_en_message, "new_offer_details": new_offer_details},
            tool_output={"status": "APPROVAL_INVALIDATED_FRESH_APPROVAL_REQUIRED"}
        )

        return {
            "campaign_id": campaign_id,
            "status": "PENDING_APPROVAL",
            "approval_status": "INVALIDATED",
            "message": "Campaign modified. Previous human approval invalidated. Fresh merchant sign-off required before execution."
        }

    @staticmethod
    def request_changes(
        campaign_id: str,
        approver_id: str = "USER-001",
        change_notes: str = "Please reduce discount amount and target VIPs only."
    ) -> Dict[str, Any]:
        """Requests revisions from the AI teammate; pauses workflow execution."""
        from .campaign_service import CampaignService
        from .audit_service import AuditService

        approver_info = AUTHORIZED_APPROVERS.get(approver_id)
        draft = CampaignService.get_campaign_draft(campaign_id)
        now_utc = datetime.now(timezone.utc).isoformat()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE campaign_drafts SET status = 'CHANGES_REQUESTED', updated_at = ? WHERE campaign_id = ?", (now_utc, campaign_id))
        cur.execute("""
        UPDATE approvals SET approval_status = 'INVALIDATED', reason_or_comments = ?
        WHERE (campaign_id = ? OR workflow_id = ?) AND approval_status = 'VALID'
        """, (f"Changes requested: {change_notes}", campaign_id, campaign_id))
        conn.commit()
        conn.close()

        AuditService.log_audit_event(
            merchant_id="MERCH-001",
            task_id="WF-REC-1042",
            actor_id=(approver_info["name"] if approver_info else approver_id),
            action="CAMPAIGN_CHANGES_REQUESTED",
            resource=f"campaign:{campaign_id}",
            previous_state=(draft.status if draft else "PENDING_APPROVAL"),
            new_state="CHANGES_REQUESTED",
            tool_name="request_changes",
            tool_input={"change_notes": change_notes},
            tool_output={"status": "CHANGES_REQUESTED"}
        )

        return {"campaign_id": campaign_id, "status": "CHANGES_REQUESTED", "notes": change_notes}

    @staticmethod
    def pause_task(campaign_id: str, actor: str = "Ramesh Sharma", reason: str = "Merchant paused campaign execution.") -> Dict[str, Any]:
        """Pauses a campaign; strictly blocks any pending execution."""
        from .campaign_service import CampaignService
        from .audit_service import AuditService

        draft = CampaignService.get_campaign_draft(campaign_id)
        prev = draft.status if draft else "ACTIVE"
        now_utc = datetime.now(timezone.utc).isoformat()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE campaign_drafts SET status = 'PAUSED', updated_at = ? WHERE campaign_id = ?", (now_utc, campaign_id))
        conn.commit()
        conn.close()

        AuditService.log_audit_event(
            merchant_id="MERCH-001",
            task_id="WF-REC-1042",
            actor_id=actor,
            action="CAMPAIGN_PAUSED",
            resource=f"campaign:{campaign_id}",
            previous_state=prev,
            new_state="PAUSED",
            tool_name="pause_task",
            tool_input={"reason": reason},
            tool_output={"status": "PAUSED"}
        )

        return {"campaign_id": campaign_id, "status": "PAUSED", "reason": reason}

    @staticmethod
    def resume_task(campaign_id: str, actor: str = "Ramesh Sharma") -> Dict[str, Any]:
        """Resumes a paused campaign."""
        from .campaign_service import CampaignService
        from .audit_service import AuditService

        draft = CampaignService.get_campaign_draft(campaign_id)
        now_utc = datetime.now(timezone.utc).isoformat()

        # Check if it was previously approved
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT id FROM approvals
        WHERE (campaign_id = ? OR workflow_id = ?) AND decision = 'APPROVED' AND approval_status = 'VALID'
        LIMIT 1
        """, (campaign_id, campaign_id))
        has_valid_approval = cur.fetchone() is not None

        new_status = "APPROVED" if has_valid_approval else "PENDING_APPROVAL"
        cur.execute("UPDATE campaign_drafts SET status = ?, updated_at = ? WHERE campaign_id = ?", (new_status, now_utc, campaign_id))
        conn.commit()
        conn.close()

        AuditService.log_audit_event(
            merchant_id="MERCH-001",
            task_id="WF-REC-1042",
            actor_id=actor,
            action="CAMPAIGN_RESUMED",
            resource=f"campaign:{campaign_id}",
            previous_state="PAUSED",
            new_state=new_status,
            tool_name="resume_task",
            tool_input={},
            tool_output={"status": new_status}
        )

        return {"campaign_id": campaign_id, "status": new_status}

    # -----------------------------------------------------------------
    # Strict Pre-Execution Verification (The 6 Backend Preconditions)
    # -----------------------------------------------------------------

    @staticmethod
    def verify_execution_preconditions(campaign_id: str, caller: str = "SimulatedExecutionAdapter") -> Dict[str, Any]:
        """Enforces all 6 strict backend preconditions before allowing execution:
        1. Approval exists.
        2. Approval belongs to correct merchant.
        3. Approver is authorized.
        4. Campaign content has not changed since approval (zero content drift).
        5. Campaign is not paused, cancelled, or rejected.
        6. Execution has not already occurred (strict idempotency).
        """
        from .campaign_service import CampaignService

        draft = CampaignService.get_campaign_draft(campaign_id)
        if not draft:
            raise ApprovalPreconditionError(f"Precondition 1 Failed: Campaign '{campaign_id}' does not exist.")

        # 6. Not duplicate execution
        if draft.status == "COMPLETED" or draft.execution_id:
            raise ApprovalPreconditionError(
                f"Precondition 6 Failed (Idempotency): Campaign '{campaign_id}' has already been executed "
                f"under Execution ID '{draft.execution_id}'."
            )

        # 5. Not paused, rejected, or cancelled
        if draft.status == "PAUSED":
            raise ApprovalPreconditionError(
                f"Precondition 5 Failed: Campaign '{campaign_id}' is currently PAUSED. Dispatches are blocked."
            )
        if draft.status == "REJECTED":
            raise ApprovalPreconditionError(
                f"Precondition 5 Failed: Campaign '{campaign_id}' was REJECTED by merchant. Execution prohibited."
            )
        if draft.status == "CHANGES_REQUESTED":
            raise ApprovalPreconditionError(
                f"Precondition 5 Failed: Campaign '{campaign_id}' has pending changes requested. Fresh approval required."
            )

        # 1. Approval exists
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT * FROM approvals
        WHERE (campaign_id = ? OR workflow_id = ?) AND decision = 'APPROVED'
        ORDER BY id DESC LIMIT 1
        """, (campaign_id, campaign_id))
        appr = cur.fetchone()
        conn.close()

        if not appr:
            raise ApprovalPreconditionError(
                f"Precondition 1 Failed: No human approval record exists for campaign '{campaign_id}'. "
                f"Unapproved campaigns cannot be executed."
            )

        # Check validity status
        appr_status = appr["approval_status"]
        if appr_status != "VALID":
            raise ApprovalPreconditionError(
                f"Precondition 1 Failed: Approval record for campaign '{campaign_id}' is '{appr_status}'. "
                f"Fresh approval required before execution."
            )

        # 2. Correct merchant
        if appr["merchant_id"] != draft.merchant_id:
            raise ApprovalPreconditionError(
                f"Precondition 2 Failed: Approval merchant '{appr['merchant_id']}' does not match "
                f"campaign merchant '{draft.merchant_id}'."
            )

        # 3. Authorized approver
        approver_id = appr["approver_id"]
        if approver_id not in AUTHORIZED_APPROVERS:
            raise ApprovalPreconditionError(
                f"Precondition 3 Failed: Approver '{approver_id}' is not in the merchant authorized roles."
            )

        # 4. Zero content drift verification
        en_msg = draft.messages.get("en", "")
        hi_msg = draft.messages.get("hi", "")
        current_hash = GovernanceService.calculate_content_hash(
            draft.campaign_name, en_msg, hi_msg, draft.offer_details, draft.target_customer_segment
        )

        stored_hash = appr["content_hash"]
        if stored_hash and stored_hash != current_hash:
            # Invalidate approval immediately
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
            UPDATE approvals SET approval_status = 'INVALIDATED',
                                reason_or_comments = 'Pre-execution check detected content drift. Approval invalidated.'
            WHERE id = ?
            """, (appr["id"],))
            cur.execute("UPDATE campaign_drafts SET status = 'PENDING_APPROVAL' WHERE campaign_id = ?", (campaign_id,))
            conn.commit()
            conn.close()

            raise ContentDriftError(
                f"Precondition 4 Failed (Content Drift): Campaign content has changed since approval was granted. "
                f"Previous approval is invalidated. A fresh merchant sign-off is required."
            )

        return {
            "verified": True,
            "campaign_id": campaign_id,
            "approval_id": appr["id"],
            "approver": appr["approved_by"],
            "content_hash": current_hash,
            "max_budget_authorized_inr": appr["max_budget_authorized_inr"]
        }
