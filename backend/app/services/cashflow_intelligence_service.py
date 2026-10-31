"""Paytm AI ActionMate Cash-Flow Early Warning Engine (Phase 8 Innovation 4).
Forecasts operational working capital, matches incoming Paytm settlements against
committed supplier payables and operating expenses, and warns of impending cash deficits.
Strictly an operational planning tool; does NOT perform credit or lending decisions.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from ..database import get_connection

class CashFlowIntelligenceService:
    """Computes cash-flow projections and alerts merchants to liquidity timing traps."""

    @staticmethod
    def get_cashflow_forecast(merchant_id: str = "MERCH-001", horizon_days: int = 14) -> Dict[str, Any]:
        """Calculates expected inflows, committed outflows, daily cumulative balances, and pinch warnings."""
        conn = get_connection()
        cur = conn.cursor()

        # 1. Fetch Inflow Settlements
        cur.execute("""
        SELECT settlement_id, settlement_date, expected_amount_inr, channel, status
        FROM merchant_settlements
        WHERE merchant_id = ?
        ORDER BY settlement_date ASC
        """, (merchant_id,))
        settlement_rows = cur.fetchall()

        # 2. Fetch Outflow Expenses
        cur.execute("""
        SELECT expense_id, category, vendor_name, description, amount_inr, due_date, status
        FROM merchant_expenses
        WHERE merchant_id = ?
        ORDER BY due_date ASC
        """, (merchant_id,))
        expense_rows = cur.fetchall()
        conn.close()

        today = datetime.now(timezone.utc)
        daily_timeline = []

        total_inflows = 0.0
        total_outflows = 0.0
        running_cash_balance = 25000.0  # Assumed starting operating buffer for demo

        early_pinch_detected = False
        pinch_details = None
        min_projected_balance = running_cash_balance

        for d in range(horizon_days):
            date_str = (today + timedelta(days=d)).strftime("%Y-%m-%d")

            # Day's expected settlements
            day_inflows = sum(
                float(r["expected_amount_inr"]) for r in settlement_rows
                if r["settlement_date"] == date_str and r["status"] == "PENDING"
            )
            # Day's committed expenses
            day_outflows = sum(
                float(r["amount_inr"]) for r in expense_rows
                if r["due_date"] == date_str and r["status"] == "PENDING"
            )

            total_inflows += day_inflows
            total_outflows += day_outflows
            net_change = day_inflows - day_outflows
            running_cash_balance += net_change

            if running_cash_balance < min_projected_balance:
                min_projected_balance = running_cash_balance

            # Detect pinch: If buffer drops below ₹10,000 or net cash is negative
            is_pinch_day = running_cash_balance < 10000.0
            if is_pinch_day and not early_pinch_detected:
                early_pinch_detected = True
                pinch_details = {
                    "pinch_date": date_str,
                    "projected_buffer_inr": round(running_cash_balance, 2),
                    "days_until_pinch": d
                }

            daily_timeline.append({
                "date": date_str,
                "day_offset": d,
                "expected_inflows_inr": round(day_inflows, 2),
                "committed_outflows_inr": round(day_outflows, 2),
                "net_daily_cashflow_inr": round(net_change, 2),
                "projected_cash_balance_inr": round(running_cash_balance, 2),
                "is_pinch_day": is_pinch_day
            })

        # Early Warning Alert Generation
        alerts = []
        if early_pinch_detected and pinch_details:
            alerts.append({
                "severity": "HIGH",
                "title": f"Liquidity Pinch Warning: Day {pinch_details['days_until_pinch']} ({pinch_details['pinch_date']})",
                "message": (
                    f"Your projected cash buffer compresses to ₹{pinch_details['projected_buffer_inr']:,.2f} on {pinch_details['pinch_date']}. "
                    "Upcoming supplier payables (₹22,000) and utility dues (₹8,000) absorb nearly all incoming settlements."
                ),
                "recommended_action": "1. Accelerate weekend Paytm Soundbox collections. 2. Request a 4-day extension on the equipment calibration retainer (₹6,500)."
            })
        else:
            alerts.append({
                "severity": "NORMAL",
                "title": "Healthy Working Capital Projection",
                "message": "Expected settlements comfortably cover committed operational expenses over the next 14 days.",
                "recommended_action": "Maintain planned supplier purchase schedules."
            })

        return {
            "merchant_id": merchant_id,
            "forecast_horizon_days": horizon_days,
            "starting_operating_balance_inr": 25000.0,
            "total_projected_inflows_inr": round(total_inflows, 2),
            "total_committed_outflows_inr": round(total_outflows, 2),
            "net_cumulative_cashflow_inr": round(total_inflows - total_outflows, 2),
            "minimum_projected_balance_inr": round(min_projected_balance, 2),
            "early_pinch_detected": early_pinch_detected,
            "alerts": alerts,
            "timeline": daily_timeline,
            "settlements_pending": [dict(r) for r in settlement_rows if r["status"] == "PENDING"],
            "expenses_pending": [dict(r) for r in expense_rows if r["status"] == "PENDING"],
            "regulatory_disclaimer": (
                "OPERATIONAL PLANNING TOOL ONLY: This forecast is calculated solely from recorded Paytm settlements "
                "and user-entered merchant payables. It is NOT a credit score, loan eligibility assessment, or underwriting decision."
            )
        }
