"""Paytm AI ActionMate No-Regret Business Guardrails Engine (Phase 8 Innovation 6).
Enforces merchant-controlled business boundaries strictly in the backend.
Validates campaigns, discounts, budgets, margins, and inventory safety stock before execution.
"""

from typing import Dict, Any, List, Optional
from ..database import get_connection

class GuardrailViolationError(Exception):
    """Raised when an autonomous action breaches an active merchant business rule."""
    def __init__(self, rule_code: str, reason: str, alternative: str):
        super().__init__(f"GUARDRAIL_BLOCKED [{rule_code}]: {reason}")
        self.rule_code = rule_code
        self.reason = reason
        self.alternative = alternative

class GuardrailsService:
    """Manages and enforces merchant business boundaries."""

    @staticmethod
    def get_all_guardrails(merchant_id: str = "MERCH-001") -> List[Dict[str, Any]]:
        """Retrieves active merchant guardrails and configured parameter thresholds."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT rule_id, merchant_id, rule_code, rule_name, parameter_value, unit,
               description, enforcement_level, is_active
        FROM merchant_guardrails
        WHERE merchant_id = ?
        ORDER BY rule_id ASC
        """, (merchant_id,))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def update_guardrail(
        rule_code: str,
        new_value: float,
        is_active: Optional[bool] = None,
        merchant_id: str = "MERCH-001"
    ) -> Dict[str, Any]:
        """Updates a guardrail threshold or toggles its active status."""
        conn = get_connection()
        cur = conn.cursor()

        if is_active is not None:
            cur.execute("""
            UPDATE merchant_guardrails
            SET parameter_value = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE rule_code = ? AND merchant_id = ?
            """, (new_value, 1 if is_active else 0, rule_code, merchant_id))
        else:
            cur.execute("""
            UPDATE merchant_guardrails
            SET parameter_value = ?, updated_at = CURRENT_TIMESTAMP
            WHERE rule_code = ? AND merchant_id = ?
            """, (new_value, rule_code, merchant_id))

        conn.commit()
        conn.close()

        return {
            "status": "UPDATED",
            "rule_code": rule_code,
            "new_parameter_value": new_value,
            "merchant_id": merchant_id
        }

    @staticmethod
    def evaluate_campaign_guardrails(
        proposed_action: Dict[str, Any],
        merchant_id: str = "MERCH-001"
    ) -> Dict[str, Any]:
        """Validates all configured merchant guardrails against a proposed campaign or action.
        Returns passed: True/False, violations list, and suggested compliant alternatives.
        """
        guardrails = {g["rule_code"]: g for g in GuardrailsService.get_all_guardrails(merchant_id)}
        violations = []

        # 1. Check Max Discount %
        rule_max_disc = guardrails.get("MAX_DISCOUNT_PERCENT")
        if rule_max_disc and rule_max_disc["is_active"]:
            max_disc = float(rule_max_disc["parameter_value"])
            proposed_disc = float(proposed_action.get("discount_pct", 0.0))
            if proposed_disc > max_disc:
                violations.append({
                    "rule_code": "MAX_DISCOUNT_PERCENT",
                    "rule_name": rule_max_disc["rule_name"],
                    "threshold": max_disc,
                    "proposed_value": proposed_disc,
                    "reason": f"Proposed discount of {proposed_disc}% exceeds configured maximum limit of {max_disc}%.",
                    "suggested_alternative": f"Cap promotional discount at {max_disc}% or switch to a high-margin product bundle."
                })

        # 2. Check Max Campaign Budget
        rule_max_budget = guardrails.get("MAX_CAMPAIGN_BUDGET_INR")
        if rule_max_budget and rule_max_budget["is_active"]:
            max_budget = float(rule_max_budget["parameter_value"])
            proposed_budget = float(proposed_action.get("total_budget_inr", proposed_action.get("marketing_cost_inr", 0.0)))
            if proposed_budget > max_budget:
                violations.append({
                    "rule_code": "MAX_CAMPAIGN_BUDGET_INR",
                    "rule_name": rule_max_budget["rule_name"],
                    "threshold": max_budget,
                    "proposed_value": proposed_budget,
                    "reason": f"Proposed campaign budget of ₹{proposed_budget:,.2f} exceeds merchant ceiling of ₹{max_budget:,.2f}.",
                    "suggested_alternative": f"Limit audience size or reduce duration to keep total expenditure under ₹{max_budget:,.2f}."
                })

        # 3. Check Minimum Product Gross Margin Floor
        rule_min_margin = guardrails.get("MIN_GROSS_MARGIN_PERCENT")
        if rule_min_margin and rule_min_margin["is_active"]:
            min_margin = float(rule_min_margin["parameter_value"])
            post_disc_margin = float(proposed_action.get("estimated_margin_pct", 30.0))
            if post_disc_margin < min_margin:
                violations.append({
                    "rule_code": "MIN_GROSS_MARGIN_PERCENT",
                    "rule_name": rule_min_margin["rule_name"],
                    "threshold": min_margin,
                    "proposed_value": post_disc_margin,
                    "reason": f"Post-discount gross margin of {post_disc_margin}% falls below merchant floor of {min_margin}%.",
                    "suggested_alternative": f"Increase minimum order value requirement or select a SKU with baseline margin > {min_margin + 10}%."
                })

        # 4. Check Low Inventory Safety Stock
        rule_inv_safety = guardrails.get("INVENTORY_SAFETY_STOCK_DAYS")
        if rule_inv_safety and rule_inv_safety["is_active"]:
            min_days = float(rule_inv_safety["parameter_value"])
            sku_days = float(proposed_action.get("target_sku_days_on_hand", 15.0))
            if sku_days < min_days:
                violations.append({
                    "rule_code": "INVENTORY_SAFETY_STOCK_DAYS",
                    "rule_name": rule_inv_safety["rule_name"],
                    "threshold": min_days,
                    "proposed_value": sku_days,
                    "reason": f"Target product has only {sku_days} days of inventory on hand (below {min_days}-day safety threshold).",
                    "suggested_alternative": "Promote surplus inventory items with > 15 days of stock to prevent stockout."
                })

        # 5. Check Category C Financial Block
        action_type = proposed_action.get("action_type", "")
        if action_type in ("issue_refund", "modify_bank_account", "alter_settlement_payout"):
            violations.append({
                "rule_code": "FINANCIAL_ACTION_BLOCKED",
                "rule_name": "Prohibited Financial Mutation",
                "threshold": 0.0,
                "proposed_value": 1.0,
                "reason": f"Action '{action_type}' is classified as Category C (Financial Operation). Strictly blocked for autonomous agents.",
                "suggested_alternative": "Perform financial operations directly within the authenticated Paytm Merchant Portal."
            })

        passed = len(violations) == 0

        return {
            "passed": passed,
            "violations_count": len(violations),
            "violations": violations,
            "enforcement_action": "ALLOW" if passed else "BLOCK_EXECUTION",
            "merchant_id": merchant_id
        }

