"""Paytm AI ActionMate Epistemic Reasoning Engine.
Synthesizes verified data from context tools into evidence-based explanations,
strictly categorizing knowledge into:
1. Confirmed Data (verified from SQLite / Soundbox telemetry)
2. AI Interpretation (grounded behavioral inferences)
3. Recommendations (actionable strategies)
4. Unknown Information (unverified external factors)
Never presents assumptions as confirmed facts.
"""

from typing import Dict, Any, List, Optional
from ..schemas import EpistemicReportSchema

class ReasoningEngine:
    """Evaluates business anomalies, customer attrition, and formulates evidence-based findings."""

    @staticmethod
    def evaluate(
        sales_drop: Dict[str, Any],
        repeat_analysis: Dict[str, Any],
        merchant_profile: Dict[str, Any],
        customer_segments: List[Dict[str, Any]],
        product_performance: List[Dict[str, Any]],
        sales_summary: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Synthesizes business context into findings and an epistemic report."""

        sales_summary = sales_summary or {}
        drop_pct = float(sales_drop.get("sales_percentage_difference", 0.0) or 0.0)
        diff_inr = abs(float(sales_drop.get("sales_difference_inr", 0.0) or 0.0))
        current_repeat_pct = float(repeat_analysis.get("week_4_pct", 0.0) or 0.0)
        prev_repeat_pct = float(repeat_analysis.get("week_3_pct", 0.0) or 0.0)
        repeat_drop_pts = float(repeat_analysis.get("drop_percentage_points", 0.0) or 0.0)
        at_risk_count = int(repeat_analysis.get("unreturned_regular_patrons", 0) or 0)
        leakage_inr = float(repeat_analysis.get("revenue_at_risk_inr", 0.0) or 0.0)
        soundbox_id = merchant_profile.get("soundbox_device_id", "Not connected")
        store_name = merchant_profile.get("store_name", "your store")
        category = str(merchant_profile.get("category", "")).lower()
        is_grocery = "grocery" in category
        discount_code = "GROCERY50" if is_grocery else "LOCAL50"
        min_order_inr = 499.0 if is_grocery else 249.0
        sales_last_week = float(sales_summary.get("last_week_total_k", 0.0) or 0.0) * 1000
        sales_this_week = float(sales_summary.get("this_week_total_k", 0.0) or 0.0) * 1000
        sales_change = "fell" if drop_pct < 0 else "rose"

        # 1. Confirmed Data (strictly grounded facts from SQLite database)
        confirmed_data = [
            f"Completed receipts for {store_name} show sales {sales_change} from ₹{sales_last_week:,.0f} last week "
            f"to ₹{sales_this_week:,.0f} this week ({drop_pct:+.1f}%; change of ₹{diff_inr:,.0f}).",
            f"Recorded repeat-order share changed from {prev_repeat_pct:.1f}% to {current_repeat_pct:.1f}% "
            f"({repeat_drop_pts:+.1f} percentage points).",
            f"{at_risk_count} named customers had repeat orders in the prior three weeks but none in the latest week.",
            (
                f"The seeded demo opportunity estimates ₹{leakage_inr:,.0f} at risk; this is not confirmed lost revenue or profit."
                if leakage_inr else "No revenue-at-risk estimate is recorded for this merchant."
            ),
            f"Merchant profile lists Soundbox {soundbox_id}; device status is {merchant_profile.get('soundbox_status', 'unknown')}.",
            f"These figures come from completed order records for {store_name}; they do not include unrecorded cash sales."
        ]

        # 2. AI Interpretation (grounded analytical deductions)
        ai_interpretation = [
            (
                "A lower repeat-order share suggests some regular shoppers may be visiting less often, "
                "but the records do not establish the cause."
                if repeat_drop_pts < 0 else
                "Repeat-order share did not decline in the compared weeks."
            ),
            "The sales pattern is a signal to investigate, not proof of competitor activity, customer churn, or a specific cause.",
            "A small, owner-approved offer can be tested against a holdout group before expanding it."
        ]

        # 3. Recommendations (actionable proposals)
        recommendations = [
            f"Review the {at_risk_count} customers with prior repeat orders and no receipt in the latest week before outreach.",
            f"Consider testing ₹50 off baskets above ₹{min_order_inr:,.0f} with code {discount_code}; verify product margin and stock first.",
            "Keep the ₹3,600 campaign liability cap and require owner approval before any customer message is sent.",
            f"Use the merchant's selected language for any Soundbox or customer-facing message for {store_name}.",
            "Require merchant cryptographic HMAC approval before any promotional dispatch can execute."
        ]

        # 4. Unknown Information (explicit awareness of boundaries)
        unknown_information = [
            "Competitor pricing actions or promotions launched near Connaught Place during this week are not captured in internal telemetry.",
            "Weather or road accessibility disruptions affecting footfall on Friday and Saturday are unverified.",
            "Individual customer intent and purchases at other stores cannot be confirmed from this merchant's receipts."
        ]

        epistemic_report = EpistemicReportSchema(
            confirmed_data=confirmed_data,
            ai_interpretation=ai_interpretation,
            recommendations=recommendations,
            unknown_information=unknown_information
        )

        concise_explanation = (
            f"Recorded sales {sales_change} by {abs(drop_pct):.1f}% (₹{diff_inr:,.0f}) and repeat-order share moved "
            f"from {prev_repeat_pct:.1f}% to {current_repeat_pct:.1f}%. {at_risk_count} prior repeat customers have no receipt "
            f"in the latest week. The estimated ₹{leakage_inr:,.0f} at-risk amount is not confirmed lost profit. "
            f"ActionMate proposes reviewing a capped {discount_code} offer; owner approval is required."
        )

        return {
            "sales_drop_detected": bool(sales_drop.get("is_drop_detected", False)),
            "drop_severity": sales_drop.get("drop_severity", "NONE"),
            "sales_drop_pct": drop_pct,
            "revenue_leakage_inr": leakage_inr,
            "missing_patrons_count": at_risk_count,
            "target_cohort_size": at_risk_count,
            "telemetry_source": f"Paytm Soundbox 4G Telemetry ({soundbox_id})",
            "explanation": concise_explanation,
            "epistemic_report": epistemic_report.dict(),
            "recommendation": {
                "campaign_name": f"{'Grocery' if is_grocery else 'Local'} Repeat-Customer Recovery",
                "discount_code": discount_code,
                "discount_amount_inr": 50.0,
                "min_order_inr": min_order_inr,
                "max_liability_cap_inr": 3600.0,
                "expected_redemption_rate_pct": None,
                "expected_redemptions": None,
                "expected_gross_sales_inr": None,
                "expected_net_margin_inr": None,
                "projected_roi_multiple": None
            }
        }
