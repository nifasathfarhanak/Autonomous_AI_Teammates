"""Paytm AI ActionMate Proactive Business Opportunity Discovery Engine (Phase 8 Innovation 8).
Continuously identifies actionable opportunities across Profit, Inventory, Cash-Flow, and Retention
without waiting for merchants to ask questions. Prioritizes by financial impact and urgency.
"""

import json
from typing import Dict, Any, List, Optional
from ..database import get_connection

class OpportunityDiscoveryService:
    """Scans business tables and surfaces prioritized commercial opportunities."""

    @staticmethod
    def get_ranked_opportunities(merchant_id: str = "MERCH-001") -> List[Dict[str, Any]]:
        """Returns proactive business opportunities scored and sorted by priority."""
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
        SELECT 
            opportunity_id, merchant_id, category, title, problem_statement,
            evidence_json, financial_impact_inr, recommended_action, expected_cost_inr,
            expected_benefit_inr, urgency_level, confidence_level, required_permission,
            verification_method, status, created_at
        FROM business_opportunities
        WHERE merchant_id = ?
        ORDER BY financial_impact_inr DESC
        """, (merchant_id,))
        rows = cur.fetchall()
        conn.close()

        opps = []
        urgency_weight = {"HIGH": 10.0, "MEDIUM": 6.0, "LOW": 3.0}

        for r in rows:
            data = dict(r)
            evidence = json.loads(data["evidence_json"]) if isinstance(data["evidence_json"], str) else (data["evidence_json"] or {})

            # Priority Score (0 to 100)
            # 40% Financial Impact (normalized to 100k) + 30% Urgency + 20% Confidence + 10% Permission Feasibility
            impact_score = min(40.0, (data["financial_impact_inr"] / 100000.0) * 40.0)
            urg_score = (urgency_weight.get(data["urgency_level"], 5.0) / 10.0) * 30.0
            conf_score = data["confidence_level"] * 20.0
            feasibility_score = 10.0 if data["required_permission"] == "CATEGORY_A" else (8.0 if data["required_permission"] == "CATEGORY_B" else 4.0)

            priority_rank_score = round(impact_score + urg_score + conf_score + feasibility_score, 1)

            opps.append({
                "opportunity_id": data["opportunity_id"],
                "category": data["category"],
                "title": data["title"],
                "problem_statement": data["problem_statement"],
                "evidence": evidence,
                "financial_impact_inr": data["financial_impact_inr"],
                "financial_impact_display": f"₹{data['financial_impact_inr']:,.2f}",
                "recommended_action": data["recommended_action"],
                "expected_cost_inr": data["expected_cost_inr"],
                "expected_benefit_inr": data["expected_benefit_inr"],
                "urgency_level": data["urgency_level"],
                "confidence_level": data["confidence_level"],
                "confidence_display": f"{int(data['confidence_level'] * 100)}%",
                "required_permission": data["required_permission"],
                "verification_method": data["verification_method"],
                "status": data["status"],
                "priority_rank_score": priority_rank_score
            })

        opps.sort(key=lambda x: x["priority_rank_score"], reverse=True)
        return opps

    @staticmethod
    def get_opportunity_summary(merchant_id: str = "MERCH-001") -> Dict[str, Any]:
        """Provides high-level opportunity counts and total pipeline value."""
        opps = OpportunityDiscoveryService.get_ranked_opportunities(merchant_id)

        total_value = round(sum(o["financial_impact_inr"] for o in opps), 2)
        high_urgency = [o for o in opps if o["urgency_level"] == "HIGH"]

        category_counts: Dict[str, int] = {}
        for o in opps:
            c = o["category"]
            category_counts[c] = category_counts.get(c, 0) + 1

        return {
            "merchant_id": merchant_id,
            "total_opportunities_discovered": len(opps),
            "total_unlocked_value_inr": total_value,
            "total_unlocked_value_display": f"₹{total_value:,.2f}",
            "high_urgency_count": len(high_urgency),
            "category_distribution": category_counts,
            "top_priority_opportunity": opps[0] if opps else None,
            "opportunities": opps
        }
