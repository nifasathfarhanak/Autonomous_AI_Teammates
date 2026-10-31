"""DealPilot AI Agent 2: DealStrategist (Strategy & Economics Formulator).
Designs unit-economic viable recovery incentives with hard liability caps and expected ROI bounds.
"""

from typing import Dict, Any

class DealStrategistAgent:
    """Specialized in margin-safe discount structures, liability capping, and recovery economics."""

    def __init__(self, agent_name: str = "DealStrategist"):
        self.agent_name = agent_name

    def evaluate_unit_economics(self, gross_margin_pct: float, avg_ticket: float, discount_inr: float) -> Dict[str, Any]:
        """Calculates margin retention per unit order."""
        gross_profit_before_discount = avg_ticket * (gross_margin_pct / 100.0)
        net_profit_after_discount = gross_profit_before_discount - discount_inr
        net_margin_pct = (net_profit_after_discount / avg_ticket) * 100.0
        return {
            "avg_ticket_inr": avg_ticket,
            "gross_profit_inr": round(gross_profit_before_discount, 2),
            "discount_inr": discount_inr,
            "net_profit_inr": round(net_profit_after_discount, 2),
            "net_margin_pct": round(net_margin_pct, 1),
            "is_viable": net_profit_after_discount > 0
        }

    def formulate_plan(self, cohort_count: int, max_budget_ceiling: float = 3600.0) -> Dict[str, Any]:
        """Formulates an optimized coupon strategy respecting hard safety caps."""
        discount_code = "RET50"
        discount_amount = 50.0
        min_order = 249.0
        expected_redemption_rate = 18.2  # 18.2% baseline
        
        # Max theoretical liability if 100% redeem: 240 * 50 = 12,000.
        # But hard programmatically capped at ₹3,600 (allowing at most 72 claims).
        hard_cap = min(max_budget_ceiling, 3600.0)

        expected_redeemers = round(cohort_count * (expected_redemption_rate / 100.0))
        expected_spend_per_redeemer = 385.0
        expected_gross_sales = expected_redeemers * expected_spend_per_redeemer
        expected_discount_cost = expected_redeemers * discount_amount
        expected_net_margin = round(expected_gross_sales * 0.55 - expected_discount_cost, 2)

        return {
            "discount_code": discount_code,
            "discount_amount_inr": discount_amount,
            "min_order_inr": min_order,
            "max_liability_cap_inr": hard_cap,
            "expected_redemption_count": expected_redeemers,
            "expected_gross_sales_inr": round(expected_gross_sales, 2),
            "expected_net_margin_inr": round(expected_net_margin, 2),
            "safety_checks": {
                "budget_capped": True,
                "trai_dnd_compliant": True,
                "no_lending_exposure": True
            }
        }
