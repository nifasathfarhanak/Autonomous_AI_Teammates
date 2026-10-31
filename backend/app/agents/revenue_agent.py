"""DealPilot AI Agent 1: Revenue Intelligence Agent.
Discovers missed revenue opportunities from ingested CRM/CSV records using a deterministic mathematical scoring model.
"""

import json
from typing import Dict, Any, List
from datetime import datetime, date
from ..database import get_connection

class RevenueIntelligenceAgent:
    """Discovers missed revenue opportunities, calculates transparent scores (0-100), and ranks priority."""

    def __init__(self, merchant_id: str = "MERCH-001"):
        self.merchant_id = merchant_id
        self.agent_name = "RevenueIntelligenceAgent"

    def calculate_recovery_score(self, customer: Dict[str, Any], ref_date: str = "2026-10-30") -> Dict[str, Any]:
        """Calculates transparent recovery opportunity score based on 5 strict weighted factors:
        1. Historical Customer Value (25%)
        2. Purchase Intent (25%)
        3. Recency of Interaction (20%)
        4. Outstanding Quotation (20%)
        5. Engagement History (10%)
        Total: 100 points.
        """
        # 1. Historical Customer Value (Max 25 pts)
        ltv = float(customer.get("lifetime_value", 0.0) or 0.0)
        if ltv >= 200000.0:
            hist_pts = 25
        elif ltv >= 100000.0:
            hist_pts = 20
        elif ltv >= 50000.0:
            hist_pts = 15
        elif ltv >= 10000.0:
            hist_pts = 10
        else:
            hist_pts = 5

        # 2. Purchase Intent (Max 25 pts)
        interested_product = str(customer.get("interested_product", "") or "").strip()
        q_status = str(customer.get("quotation_status", "NONE") or "NONE").upper()
        if interested_product and q_status in ("UNANSWERED", "SENT"):
            intent_pts = 25
        elif interested_product:
            intent_pts = 18
        else:
            intent_pts = 5

        # 3. Recency of Interaction (Max 20 pts)
        last_int = customer.get("last_interaction_date") or customer.get("last_purchase_date")
        days_since_int = 30
        if last_int:
            try:
                d1 = datetime.strptime(last_int, "%Y-%m-%d").date()
                d2 = datetime.strptime(ref_date, "%Y-%m-%d").date()
                days_since_int = max(1, (d2 - d1).days)
            except Exception:
                days_since_int = 30

        # Sweet spot for recovery: 14 to 90 days
        if 14 <= days_since_int <= 45:
            recency_pts = 20
        elif 46 <= days_since_int <= 90:
            recency_pts = 16
        elif days_since_int < 14:
            recency_pts = 12  # Too recent
        else:
            recency_pts = 8   # Very cold

        # 4. Outstanding Quotation (Max 20 pts)
        q_val = float(customer.get("quotation_value", 0.0) or 0.0)
        if q_val > 0 and q_status == "UNANSWERED":
            quote_pts = 20
        elif q_val > 0 and q_status == "SENT":
            quote_pts = 16
        elif q_status == "EXPIRED":
            quote_pts = 10
        else:
            quote_pts = 0

        # 5. Engagement History (Max 10 pts)
        last_pur_val = float(customer.get("last_purchase_value", 0.0) or 0.0)
        if q_status == "UNANSWERED":
            eng_pts = 5  # Unanswered quotation indicates pending engagement
        elif last_pur_val > 100000.0:
            eng_pts = 10
        elif last_pur_val > 50000.0:
            eng_pts = 8
        else:
            eng_pts = 5

        total_score = hist_pts + intent_pts + recency_pts + quote_pts + eng_pts

        return {
            "total_score": total_score,
            "days_since_interaction": days_since_int,
            "breakdown": {
                "historical_value_pts": {"points": hist_pts, "max": 25, "weight": "25%"},
                "purchase_intent_pts": {"points": intent_pts, "max": 25, "weight": "25%"},
                "recency_interaction_pts": {"points": recency_pts, "max": 20, "weight": "20%"},
                "outstanding_quotation_pts": {"points": quote_pts, "max": 20, "weight": "20%"},
                "engagement_history_pts": {"points": eng_pts, "max": 10, "weight": "10%"}
            }
        }

    def discover_opportunities(self, min_score_threshold: int = 50) -> List[Dict[str, Any]]:
        """Scans all customers, evaluates recovery opportunity, and persists to opportunities table."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM customers WHERE merchant_id = ? AND is_unsubscribed = 0", (self.merchant_id,))
        customers = [dict(r) for r in cur.fetchall()]

        opportunities = []
        for cust in customers:
            score_data = self.calculate_recovery_score(cust)
            score = score_data["total_score"]

            if score < min_score_threshold:
                continue

            q_status = str(cust.get("quotation_status", "NONE")).upper()
            q_val = float(cust.get("quotation_value", 0.0) or 0.0)
            ltv = float(cust.get("lifetime_value", 0.0) or 0.0)
            product = cust.get("interested_product", "General inquiry")
            days_int = score_data["days_since_interaction"]

            # Categorize Opportunity
            if q_val > 0 and q_status in ("UNANSWERED", "SENT"):
                category = "UNANSWERED_QUOTATION"
                opp_value = q_val
                evidence = f"Customer was sent quotation for ₹{q_val:,.0f} on {cust.get('last_interaction_date')} ({days_int} days ago) for '{product}' with no response."
                rec_action = "Follow up on outstanding quotation with clarification offer."
            elif ltv >= 150000.0:
                category = "INACTIVE_HIGH_LTV"
                opp_value = round(ltv * 0.25, 2)
                evidence = f"High-LTV customer (₹{ltv:,.0f} spend) has had zero purchases for {days_int} days. Prior interest: '{product}'."
                rec_action = "Executive VIP re-engagement with tailored seasonal offer."
            else:
                category = "UNCONVERTED_INTEREST"
                opp_value = float(cust.get("last_purchase_value", 25000.0) or 25000.0)
                evidence = f"Customer showed purchase interest in '{product}' {days_int} days ago without completing an order."
                rec_action = "Consultative follow-up to address questions or technical specifications."

            opp_id = f"OPP-{cust['customer_id']}"
            cur.execute("""
            INSERT OR REPLACE INTO opportunities (
                opportunity_id, customer_id, merchant_id, opportunity_category,
                estimated_opportunity_value, recovery_score, score_breakdown_json,
                evidence_summary, recommended_next_action, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'IDENTIFIED')
            """, (
                opp_id, cust["customer_id"], self.merchant_id, category,
                opp_value, score, json.dumps(score_data["breakdown"]),
                evidence, rec_action
            ))

            opportunities.append({
                "opportunity_id": opp_id,
                "customer": cust,
                "category": category,
                "estimated_opportunity_value": opp_value,
                "recovery_score": score,
                "score_breakdown": score_data["breakdown"],
                "evidence_summary": evidence,
                "recommended_next_action": rec_action
            })

        conn.commit()
        conn.close()

        # Sort descending by recovery score
        opportunities.sort(key=lambda x: x["recovery_score"], reverse=True)
        return opportunities
