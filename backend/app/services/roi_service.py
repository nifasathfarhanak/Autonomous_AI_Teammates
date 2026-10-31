"""ROI reporting based only on recorded, verified post-campaign transactions."""

from typing import Dict, Any
from ..database import get_connection

def simulate_and_verify_roi(
    workflow_id: str,
    redemption_count: int = 0,
    avg_ticket_inr: float = 0.0
) -> Dict[str, Any]:
    """Compatibility wrapper that never treats simulated dispatch as verified revenue."""
    summary = get_roi_summary(workflow_id)
    if not summary:
        return {}
    if summary.get("is_verified"):
        return summary
    return {
        "workflow_id": workflow_id,
        "target_recipients": summary.get("total_targeted"),
        "redemption_count": None,
        "gross_recovered_sales_inr": None,
        "total_discounts_paid_inr": None,
        "execution_cost_inr": summary.get("total_execution_cost_inr"),
        "net_recovered_profit_inr": None,
        "roi_multiple": None,
        "is_verified": False,
        "outcome_status": "AWAITING_REAL_POST_CAMPAIGN_TRANSACTIONS"
    }

def get_roi_summary(workflow_id: str) -> Dict[str, Any]:
    """Retrieves current ROI status from database."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM roi_metrics WHERE workflow_id = ?", (workflow_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {}
    return dict(row)
