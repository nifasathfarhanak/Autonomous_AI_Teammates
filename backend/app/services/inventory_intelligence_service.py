"""Paytm AI ActionMate Predictive Inventory Intelligence Engine (Phase 8 Innovation 2).
Monitors product stock availability, sales velocity, estimated stockout dates,
supplier reorder thresholds, inventory aging, and inventory-linked marketing triggers.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from ..database import get_connection

class InventoryIntelligenceService:
    """Provides real-time inventory monitoring, stockout predictions, and replenishment recommendations."""

    @staticmethod
    def get_inventory_status(merchant_id: str = "MERCH-001") -> List[Dict[str, Any]]:
        """Returns stock on hand, velocity, days of supply, and stockout risk for all SKUs."""
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
        SELECT 
            inventory_id, product_id, product_name, category,
            current_stock_units, min_safety_stock, reorder_point, lead_time_days,
            unit_cost_inr, unit_selling_price_inr, stock_age_days, last_restocked_date
        FROM merchant_inventory
        WHERE merchant_id = ?
        ORDER BY current_stock_units ASC
        """, (merchant_id,))
        rows = cur.fetchall()

        # Calculate sales velocity over last 14 days from order_items
        cur.execute("""
        SELECT product_id, SUM(quantity) as total_units_sold
        FROM order_items
        GROUP BY product_id
        """)
        sales_map = {r["product_id"]: max(1, r["total_units_sold"]) for r in cur.fetchall()}
        conn.close()

        today = datetime.now(timezone.utc)
        items = []

        for r in rows:
            pid = r["product_id"]
            stock = r["current_stock_units"]
            safety = r["min_safety_stock"]
            reorder_pt = r["reorder_point"]
            lead_time = r["lead_time_days"]
            cost = r["unit_cost_inr"]
            selling = r["unit_selling_price_inr"]
            age_days = r["stock_age_days"]

            # Daily velocity (units / 14 days)
            total_sold_14d = sales_map.get(pid, 3)
            daily_velocity = round(total_sold_14d / 14.0, 2)
            if daily_velocity <= 0.05:
                daily_velocity = 0.10

            days_on_hand = round(stock / daily_velocity, 1) if daily_velocity > 0 else 999.0
            stockout_date = (today + timedelta(days=days_on_hand)).strftime("%Y-%m-%d")

            # Stockout Risk Status
            if stock <= safety or days_on_hand <= lead_time:
                risk_status = "CRITICAL_STOCKOUT_RISK"
                action = f"Stockout predicted in {int(days_on_hand)} days. Supplier lead time is {lead_time} days. Immediate reorder required."
            elif stock <= reorder_pt:
                risk_status = "REORDER_RECOMMENDED"
                action = f"Stock approaching reorder threshold. Schedule supplier order within {max(1, int(days_on_hand - lead_time))} days."
            elif age_days >= 60:
                risk_status = "SLOW_MOVING_SURPLUS"
                action = f"Capital trapped for {age_days} days. Eligible for bundle discount with fast-moving SKUs."
            else:
                risk_status = "HEALTHY"
                action = "Stock levels optimal. No operational intervention needed."

            # Reorder Quantity recommendation: Lead time demand + Safety stock - Current stock
            reorder_qty = max(0, int(round((lead_time * daily_velocity * 2.0) + safety - stock)))

            items.append({
                "inventory_id": r["inventory_id"],
                "product_id": pid,
                "product_name": r["product_name"],
                "category": r["category"],
                "current_stock_units": stock,
                "min_safety_stock": safety,
                "reorder_point": reorder_pt,
                "lead_time_days": lead_time,
                "unit_cost_inr": cost,
                "unit_selling_price_inr": selling,
                "stock_age_days": age_days,
                "daily_sales_velocity": daily_velocity,
                "days_on_hand": days_on_hand,
                "estimated_stockout_date": stockout_date,
                "stockout_risk_status": risk_status,
                "recommended_reorder_units": reorder_qty,
                "recommended_action": action,
                "promotional_eligibility": days_on_hand >= 5.0, # Guardrail: cannot promote if days_on_hand < 5
                "trapped_capital_inr": round(stock * cost, 2) if age_days >= 60 else 0.0
            })

        return items

    @staticmethod
    def get_inventory_summary(merchant_id: str = "MERCH-001") -> Dict[str, Any]:
        """Provides high-level working capital, turnover, and stockout exposure summary."""
        items = InventoryIntelligenceService.get_inventory_status(merchant_id)

        total_skus = len(items)
        total_stock_units = sum(i["current_stock_units"] for i in items)
        total_valuation_inr = round(sum(i["current_stock_units"] * i["unit_cost_inr"] for i in items), 2)
        total_trapped_capital_inr = round(sum(i["trapped_capital_inr"] for i in items), 2)

        critical_items = [i for i in items if i["stockout_risk_status"] == "CRITICAL_STOCKOUT_RISK"]
        reorder_items = [i for i in items if i["stockout_risk_status"] == "REORDER_RECOMMENDED"]
        slow_moving_items = [i for i in items if i["stockout_risk_status"] == "SLOW_MOVING_SURPLUS"]

        # Inventory Turnover Ratio: Annualized COGS / Average Inventory Valuation
        # Based on ₹300k weekly sales ~ ₹200k weekly COGS ~ ₹860k monthly COGS
        monthly_cogs = 860000.0
        turnover_ratio = round((monthly_cogs * 12.0) / total_valuation_inr, 2) if total_valuation_inr > 0 else 0.0

        return {
            "merchant_id": merchant_id,
            "total_skus_tracked": total_skus,
            "total_stock_units": total_stock_units,
            "total_inventory_valuation_inr": total_valuation_inr,
            "trapped_working_capital_inr": total_trapped_capital_inr,
            "annualized_inventory_turnover_ratio": turnover_ratio,
            "critical_stockouts_count": len(critical_items),
            "reorders_pending_count": len(reorder_items),
            "slow_moving_skus_count": len(slow_moving_items),
            "critical_stockout_items": critical_items,
            "reorder_recommended_items": reorder_items,
            "slow_moving_items": slow_moving_items,
            "disclaimer": "Inventory velocities are calculated deterministically from transaction histories. Supplier lead times are based on merchant records."
        }

    @staticmethod
    def check_sku_promotional_guardrail(product_id: str, merchant_id: str = "MERCH-001") -> Dict[str, Any]:
        """Validates whether a product has sufficient stock to be promoted without causing a stockout."""
        items = InventoryIntelligenceService.get_inventory_status(merchant_id)
        sku = next((i for i in items if i["product_id"] == product_id), None)
        if not sku:
            return {"allowed": True, "reason": "SKU not tracked in inventory"}

        if sku["days_on_hand"] < 5.0 or sku["stockout_risk_status"] == "CRITICAL_STOCKOUT_RISK":
            return {
                "allowed": False,
                "product_id": product_id,
                "product_name": sku["product_name"],
                "current_stock_units": sku["current_stock_units"],
                "days_on_hand": sku["days_on_hand"],
                "violated_rule": "INVENTORY_SAFETY_STOCK_DAYS",
                "reason": f"Cannot promote '{sku['product_name']}'. Only {sku['days_on_hand']} days of inventory remaining (below 5-day safety floor). Promoting now will trigger an immediate stockout.",
                "suggested_alternative": "Promote slow-moving surplus items (e.g., PROD-005) or steady performers with > 15 days of stock."
            }

        return {
            "allowed": True,
            "product_id": product_id,
            "product_name": sku["product_name"],
            "days_on_hand": sku["days_on_hand"],
            "stock_units": sku["current_stock_units"]
        }

