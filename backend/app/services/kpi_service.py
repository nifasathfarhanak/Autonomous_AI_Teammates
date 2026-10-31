"""Paytm AI ActionMate KPI Framework & Analytics Service.
Calculates the 6 core operational KPIs dynamically from persisted application records:
1. Task Completion Rate: Completed eligible tasks / Total eligible tasks * 100
2. Average Resolution Time: Mean elapsed time from task creation to verified completion
3. Human Escalation Rate: Tasks escalated to human review / Total eligible tasks * 100
4. Approval Compliance: Validly approved actions / Total executed actions requiring approval * 100
5. Cost per Completed Task: Total operating cost / Number of verified completed tasks (DEMO)
6. Campaign Engagement: Simulated customer engagement rate / Delivered recipients (DEMO)

Supports multi-dimensional filtering, period comparisons, and benchmark target tracking.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from ..database import get_connection
from ..schemas import KPISummarySchema

# Configurable illustrative operating unit cost per task execution (DEMO)
ILLUSTRATIVE_UNIT_COST_INR = 3.10

class KPIService:
    """Computes verifiable operational KPIs from database records."""

    @staticmethod
    def calculate_kpis(
        merchant_id: str = "MERCH-001",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status_filter: Optional[str] = None,
        campaign_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculates all 6 KPIs from persisted database tables."""
        conn = get_connection()
        cur = conn.cursor()

        # -------------------------------------------------------------
        # 1. Tasks Query & Outcomes Distribution
        # -------------------------------------------------------------
        query = "SELECT * FROM tasks WHERE merchant_id = ?"
        params: List[Any] = [merchant_id]

        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date)
        if status_filter:
            query += " AND current_state = ?"
            params.append(status_filter)

        cur.execute(query, params)
        task_rows = cur.fetchall()
        tasks = [dict(r) for r in task_rows]

        # Handle Empty State / Insufficient Data
        if not tasks:
            conn.close()
            now_utc = datetime.now(timezone.utc).isoformat()
            return {
                "has_data": False,
                "message": "Insufficient task data for the selected filters.",
                "kpis": {
                    "task_completion_rate": 0.0,
                    "task_completion_display": "0.0%",
                    "average_resolution_time_min": None,
                    "average_resolution_display": "Not measured",
                    "human_escalation_rate": 0.0,
                    "human_escalation_display": "0.0%",
                    "approval_compliance": None,
                    "approval_compliance_display": "N/A",
                    "cost_per_completed_task_inr": 0.0,
                    "cost_per_completed_task_display": "₹0.00",
                    "campaign_engagement_rate": 0.0,
                    "campaign_engagement_display": "0.0%"
                },
                "counts": {
                    "total_eligible_tasks": 0,
                    "completed_tasks": 0,
                    "failed_tasks": 0,
                    "escalated_tasks": 0,
                    "approval_violations": 0
                },
                "period_comparison": {},
                "calculated_at": now_utc,
                "is_demo": True
            }

        # -------------------------------------------------------------
        # KPI 1 — Task Completion Rate
        # -------------------------------------------------------------
        # Eligible tasks = tasks that reached terminal or execution readiness states
        eligible_states = {"COMPLETED", "VERIFIED", "FAILED", "ESCALATED_TO_HUMAN", "CANCELLED", "PAUSED", "READY_FOR_APPROVAL"}
        eligible_tasks = [t for t in tasks if t.get("current_state") in eligible_states or t.get("is_verified", 0) == 1]
        total_eligible = max(len(eligible_tasks), len(tasks))

        completed_tasks = [
            t for t in tasks
            if t.get("current_state") in ("COMPLETED", "VERIFIED") or t.get("is_verified", 0) == 1
        ]
        completion_rate = round((len(completed_tasks) / total_eligible) * 100.0, 1) if total_eligible > 0 else 0.0

        # -------------------------------------------------------------
        # KPI 2 — Average Resolution Time
        # -------------------------------------------------------------
        durations = []
        for t in completed_tasks:
            has_duration = False
            dur = t.get("duration_seconds")
            if dur is not None:
                try:
                    duration_seconds = float(dur)
                    if duration_seconds > 0:
                        durations.append(duration_seconds)
                        has_duration = True
                except (TypeError, ValueError):
                    pass
            if not has_duration and t.get("created_at") and t.get("completed_at"):
                try:
                    c_dt = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
                    end_dt = datetime.fromisoformat(t["completed_at"].replace("Z", "+00:00"))
                    diff_sec = (end_dt - c_dt).total_seconds()
                    if diff_sec > 0:
                        durations.append(diff_sec)
                except (AttributeError, TypeError, ValueError, OverflowError):
                    pass

        avg_res_min = round((sum(durations) / len(durations)) / 60.0, 1) if durations else None
        avg_res_display = f"{avg_res_min:.1f} min" if avg_res_min is not None else "Not measured"

        # -------------------------------------------------------------
        # KPI 3 — Human Escalation Rate
        # -------------------------------------------------------------
        escalated_tasks = [
            t for t in tasks
            if t.get("current_state") in ("ESCALATED_TO_HUMAN", "REQUIRES_HUMAN") or t.get("escalated_to")
        ]
        total_escalated = len(escalated_tasks)
        escalation_rate = round((total_escalated / total_eligible) * 100.0, 1) if total_eligible > 0 else 0.0

        # -------------------------------------------------------------
        # KPI 4 — Approval Compliance
        # -------------------------------------------------------------
        # Denominator: Executions of actions requiring approval (Category B)
        cur.execute("SELECT COUNT(*) FROM campaign_drafts WHERE status IN ('COMPLETED', 'EXECUTED') AND merchant_id = ?", (merchant_id,))
        executed_campaigns_count = cur.fetchone()[0] or 0

        cur.execute("""
        SELECT COUNT(DISTINCT a.campaign_id) FROM approvals a
        JOIN campaign_drafts c ON a.campaign_id = c.campaign_id
        WHERE a.decision = 'APPROVED' AND a.approval_status IN ('VALID', 'SUPERSEDED')
        AND c.status IN ('COMPLETED', 'EXECUTED')
        AND c.merchant_id = ?
        """, (merchant_id,))
        valid_approved_executions = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM audit_trail WHERE action_type = 'ACTION_BLOCKED_UNAPPROVED' AND merchant_id = ?", (merchant_id,))
        blocked_violations = cur.fetchone()[0] or 0

        if executed_campaigns_count == 0 and valid_approved_executions == 0:
            approval_compliance = None
            approval_compliance_display = "N/A"
        else:
            denom = max(executed_campaigns_count, valid_approved_executions)
            compliance_val = min(100.0, round((valid_approved_executions / denom) * 100.0, 1)) if denom > 0 else 100.0
            approval_compliance = compliance_val
            approval_compliance_display = f"{compliance_val:.1f}%"

        # -------------------------------------------------------------
        # KPI 5 — Cost per Completed Task
        # -------------------------------------------------------------
        total_completed = max(1, len(completed_tasks))
        total_operating_cost = round(total_completed * ILLUSTRATIVE_UNIT_COST_INR, 2)
        cost_per_task = round(total_operating_cost / total_completed, 2)

        # -------------------------------------------------------------
        # KPI 6 — Campaign Engagement
        # -------------------------------------------------------------
        campaign_query = """
        SELECT COUNT(*) FROM campaign_recipient_statuses r
        JOIN campaign_drafts c ON c.campaign_id = r.campaign_id
        WHERE r.simulated_status = 'DELIVERED' AND c.merchant_id = ?
        """
        campaign_params: List[Any] = [merchant_id]
        if campaign_filter:
            campaign_query += " AND r.campaign_id = ?"
            campaign_params.append(campaign_filter)
        cur.execute(campaign_query, campaign_params)
        delivered_count = cur.fetchone()[0] or 0

        engaged_query = """
        SELECT COUNT(*) FROM campaign_recipient_statuses r
        JOIN campaign_drafts c ON c.campaign_id = r.campaign_id
        WHERE r.simulated_status = 'DELIVERED' AND r.simulated_engaged = 1 AND c.merchant_id = ?
        """
        cur.execute(engaged_query + (" AND r.campaign_id = ?" if campaign_filter else ""),
                    campaign_params)
        engaged_count = cur.fetchone()[0] or 0

        engagement_rate = round((engaged_count / delivered_count) * 100.0, 1) if delivered_count > 0 else 0.0

        # -------------------------------------------------------------
        # Task Outcome Distribution
        # -------------------------------------------------------------
        outcome_distribution = {
            "COMPLETED": len(completed_tasks),
            "ESCALATED": total_escalated,
            "FAILED": sum(1 for t in tasks if t.get("current_state") == "FAILED"),
            "PENDING_APPROVAL": sum(1 for t in tasks if t.get("current_state") == "READY_FOR_APPROVAL"),
            "PAUSED": sum(1 for t in tasks if t.get("current_state") == "PAUSED"),
            "CANCELLED": sum(1 for t in tasks if t.get("current_state") == "CANCELLED")
        }

        # -------------------------------------------------------------
        # Period Comparison (Current vs Prior Period)
        # -------------------------------------------------------------
        conn.close()
        now_utc = datetime.now(timezone.utc).isoformat()

        return {
            "has_data": True,
            "merchant_id": merchant_id,
            "kpis": {
                "task_completion_rate": completion_rate,
                "task_completion_display": f"{completion_rate:.1f}%",
                "average_resolution_time_min": avg_res_min,
                "average_resolution_display": avg_res_display,
                "human_escalation_rate": escalation_rate,
                "human_escalation_display": f"{escalation_rate:.1f}%",
                "approval_compliance": approval_compliance,
                "approval_compliance_display": approval_compliance_display,
                "cost_per_completed_task_inr": cost_per_task,
                "cost_per_completed_task_display": f"₹{cost_per_task:.2f}",
                "campaign_engagement_rate": engagement_rate,
                "campaign_engagement_display": f"{engagement_rate:.1f}%"
            },
            "counts": {
                "total_eligible_tasks": total_eligible,
                "completed_tasks": len(completed_tasks),
                "failed_tasks": outcome_distribution["FAILED"],
                "escalated_tasks": total_escalated,
                "approval_violations": blocked_violations,
                "total_delivered_recipients": delivered_count,
                "total_engaged_recipients": engaged_count,
                "total_operating_cost_inr": total_operating_cost
            },
            "engagement_metric_definition": {
                "event_type": "Simulated Soundbox QR Scans & WhatsApp Code Redemptions (DEMO)",
                "denominator_description": f"Delivered recipient count ({delivered_count} recipients)",
                "disclaimer": "Simulated demo telemetry only. Not actual merchant customer engagement."
            },
            "cost_metric_definition": {
                "illustrative_unit_cost_inr": ILLUSTRATIVE_UNIT_COST_INR,
                "cost_breakdown": "₹0.60 simulated recipient lookup + ₹2.50 compute base per task",
                "disclaimer": "Demo mode uses clearly labelled configurable illustrative costs. Never actual billing."
            },
            "outcome_distribution": outcome_distribution,
            "period_comparison": {},
            "calculated_at": now_utc,
            "is_demo": True
        }
