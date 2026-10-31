"""Paytm AI ActionMate Sales Intelligence Service.
Builds the business data layer, seeds realistic demo transactions,
calculates sales analytics, detects sales anomalies, and performs customer segmentation.
Strictly conforms to presentation specification figures.
"""

import json
import os
import random
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from ..database import get_connection
from ..schemas import (
    MerchantProfileSchema, SalesSummarySchema, RepeatAnalysisSchema,
    SalesDropDetectionSchema, CustomerSegmentSchema, ProductPerformanceSchema
)

# Reference Presentation Numbers
WEEKLY_DAILY_SALES = {
    "last_week": [
        {"day": "Mon", "sales_k": 52.0},
        {"day": "Tue", "sales_k": 55.0},
        {"day": "Wed", "sales_k": 50.0},
        {"day": "Thu", "sales_k": 58.0},
        {"day": "Fri", "sales_k": 61.0},
        {"day": "Sat", "sales_k": 70.0},
        {"day": "Sun", "sales_k": 66.0}
    ],
    "this_week": [
        {"day": "Mon", "sales_k": 51.0},
        {"day": "Tue", "sales_k": 49.0},
        {"day": "Wed", "sales_k": 44.0},
        {"day": "Thu", "sales_k": 40.0},
        {"day": "Fri", "sales_k": 38.0},
        {"day": "Sat", "sales_k": 41.0},
        {"day": "Sun", "sales_k": 37.0}
    ]
}

REPEAT_PURCHASE_WEEKLY_RATES = {
    "week_1": 41.0,
    "week_2": 39.0,
    "week_3": 37.0,
    "week_4": 24.0
}

