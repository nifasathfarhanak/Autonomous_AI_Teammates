"""Paytm AI ActionMate Task Planner.
Generates structured 10-step execution plans with explicit tool requirements,
parameter bindings, risk levels, and human-in-the-loop approval gates.
"""

from typing import List, Dict, Any
from ..schemas import PlanStepSchema

class TaskPlanner:
    """Creates structured multi-step execution plans for autonomous business workflows."""

    @staticmethod
    def generate_plan(
        merchant_id: str = "MERCH-001",
        target_cohort_size: int = 46,
        discount_code: str = "GROCERY50",
        discount_amount_inr: float = 50.0,
        min_order_inr: float = 499.0,
        cap_inr: float = 3600.0,
        is_approved: bool = False,
        is_executed: bool = False,
        is_completed: bool = False
    ) -> List[PlanStepSchema]:
        """Generates the 10-step autonomous execution plan conforming strictly to Section 5."""

        return [
            PlanStepSchema(
                step_id="step_1_get_weekly_sales",
                step_number=1,
                name="Retrieve Weekly Sales",
                description="Fetch 7-day daily transaction totals and order counts from Paytm Soundbox telemetry.",
                tool_required="get_weekly_sales",
                input_parameters={"merchant_id": merchant_id, "period": "this_week"},
                expected_output="7-day daily grocery sales totals and receipt counts from merchant records.",
                risk_level="LOW",
                requires_approval=False,
                status="COMPLETED",
                execution_result={"status": "SUCCESS", "sales_total_k": 300.0, "days": 7}
            ),
            PlanStepSchema(
                step_id="step_2_compare_sales_periods",
                step_number=2,
                name="Compare with Previous Week",
                description="Compare this week's completed grocery receipts with the previous week's baseline.",
                tool_required="compare_sales_periods",
                input_parameters={"merchant_id": merchant_id},
                expected_output="Report the measured sales change and supporting daily receipt totals.",
                risk_level="LOW",
                requires_approval=False,
                status="COMPLETED",
                execution_result={"status": "SUCCESS", "is_drop_detected": True, "percentage_drop": -27.2}
            ),
            PlanStepSchema(
                step_id="step_3_get_repeat_purchase_trend",
                step_number=3,
                name="Analyse Repeat-Purchase Trend",
                description="Calculate four-week repeat-basket share and identify regular shoppers whose visits declined.",
                tool_required="get_repeat_purchase_trend",
                input_parameters={"merchant_id": merchant_id},
                expected_output="Severe repeat-customer drop from 37% to 24% (-13 percentage points, 46 absent patrons).",
                risk_level="LOW",
                requires_approval=False,
                status="COMPLETED",
                execution_result={"status": "SUCCESS", "week_4_rate": 24.0, "drop_pts": -13.0, "missing_patrons": 46}
            ),
            PlanStepSchema(
                step_id="step_4_get_customer_segments",
                step_number=4,
                name="Identify Suitable Customer Segments",
                description=f"Segment household shoppers and identify up to {target_cohort_size} regular customers for review.",
                tool_required="get_customer_segments",
                input_parameters={"merchant_id": merchant_id},
                expected_output=f"Target cohort identified: up to {target_cohort_size} regular grocery shoppers.",
                risk_level="LOW",
                requires_approval=False,
                status="COMPLETED",
                execution_result={"status": "SUCCESS", "target_cohort_size": target_cohort_size}
            ),
            PlanStepSchema(
                step_id="step_5_recommend_campaign",
                step_number=5,
                name="Recommend a Re-Engagement Campaign",
                description=f"Formulate an offer of ₹{discount_amount_inr:.0f} off baskets above ₹{min_order_inr:.0f}, subject to margin, stock, and owner approval.",
                tool_required="recommend_campaign",
                input_parameters={"merchant_id": merchant_id, "target_cohort_size": target_cohort_size},
                expected_output="Campaign parameters formulated with a strict budget cap; projected outcomes remain estimates.",
                risk_level="MEDIUM",
                requires_approval=False,
                status="COMPLETED",
                execution_result={
                    "status": "SUCCESS",
                    "discount_code": discount_code,
                    "discount_amount_inr": discount_amount_inr,
                    "min_order_inr": min_order_inr,
                    "max_liability_cap_inr": cap_inr,
                    "projected_roi": None
                }
            ),
            PlanStepSchema(
                step_id="step_6_draft_messages",
                step_number=6,
                name="Generate Personalised Messages",
                description="Draft localized promotional copy in English and Hindi, along with Soundbox audio voice script.",
                tool_required="draft_promo_messages",
                input_parameters={"discount_code": discount_code, "discount_amount_inr": discount_amount_inr},
                expected_output="Bilingual SMS/WhatsApp copy and Soundbox audio prompt synthesized.",
                risk_level="LOW",
                requires_approval=False,
                status="COMPLETED",
                execution_result={"status": "SUCCESS", "languages": ["en", "hi"], "soundbox_audio": True}
            ),
            PlanStepSchema(
                step_id="step_7_request_approval",
                step_number=7,
                name="Request Merchant Approval",
                description="Enforce mandatory human authorization gate. Merchant must verify parameters and sign with HMAC.",
                tool_required="request_merchant_approval",
                input_parameters={"budget_cap_inr": cap_inr, "requires_signature": True},
                expected_output="Cryptographic HMAC-SHA256 signature authorized by merchant.",
                risk_level="HIGH",
                requires_approval=True,
                status="COMPLETED" if is_approved else "PENDING_APPROVAL",
                execution_result={"status": "APPROVED" if is_approved else "AWAITING_MERCHANT_SIGN_OFF"}
            ),
            PlanStepSchema(
                step_id="step_8_simulate_execution",
                step_number=8,
                name="Execute the Approved Simulated Action",
                description=f"Dispatch simulated outreach to up to {target_cohort_size} eligible shoppers with opt-out and contact validation.",
                tool_required="execute_simulated_dispatch",
                input_parameters={"campaign_code": discount_code, "target_count": target_cohort_size},
                expected_output="Simulate outreach only to eligible, owner-approved recipients.",
                risk_level="HIGH",
                requires_approval=True,
                status="COMPLETED" if is_executed else ("READY_FOR_EXECUTION" if is_approved else "QUEUED"),
                execution_result={"status": "DISPATCHED" if is_executed else "QUEUED"}
            ),
            PlanStepSchema(
                step_id="step_9_verify_execution",
                step_number=9,
                name="Verify the Execution Result",
                description=f"Match recorded payment outcomes against campaign code {discount_code}.",
                tool_required="verify_pos_outcomes",
                input_parameters={"campaign_code": discount_code},
                expected_output="Report recorded redemptions and compare outcomes with baseline; do not infer unobserved profit.",
                risk_level="LOW",
                requires_approval=False,
                status="WAITING_FOR_DATA" if is_completed else ("READY_FOR_EXECUTION" if is_executed else "QUEUED"),
                execution_result={"status": "AWAITING_REAL_POST_CAMPAIGN_TRANSACTIONS" if is_completed else "QUEUED", "verified_redemptions": None}
            ),
            PlanStepSchema(
                step_id="step_10_report_outcome",
                step_number=10,
                name="Report the Outcome & Audit Trail",
                description="Publish the observed campaign outcome, its evidence, and the audit ledger.",
                tool_required="report_campaign_outcome",
                input_parameters={"merchant_id": merchant_id, "discount_code": discount_code},
                expected_output="Final executive report published with verifiable accounting attribution.",
                risk_level="LOW",
                requires_approval=False,
                status="COMPLETED" if is_completed else "QUEUED",
                execution_result={"status": "REPORTED" if is_completed else "QUEUED", "roi_multiple": None}
            )
        ]