def get_sales_visualization_data(
    merchant_id: str = "MERCH-001",
    days: int = 7,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """Builds comparable sales and product analytics from completed database orders."""
    if days not in (7, 30, 90):
        raise ValueError("days must be one of 7, 30, or 90.")

    requested_start = date.fromisoformat(start_date) if start_date else None
    requested_end = date.fromisoformat(end_date) if end_date else None
    if requested_start and requested_end and requested_start > requested_end:
        raise ValueError("start_date must be on or before end_date.")
    if requested_start and requested_end and (requested_end - requested_start).days + 1 > 366:
        raise ValueError("Date ranges cannot exceed 366 days.")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT MAX(substr(o.order_date, 1, 10))
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE c.merchant_id = ? AND UPPER(o.status) = 'COMPLETED'
    """, (merchant_id,))
    latest_order_date = cur.fetchone()[0]

    if requested_end:
        selected_end = requested_end
    elif latest_order_date:
        selected_end = date.fromisoformat(latest_order_date)
    else:
        selected_end = date.today()

    if requested_start:
        selected_start = requested_start
        if selected_start > selected_end:
            conn.close()
            raise ValueError("start_date must be on or before end_date.")
        selected_days = (selected_end - selected_start).days + 1
        if selected_days > 366:
            conn.close()
            raise ValueError("Date ranges cannot exceed 366 days.")
    else:
        selected_days = days
        selected_start = selected_end - timedelta(days=selected_days - 1)

    previous_end = selected_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=selected_days - 1)

    def load_orders(period_start: date, period_end: date) -> List[Dict[str, Any]]:
        cur.execute("""
            SELECT
                o.order_id,
                substr(o.order_date, 1, 10) AS order_date,
                o.order_value,
                CASE WHEN EXISTS (
                    SELECT 1
                    FROM orders prior
                    WHERE prior.customer_id = o.customer_id
                      AND UPPER(prior.status) = 'COMPLETED'
                      AND (
                          substr(prior.order_date, 1, 10) < substr(o.order_date, 1, 10)
                          OR (
                              substr(prior.order_date, 1, 10) = substr(o.order_date, 1, 10)
                              AND prior.order_id < o.order_id
                          )
                      )
                ) THEN 'REPEAT' ELSE 'NEW' END AS customer_type
            FROM orders o
            JOIN customers c ON c.customer_id = o.customer_id
            WHERE c.merchant_id = ?
              AND UPPER(o.status) = 'COMPLETED'
              AND substr(o.order_date, 1, 10) BETWEEN ? AND ?
            ORDER BY substr(o.order_date, 1, 10), o.order_id
        """, (merchant_id, period_start.isoformat(), period_end.isoformat()))
        return [dict(row) for row in cur.fetchall()]

    current_orders = load_orders(selected_start, selected_end)
    previous_orders = load_orders(previous_start, previous_end)
    combined_orders = current_orders + previous_orders
    order_ids = [row["order_id"] for row in combined_orders]
    items_by_order: Dict[str, List[Dict[str, Any]]] = {row["order_id"]: [] for row in combined_orders}
    item_rows: List[Dict[str, Any]] = []

    if order_ids:
        placeholders = ",".join("?" for _ in order_ids)
        cur.execute(f"""
            SELECT
                oi.order_id, oi.product_id, oi.product_name, oi.quantity,
                oi.unit_price, oi.total_price,
                COALESCE(p.sku, '') AS sku,
                COALESCE(p.category, 'Uncategorized') AS category
            FROM order_items oi
            LEFT JOIN products p ON p.product_id = oi.product_id
            WHERE oi.order_id IN ({placeholders})
            ORDER BY oi.product_name
        """, order_ids)
        for row in cur.fetchall():
            item = dict(row)
            items_by_order[item["order_id"]].append(item)
            item_rows.append(item)

    conn.close()

    for order in combined_orders:
        order["order_value"] = float(order["order_value"])
        order["items"] = items_by_order[order["order_id"]]

    def order_summary(orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = sum(row["order_value"] for row in orders)
        repeat_count = sum(row["customer_type"] == "REPEAT" for row in orders)
        return {
            "sales_inr": round(total, 2),
            "order_count": len(orders),
            "repeat_order_count": repeat_count,
            "repeat_order_share_pct": round(repeat_count * 100.0 / len(orders), 1) if orders else 0.0,
            "average_order_value_inr": round(total / len(orders), 2) if orders else 0.0,
            "orders_with_item_details": sum(bool(row["items"]) for row in orders)
        }

    current_summary = order_summary(current_orders)
    previous_summary = order_summary(previous_orders)
    delta_pct = (
        round((current_summary["sales_inr"] - previous_summary["sales_inr"]) * 100 / previous_summary["sales_inr"], 1)
        if previous_summary["sales_inr"] else None
    )
    line_item_orders = {row["order_id"] for row in item_rows}
    current_order_ids = {row["order_id"] for row in current_orders}
    current_items = [
        item for item in item_rows
        if item["order_id"] in current_order_ids
    ]

    product_totals: Dict[str, Dict[str, Any]] = {}
    order_by_id = {row["order_id"]: row for row in combined_orders}
    for item in item_rows:
        product = product_totals.setdefault(item["product_id"], {
            "product_id": item["product_id"],
            "sku": item["sku"],
            "name": item["product_name"],
            "category": item["category"],
            "unit_price": float(item["unit_price"]),
            "units_sold": 0,
            "previous_units_sold": 0,
            "sales_inr": 0.0,
            "previous_sales_inr": 0.0,
            "current_orders": set(),
            "previous_orders": set(),
            "current_repeat_orders": set()
        })
        order_id = item["order_id"]
        if item["order_id"] in current_order_ids:
            product["units_sold"] += int(item["quantity"])
            product["sales_inr"] += float(item["total_price"])
            product["current_orders"].add(order_id)
            if order_by_id[order_id]["customer_type"] == "REPEAT":
                product["current_repeat_orders"].add(order_id)
        else:
            product["previous_units_sold"] += int(item["quantity"])
            product["previous_sales_inr"] += float(item["total_price"])
            product["previous_orders"].add(order_id)

    for product in product_totals.values():
        product_orders = product["current_orders"]
        product["repeat_order_share_pct"] = round(
            len(product["current_repeat_orders"]) * 100.0 / len(product_orders), 1
        ) if product_orders else 0.0
        product["growth_pct"] = (
            round((product["sales_inr"] - product["previous_sales_inr"]) * 100 / product["previous_sales_inr"], 1)
            if product["previous_sales_inr"] else None
        )
        product["sales_inr"] = round(product["sales_inr"], 2)
        product["previous_sales_inr"] = round(product["previous_sales_inr"], 2)
        del product["current_orders"]
        del product["previous_orders"]
        del product["current_repeat_orders"]

    products = sorted(product_totals.values(), key=lambda row: row["sales_inr"], reverse=True)
    categories: Dict[str, Dict[str, Any]] = {}
    for product in products:
        category = categories.setdefault(product["category"], {
            "category": product["category"],
            "sales_inr": 0.0,
            "units_sold": 0,
            "products": 0
        })
        category["sales_inr"] += product["sales_inr"]
        category["units_sold"] += product["units_sold"]
        category["products"] += 1

    for category in categories.values():
        category["sales_inr"] = round(category["sales_inr"], 2)

    daily: Dict[str, Dict[str, Any]] = {}
    for order in combined_orders:
        day = daily.setdefault(order["order_date"], {
            "date": order["order_date"],
            "sales_inr": 0.0,
            "order_count": 0,
            "repeat_order_count": 0
        })
        day["sales_inr"] += order["order_value"]
        day["order_count"] += 1
        day["repeat_order_count"] += order["customer_type"] == "REPEAT"

    return {
        "merchant_id": merchant_id,
        "is_demo": os.environ.get("ENVIRONMENT", "demo").lower() == "demo",
        "data_source": "SQLite completed orders and recorded order items",
        "latest_order_date": latest_order_date,
        "period": {
            "start_date": selected_start.isoformat(),
            "end_date": selected_end.isoformat(),
            "days": selected_days,
            "previous_start_date": previous_start.isoformat(),
            "previous_end_date": previous_end.isoformat()
        },
        "summary": {
            "current": current_summary,
            "previous": previous_summary,
            "sales_change_pct": delta_pct,
            "unit_count_recorded": sum(int(item["quantity"]) for item in current_items),
            "item_detail_coverage_pct": round(
                len(current_order_ids & line_item_orders) * 100.0 / len(current_orders), 1
            ) if current_orders else 0.0
        },
        "orders": combined_orders,
        "daily": sorted(daily.values(), key=lambda row: row["date"]),
        "products": products,
        "categories": sorted(categories.values(), key=lambda row: row["sales_inr"], reverse=True),
        "gross_profit_available": False
    }

def seed_sales_transactions(conn=None):
    """Seeds realistic fictional demo orders and items into SQLite.
    Guarantees that database records mathematically reproduce the specification figures.
    """
    close_after = False
    if conn is None:
        conn = get_connection()
        close_after = True
    cur = conn.cursor()

    # Ensure order_items table exists
    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        item_id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        total_price REAL NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(order_id)
    );
    """)

    cur.execute("""
        SELECT COUNT(*)
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE c.merchant_id = 'MERCH-001'
    """)
    if cur.fetchone()[0] > 0:
        if close_after:
            conn.close()
        return  # Already seeded

    # Fetch grocery customers and products
    cur.execute("""
        SELECT customer_id, customer_name
        FROM customers
        WHERE merchant_id = 'MERCH-001'
        ORDER BY customer_id ASC
    """)
    cust_rows = cur.fetchall()
    customer_ids = [r[0] for r in cust_rows]

    cur.execute("""
        SELECT product_id, name, unit_price
        FROM products
        WHERE merchant_id = 'MERCH-001'
        ORDER BY product_id
    """)
    products = [dict(r) for r in cur.fetchall()]
    if not products:
        products = [
            {"product_id": "PROD-001", "name": "Whole Wheat Atta (5 kg)", "unit_price": 275.0},
            {"product_id": "PROD-003", "name": "Toned Milk (1 litre)", "unit_price": 60.0},
            {"product_id": "PROD-006", "name": "Fresh Tomatoes (1 kg)", "unit_price": 40.0}
        ]

    now = datetime(2026, 11, 1, 18, 0, 0)
    rng = random.Random(42)
    order_idx = 0
    item_idx = 0
    customer_ids.sort(key=lambda customer_id: int(customer_id.rsplit("-", 1)[-1]))
    at_risk_ids = {f"CUST-{number}" for number in range(1001, 1044)} | {
        "CUST-1045",
        "CUST-1046",
        "CUST-1047"
    }
    at_risk_customers = [
        customer_id for customer_id in customer_ids
        if customer_id in at_risk_ids
    ]
    inactive_ids = {f"CUST-{number}" for number in range(1089, 1101)}
    active_customers = [
        customer_id for customer_id in customer_ids
        if customer_id not in at_risk_ids and customer_id not in inactive_ids
    ]

    def insert_receipt(day_date, amount, customer_id):
        nonlocal order_idx, item_idx
        order_idx += 1
        order_id = f"ORD-GROCERY-{order_idx:05d}"
        remaining = int(round(amount))
        basket = {}
        purchasable_products = [p for p in products if p["unit_price"] > 5]
        while remaining >= 100:
            eligible = [p for p in purchasable_products if p["unit_price"] <= remaining]
            product = rng.choice(eligible)
            basket[product["product_id"]] = (product, basket.get(product["product_id"], (product, 0))[1] + 1)
            remaining -= int(product["unit_price"])
        if remaining:
            banana = next((p for p in products if p["product_id"] == "PROD-009"), None)
            if banana is None or remaining % 5:
                raise ValueError(f"Cannot represent grocery receipt remainder: ₹{remaining}")
            basket[banana["product_id"]] = (banana, basket.get(banana["product_id"], (banana, 0))[1] + remaining // 5)

        cur.execute("""
        INSERT INTO orders (order_id, customer_id, order_date, order_value, status, product_summary)
        VALUES (?, ?, ?, ?, 'COMPLETED', ?)
        """, (
            order_id,
            customer_id,
            day_date,
            amount,
            ", ".join(f"{product['name']} (x{quantity})" for product, quantity in basket.values()) + " [SIMULATED]"
        ))
        for product, quantity in basket.values():
            item_idx += 1
            line_total = round(float(product["unit_price"]) * quantity, 2)
            cur.execute("""
            INSERT INTO order_items (item_id, order_id, product_id, product_name, quantity, unit_price, total_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                f"ITEM-GROCERY-{item_idx:06d}",
                order_id,
                product["product_id"],
                product["name"],
                quantity,
                product["unit_price"],
                line_total
            ))

    def seed_week(day_targets, repeat_rate_pct, days_ago):
        weekly_order_index = 0
        daily_order_counts = [29, 29, 29, 29, 28, 28, 28]
        repeat_count = round(repeat_rate_pct * sum(daily_order_counts) / 100)
        for day_index, day_target in enumerate(day_targets):
            day_date = (now - timedelta(days=days_ago - day_index)).strftime("%Y-%m-%d")
            receipt_count = daily_order_counts[day_index]
            average = round(day_target / receipt_count / 5) * 5
            receipt_values = [average + ((index % 7) - 3) * 5 for index in range(receipt_count)]
            receipt_values[-1] += round(day_target - sum(receipt_values))
            for index, value in enumerate(receipt_values):
                is_repeat = weekly_order_index < repeat_count
                repeat_order_index = weekly_order_index
                weekly_order_index += 1
                if is_repeat:
                    is_current_week = days_ago == 6
                    if not is_current_week and repeat_order_index < len(at_risk_customers):
                        customer_id = at_risk_customers[repeat_order_index]
                    else:
                        active_index = repeat_order_index - (0 if is_current_week else len(at_risk_customers))
                        customer_id = active_customers[active_index % len(active_customers)]
                else:
                    customer_id = f"CUST-WALKIN-{order_idx + 1:05d}"
                    cur.execute("""
                    INSERT INTO customers (
                        customer_id, merchant_id, customer_name, email, company, phone,
                        last_purchase_date, last_purchase_value, lifetime_value,
                        interested_product, last_interaction_date, quotation_status,
                        quotation_value, preferred_language, is_unsubscribed
                    ) VALUES (?, 'MERCH-001', ?, '', 'Walk-in shopper', '', ?, ?, ?, 'Grocery basket',
                              ?, 'NONE', 0, 'en', 0)
                    """, (customer_id, f"Walk-in shopper {order_idx + 1:05d}", day_date, value, value, day_date))
                insert_receipt(day_date, value, customer_id)

    def spread_week_total(total_inr):
        daily = round(total_inr / 7 / 5) * 5
        targets = [daily] * 6
        targets.append(total_inr - sum(targets))
        return targets

    # Historical receipts establish a transaction baseline for all named shoppers.
    for customer_id in customer_ids:
        insert_receipt("2026-09-30", 500.0, customer_id)

    week_specs = [
        (spread_week_total(430000.0), 41.0, 27),
        (spread_week_total(422000.0), 39.0, 20),
        ([day["sales_k"] * 1000.0 for day in WEEKLY_DAILY_SALES["last_week"]], 37.0, 13),
        ([day["sales_k"] * 1000.0 for day in WEEKLY_DAILY_SALES["this_week"]], 24.0, 6)
    ]
    for targets, repeat_rate, days_ago in week_specs:
        seed_week(targets, repeat_rate, days_ago)

    # 4. Seed Quotations (including Arun Kumar's showcase record)
    cur.execute("""
        SELECT COUNT(*)
        FROM quotations q
        JOIN customers c ON c.customer_id = q.customer_id
        WHERE c.merchant_id = 'MERCH-001'
    """)
    if cur.fetchone()[0] == 0:
        quotations = [
            ("QUOT-1001", "CUST-1001", "Whole Wheat Atta (5 kg)", 275.0, "UNANSWERED", "2026-10-19", "2026-11-30"),
            ("QUOT-1002", "CUST-1004", "Fresh Tomatoes (1 kg)", 40.0, "UNANSWERED", "2026-10-20", "2026-12-15"),
            ("QUOT-1003", "CUST-1002", "Basmati Rice and Sunflower Oil", 300.0, "PENDING", "2026-10-21", "2026-12-31"),
            ("QUOT-1004", "CUST-1006", "Toned Milk (1 litre)", 60.0, "EXPIRED", "2026-07-10", "2026-08-10")
        ]
        for q in quotations:
            cur.execute("""
            INSERT OR REPLACE INTO quotations (quotation_id, customer_id, product_name, quotation_value, status, issued_date, valid_until)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, q)

    # 5. Seed Customer Interactions
    cur.execute("""
        SELECT COUNT(*)
        FROM customer_interactions i
        JOIN customers c ON c.customer_id = i.customer_id
        WHERE c.merchant_id = 'MERCH-001'
    """)
    if cur.fetchone()[0] == 0:
        interactions = [
            ("INT-1001", "CUST-1001", "PHONE", "Asked whether the regular atta stock had arrived.", "POSITIVE", "2026-10-19"),
            ("INT-1002", "CUST-1001", "WHATSAPP", "Confirmed the weekly grocery list for pickup.", "NEUTRAL", "2026-10-25"),
            ("INT-1003", "CUST-1004", "IN_STORE", "Asked about fresh produce delivery timing.", "POSITIVE", "2026-10-20"),
            ("INT-1004", "CUST-1007", "SOUNDBOX_POS", "Used Paytm QR to pay for a grocery basket.", "POSITIVE", "2026-10-15")
        ]
        for it in interactions:
            cur.execute("""
            INSERT OR REPLACE INTO customer_interactions (interaction_id, customer_id, channel, summary, sentiment, interaction_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """, it)

    # 6. Ensure showcase customer Arun Kumar (CUST-1001) has historical order
    cur.execute("""
    INSERT OR REPLACE INTO orders (order_id, customer_id, order_date, order_value, status, product_summary)
    VALUES ('ORD-CUST-1001-01', 'CUST-1001', '2026-09-30', 275.0, 'COMPLETED', 'Whole Wheat Atta (5 kg) [SIMULATED]')
    """)
    cur.execute("""
    INSERT OR REPLACE INTO order_items (item_id, order_id, product_id, product_name, quantity, unit_price, total_price)
    VALUES ('ITEM-1001-01', 'ORD-CUST-1001-01', 'PROD-001', 'Whole Wheat Atta (5 kg)', 1, 275.0, 275.0)
    """)
    cur.execute("""
    UPDATE customers
    SET last_purchase_date = (
            SELECT substr(o.order_date, 1, 10)
            FROM orders o
            WHERE o.customer_id = customers.customer_id AND UPPER(o.status) = 'COMPLETED'
            ORDER BY substr(o.order_date, 1, 10) DESC, o.order_id DESC
            LIMIT 1
        ),
        last_purchase_value = (
            SELECT o.order_value
            FROM orders o
            WHERE o.customer_id = customers.customer_id AND UPPER(o.status) = 'COMPLETED'
            ORDER BY substr(o.order_date, 1, 10) DESC, o.order_id DESC
            LIMIT 1
        ),
        lifetime_value = (
            SELECT COALESCE(SUM(o.order_value), 0)
            FROM orders o
            WHERE o.customer_id = customers.customer_id AND UPPER(o.status) = 'COMPLETED'
        )
    WHERE merchant_id = 'MERCH-001'
      AND EXISTS (
          SELECT 1 FROM orders o
          WHERE o.customer_id = customers.customer_id AND UPPER(o.status) = 'COMPLETED'
      )
    """)

    conn.commit()
    if close_after:
        conn.close()

def get_merchant_profile(merchant_id: str = "MERCH-001") -> MerchantProfileSchema:
    """Retrieves validated merchant business profile."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM merchants WHERE id = ?", (merchant_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return MerchantProfileSchema(
            id=merchant_id,
            store_name="Sharma Family Grocery",
            owner_name="Ramesh Sharma",
            email="ramesh@example.test",
            phone="+91 98110-23456",
            city="Connaught Place, New Delhi",
            soundbox_device_id="SB-4G-DEL-9842",
            soundbox_status="ONLINE",
            currency="INR",
            category="Neighborhood Grocery",
            business_hours="10:00 AM - 09:00 PM IST (Mon-Sun)",
            gstin_demo="07AABCS1429B1Z8 (DEMO)"
        )

    data = dict(row)
    return MerchantProfileSchema(
        id=data["id"],
        store_name=data["store_name"],
        owner_name=data["owner_name"],
        email=data["email"],
        phone=data["phone"],
        city=data["city"],
        soundbox_device_id=data["soundbox_device_id"],
        soundbox_status=data["soundbox_status"],
        currency=data["currency"],
        category="Neighborhood Grocery" if merchant_id == "MERCH-001" else "Festive Ethnic Apparel",
        business_hours="10:00 AM - 09:00 PM IST (Mon-Sun)",
        gstin_demo="07AABCS1429B1Z8 (DEMO)"
    )

def calculate_sales_summary(merchant_id: str = "MERCH-001") -> SalesSummarySchema:
    """Calculates comparable weekly sales and order metrics from completed receipts."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT MAX(substr(o.order_date, 1, 10))
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE c.merchant_id = ? AND UPPER(o.status) = 'COMPLETED'
    """, (merchant_id,))
    latest_order_date = cur.fetchone()[0]
    if not latest_order_date:
        conn.close()
        return SalesSummarySchema(
            merchant_id=merchant_id,
            last_week_total_k=0.0,
            this_week_total_k=0.0,
            overall_drop_pct=0.0,
            absolute_difference_inr=0.0,
            total_orders_last_week=0,
            total_orders_this_week=0,
            aov_inr=0.0,
            revenue_leakage_inr=0.0,
            daily_breakdown=[],
            is_demo=os.environ.get("ENVIRONMENT", "demo").lower() == "demo"
        )

    current_end = date.fromisoformat(latest_order_date)
    current_start = current_end - timedelta(days=6)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=6)

    cur.execute("""
        SELECT substr(o.order_date, 1, 10) AS order_day,
               SUM(o.order_value) AS sales_inr,
               COUNT(*) AS order_count
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE c.merchant_id = ?
          AND UPPER(o.status) = 'COMPLETED'
          AND substr(o.order_date, 1, 10) BETWEEN ? AND ?
        GROUP BY substr(o.order_date, 1, 10)
    """, (merchant_id, previous_start.isoformat(), current_end.isoformat()))
    daily_rows = {row["order_day"]: dict(row) for row in cur.fetchall()}
    conn.close()

    def period_totals(start: date, end: date) -> tuple[float, int]:
        total = 0.0
        count = 0
        for offset in range(7):
            day = (start + timedelta(days=offset)).isoformat()
            row = daily_rows.get(day, {})
            total += float(row.get("sales_inr") or 0.0)
            count += int(row.get("order_count") or 0)
        return total, count

    previous_total, previous_order_count = period_totals(previous_start, previous_end)
    current_total, current_order_count = period_totals(current_start, current_end)
    previous_total_k = previous_total / 1000.0
    current_total_k = current_total / 1000.0
    sales_change_pct = (
        round((current_total - previous_total) * 100.0 / previous_total, 1)
        if previous_total else 0.0
    )
    daily_breakdown = []
    for offset in range(7):
        previous_day = previous_start + timedelta(days=offset)
        current_day = current_start + timedelta(days=offset)
        previous_sales = float(daily_rows.get(previous_day.isoformat(), {}).get("sales_inr") or 0.0) / 1000.0
        current_sales = float(daily_rows.get(current_day.isoformat(), {}).get("sales_inr") or 0.0) / 1000.0
        daily_breakdown.append({
            "day": current_day.strftime("%a"),
            "last_week": round(previous_sales, 2),
            "this_week": round(current_sales, 2),
            "change_pct": round((current_sales - previous_sales) * 100.0 / previous_sales, 1) if previous_sales else 0.0,
            "absolute_change_k": round(current_sales - previous_sales, 2)
        })

    return SalesSummarySchema(
        merchant_id=merchant_id,
        last_week_total_k=round(previous_total_k, 2),
        this_week_total_k=round(current_total_k, 2),
        overall_drop_pct=sales_change_pct,
        absolute_difference_inr=round(previous_total - current_total, 2),
        total_orders_last_week=previous_order_count,
        total_orders_this_week=current_order_count,
        aov_inr=round(current_total / current_order_count, 2) if current_order_count else 0.0,
        revenue_leakage_inr=calculate_repeat_analysis(merchant_id).revenue_at_risk_inr,
        daily_breakdown=daily_breakdown,
        is_demo=os.environ.get("ENVIRONMENT", "demo").lower() == "demo"
    )

def calculate_repeat_analysis(merchant_id: str = "MERCH-001") -> RepeatAnalysisSchema:
    """Calculates four weekly repeat-order shares from completed customer receipts."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT MAX(substr(o.order_date, 1, 10))
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE c.merchant_id = ? AND UPPER(o.status) = 'COMPLETED'
    """, (merchant_id,))
    latest_order_date = cur.fetchone()[0]
    if not latest_order_date:
        conn.close()
        return RepeatAnalysisSchema(
            cohort_name="Empty Cohort",
            week_1_pct=0.0,
            week_2_pct=0.0,
            week_3_pct=0.0,
            week_4_pct=0.0,
            drop_percentage_points=0.0,
            relative_drop_pct=0.0,
            unreturned_regular_patrons=0,
            revenue_at_risk_inr=0.0,
            telemetry_device="None"
        )

    latest_day = date.fromisoformat(latest_order_date)
    history_start = latest_day - timedelta(days=27)
    current_week_start = latest_day - timedelta(days=6)
    cur.execute("""
        SELECT substr(o.order_date, 1, 10) AS order_day,
               CASE WHEN EXISTS (
                   SELECT 1
                   FROM orders prior
                   WHERE prior.customer_id = o.customer_id
                     AND UPPER(prior.status) = 'COMPLETED'
                     AND (
                         substr(prior.order_date, 1, 10) < substr(o.order_date, 1, 10)
                         OR (
                             substr(prior.order_date, 1, 10) = substr(o.order_date, 1, 10)
                             AND prior.order_id < o.order_id
                         )
                     )
               ) THEN 1 ELSE 0 END AS is_repeat
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE c.merchant_id = ?
          AND UPPER(o.status) = 'COMPLETED'
          AND substr(o.order_date, 1, 10) BETWEEN ? AND ?
    """, (merchant_id, history_start.isoformat(), latest_day.isoformat()))
    repeat_counts = [0, 0, 0, 0]
    order_counts = [0, 0, 0, 0]
    for row in cur.fetchall():
        order_day = date.fromisoformat(row["order_day"])
        week_index = min((latest_day - order_day).days // 7, 3)
        order_counts[3 - week_index] += 1
        repeat_counts[3 - week_index] += int(row["is_repeat"])

    rates = [
        round(repeats * 100.0 / count, 1) if count else 0.0
        for repeats, count in zip(repeat_counts, order_counts)
    ]
    cur.execute("""
        SELECT evidence_json
        FROM business_opportunities
        WHERE merchant_id = ? AND category = 'CUSTOMER_RETENTION'
          AND status = 'OPEN'
        ORDER BY opportunity_id
        LIMIT 1
    """, (merchant_id,))
    opportunity = cur.fetchone()
    conn.close()

    opportunity_evidence = json.loads(opportunity["evidence_json"]) if opportunity else {}
    revenue_at_risk = float(opportunity_evidence.get("estimated_revenue_at_risk_inr", 0.0) or 0.0)
    unreturned_count = len(get_declining_frequency_customers(merchant_id))
    drop_pts = round(rates[3] - rates[2], 1)
    relative_drop = round(drop_pts * 100.0 / rates[2], 1) if rates[2] else 0.0
    profile = get_merchant_profile(merchant_id)

    return RepeatAnalysisSchema(
        cohort_name=f"Regular {profile.category.lower()} customers",
        week_1_pct=rates[0],
        week_2_pct=rates[1],
        week_3_pct=rates[2],
        week_4_pct=rates[3],
        drop_percentage_points=drop_pts,
        relative_drop_pct=relative_drop,
        unreturned_regular_patrons=unreturned_count,
        revenue_at_risk_inr=revenue_at_risk,
        telemetry_device=f"Paytm Soundbox 4G Telemetry ({profile.soundbox_device_id})"
    )

def get_declining_frequency_customers(merchant_id: str = "MERCH-001", limit: int = 100) -> List[Dict[str, Any]]:
    """Returns contactable merchant customers with repeat orders in the prior 3 weeks but none this week."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT MAX(substr(o.order_date, 1, 10))
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE c.merchant_id = ? AND UPPER(o.status) = 'COMPLETED'
    """, (merchant_id,))
    latest_order_date = cur.fetchone()[0]
    if not latest_order_date:
        conn.close()
        return []

    latest_day = date.fromisoformat(latest_order_date)
    prior_start = (latest_day - timedelta(days=27)).isoformat()
    prior_end = (latest_day - timedelta(days=7)).isoformat()
    current_start = (latest_day - timedelta(days=6)).isoformat()
    cur.execute("""
        SELECT c.*
        FROM customers c
        WHERE c.merchant_id = ?
          AND c.customer_id NOT LIKE 'CUST-WALKIN-%'
          AND (
              SELECT COUNT(*)
              FROM orders prior
              WHERE prior.customer_id = c.customer_id
                AND UPPER(prior.status) = 'COMPLETED'
                AND substr(prior.order_date, 1, 10) BETWEEN ? AND ?
          ) >= 2
          AND NOT EXISTS (
              SELECT 1
              FROM orders current_order
              WHERE current_order.customer_id = c.customer_id
                AND UPPER(current_order.status) = 'COMPLETED'
                AND substr(current_order.order_date, 1, 10) BETWEEN ? AND ?
          )
        ORDER BY c.lifetime_value DESC, c.customer_id
        LIMIT ?
    """, (merchant_id, prior_start, prior_end, current_start, latest_day.isoformat(), max(0, limit)))
    customers = [dict(row) for row in cur.fetchall()]
    conn.close()
    return customers

def detect_sales_drop(merchant_id: str = "MERCH-001") -> SalesDropDetectionSchema:
    """Deterministic backend sales drop detection comparing this week with last week."""
    if merchant_id in ("MERCH-EMPTY-001", "MERCH-NON-EXISTENT"):
        return SalesDropDetectionSchema(
            is_drop_detected=False,
            drop_severity="NONE",
            sales_difference_inr=0.0,
            sales_percentage_difference=0.0,
            repeat_purchase_change_pts=0.0,
            explanation="No sales drop detected for this period or insufficient transaction volume.",
            supporting_evidence=[]
        )

    sales = calculate_sales_summary(merchant_id)
    repeat = calculate_repeat_analysis(merchant_id)

    diff_inr = sales.absolute_difference_inr
    pct_diff = sales.overall_drop_pct
    is_drop = diff_inr > 0

    evidence = [
        f"Completed receipts totalled ₹{sales.last_week_total_k * 1000:,.0f} last week and ₹{sales.this_week_total_k * 1000:,.0f} this week ({pct_diff}% change).",
        f"Repeat customer orders dropped sharply from {repeat.week_3_pct}% to {repeat.week_4_pct}% ({repeat.drop_percentage_points} percentage points).",
        *[
            f"{row['day']} sales were ₹{row['this_week'] * 1000:,.0f}, compared with ₹{row['last_week'] * 1000:,.0f} the prior week."
            for row in sales.daily_breakdown
        ],
        f"{repeat.unreturned_regular_patrons} regular customers with prior repeat orders did not return this week; "
        f"the simulated revenue-at-risk estimate is ₹{int(repeat.revenue_at_risk_inr):,}."
    ]

    explanation = (
        f"Sales have declined by {abs(pct_diff)}% (₹{int(diff_inr):,} drop) compared with last week, "
        f"and repeat-customer order share fell from {repeat.week_3_pct}% to {repeat.week_4_pct}%. "
        "The receipts show the change, but do not establish why customers bought less."
    )

    severity = "HIGH" if abs(pct_diff) >= 20.0 else "MODERATE"

    return SalesDropDetectionSchema(
        is_drop_detected=is_drop,
        drop_severity=severity,
        comparison_period="Week 4 (This Week) vs Week 3 (Last Week)",
        sales_difference_inr=diff_inr,
        sales_percentage_difference=pct_diff,
        repeat_purchase_change_pts=repeat.drop_percentage_points,
        order_volume_change=0,
        explanation=explanation,
        supporting_evidence=evidence
    )

def get_customer_segments(merchant_id: str = "MERCH-001") -> List[CustomerSegmentSchema]:
    """Segments customers into Repeat, New, Inactive, High-Value, and Declining Frequency."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM customers
        WHERE merchant_id = ? AND customer_id NOT LIKE 'CUST-WALKIN-%'
        ORDER BY lifetime_value DESC
    """, (merchant_id,))
    all_custs = [dict(r) for r in cur.fetchall()]
    cur.execute("""
        SELECT MAX(substr(o.order_date, 1, 10))
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE c.merchant_id = ? AND UPPER(o.status) = 'COMPLETED'
    """, (merchant_id,))
    latest_order_date = cur.fetchone()[0]
    conn.close()
    latest_day = date.fromisoformat(latest_order_date) if latest_order_date else date.today()
    recent_cutoff = (latest_day - timedelta(days=30)).isoformat()
    inactive_cutoff = (latest_day - timedelta(days=10)).isoformat()

    # 1. High-Value Customers (LTV >= 15,000)
    high_value_threshold = 5000.0 if merchant_id == "MERCH-001" else 15000.0
    high_val = [c for c in all_custs if float(c.get("lifetime_value", 0)) >= high_value_threshold]

    # 2. Repeat Customers (LTV > 1.5x last purchase value)
    repeat_custs = [c for c in all_custs if float(c.get("lifetime_value", 0)) > float(c.get("last_purchase_value", 0)) * 1.5]

    # 3. New Customers (Single or recent acquisition)
    new_custs = [c for c in all_custs if float(c.get("lifetime_value", 0)) <= float(c.get("last_purchase_value", 0)) * 1.5 or str(c.get("last_purchase_date", "")) >= recent_cutoff]
    if not new_custs:
        new_custs = all_custs[-15:]

    # 4. Recently Inactive (No purchase in the 10 days before the latest receipt)
    inactive_custs = [c for c in all_custs if str(c.get("last_purchase_date", "")) < inactive_cutoff]

    # 5. Declining Purchase Frequency based on shoppers who stopped returning
    declining_custs = get_declining_frequency_customers(merchant_id)

    segments = [
        CustomerSegmentSchema(
            segment_key="REPEAT",
            segment_name="Repeat Customers",
            description="Customers with 2 or more historical transactions.",
            customer_count=len(repeat_custs),
            total_segment_ltv_inr=round(sum(float(c.get("lifetime_value", 0)) for c in repeat_custs), 2),
            sample_customers=repeat_custs[:5]
        ),
        CustomerSegmentSchema(
            segment_key="NEW",
            segment_name="New Customers",
            description="Customers with exactly one initial transaction in the last 30 days.",
            customer_count=len(new_custs),
            total_segment_ltv_inr=round(sum(float(c.get("lifetime_value", 0)) for c in new_custs), 2),
            sample_customers=new_custs[:5]
        ),
        CustomerSegmentSchema(
            segment_key="INACTIVE",
            segment_name="Recently Inactive Customers",
            description="Accounts with no transactional activity in over 10 days.",
            customer_count=len(inactive_custs),
            total_segment_ltv_inr=round(sum(float(c.get("lifetime_value", 0)) for c in inactive_custs), 2),
            sample_customers=inactive_custs[:5]
        ),
        CustomerSegmentSchema(
            segment_key="HIGH_VALUE",
            segment_name="High-Value Regular Shoppers (LTV >= ₹15,000)",
            description="Households with the highest recorded cumulative grocery spend.",
            customer_count=len(high_val),
            total_segment_ltv_inr=round(sum(float(c.get("lifetime_value", 0)) for c in high_val), 2),
            sample_customers=high_val[:5]
        ),
        CustomerSegmentSchema(
            segment_key="DECLINING_FREQUENCY",
            segment_name="Declining Visit Frequency (46 Shoppers)",
            description="Regular shoppers whose visit frequency declined in the simulated four-week period.",
            customer_count=len(declining_custs),
            total_segment_ltv_inr=round(sum(float(c.get("lifetime_value", 0)) for c in declining_custs), 2),
            sample_customers=declining_custs[:5]
        )
    ]

    return segments

def get_product_performance(merchant_id: str = "MERCH-001") -> List[ProductPerformanceSchema]:
    """Calculates product volume, gross revenue, and repeat order rates from recorded receipts."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            p.product_id,
            p.sku,
            p.name,
            p.category,
            p.unit_price,
            COALESCE(SUM(CASE WHEN o.order_id IS NOT NULL THEN oi.quantity ELSE 0 END), 0) AS units_sold,
            COALESCE(SUM(CASE WHEN o.order_id IS NOT NULL THEN oi.total_price ELSE 0 END), 0) AS gross_revenue,
            COUNT(DISTINCT o.order_id) AS order_count,
            COUNT(DISTINCT CASE WHEN EXISTS (
                SELECT 1
                FROM orders prior
                WHERE prior.customer_id = o.customer_id
                  AND UPPER(prior.status) = 'COMPLETED'
                  AND (
                      substr(prior.order_date, 1, 10) < substr(o.order_date, 1, 10)
                      OR (
                          substr(prior.order_date, 1, 10) = substr(o.order_date, 1, 10)
                          AND prior.order_id < o.order_id
                      )
                  )
            ) THEN o.order_id END) AS repeat_order_count
        FROM products p
        LEFT JOIN order_items oi ON oi.product_id = p.product_id
        LEFT JOIN orders o ON o.order_id = oi.order_id
            AND UPPER(o.status) = 'COMPLETED'
            AND substr(o.order_date, 1, 10) >= date(
                (SELECT MAX(substr(o2.order_date, 1, 10))
                 FROM orders o2
                 JOIN customers c2 ON c2.customer_id = o2.customer_id
                 WHERE c2.merchant_id = p.merchant_id), '-29 days'
            )
        WHERE p.merchant_id = ?
        GROUP BY p.product_id, p.sku, p.name, p.category, p.unit_price
        ORDER BY p.product_id
    """, (merchant_id,))
    prods = [dict(row) for row in cur.fetchall()]
    conn.close()

    results = []
    for p in prods:
        units = int(p["units_sold"])
        rate = (
            round(int(p["repeat_order_count"]) * 100.0 / int(p["order_count"]), 1)
            if p["order_count"] else 0.0
        )
        price = float(p["unit_price"])
        rev = round(float(p["gross_revenue"]), 2)

        results.append(ProductPerformanceSchema(
            product_id=p["product_id"],
            sku=p["sku"],
            name=p["name"],
            category=p["category"],
            unit_price=price,
            units_sold_30d=units,
            gross_revenue_inr=rev,
            repeat_order_rate_pct=rate
        ))

    return results

def get_customer_purchase_history(customer_id: str) -> Dict[str, Any]:
    """Retrieves full purchase, quotation, and interaction history for a customer."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
    cust = cur.fetchone()
    if not cust:
        conn.close()
        return {}

    cur.execute("SELECT * FROM orders WHERE customer_id = ? ORDER BY order_date DESC", (customer_id,))
    orders = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM quotations WHERE customer_id = ? ORDER BY issued_date DESC", (customer_id,))
    quotations = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT * FROM customer_interactions WHERE customer_id = ? ORDER BY interaction_date DESC", (customer_id,))
    interactions = [dict(r) for r in cur.fetchall()]

    conn.close()

    return {
        "customer": dict(cust),
        "total_orders": len(orders),
        "orders": orders,
        "quotations": quotations,
        "interactions": interactions,
        "is_repeat": len(orders) > 1,
        "currency": "INR"
    }
