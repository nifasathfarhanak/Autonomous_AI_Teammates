from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(days_offset: int = 0, hours_offset: int = 0, minutes_offset: int = 0) -> str:
    ts = _utc_now() + timedelta(days=days_offset, hours=hours_offset, minutes=minutes_offset)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_business_mock_data() -> Dict[str, Any]:
    """Creates a full mock business dataset for demo merchants and operations."""
    merchants = [
        {
            "id": "MERCH-001",
            "store_name": "Sharma Commercial & Industrial Supplies",
            "owner_name": "Ramesh Sharma",
            "email": "ramesh@sharmasupplies.in",
            "phone": "+91 98110-23456",
            "city": "New Delhi",
            "soundbox_device_id": "SB-4G-DEL-9842",
            "soundbox_status": "ONLINE",
            "currency": "INR",
        },
        {
            "id": "MERCH-002",
            "store_name": "Hussain Fashion Store",
            "owner_name": "Zubair Hussain",
            "email": "zubair@hussainfashion.in",
            "phone": "+91 98290-11234",
            "city": "Jaipur",
            "soundbox_device_id": "SBOX-JP-8891",
            "soundbox_status": "ONLINE",
            "currency": "INR",
        },
        {
            "id": "MERCH-003",
            "store_name": "Nayan Agro Fresh",
            "owner_name": "Nayan Gupta",
            "email": "nayan@nayanagro.in",
            "phone": "+91 98370-44210",
            "city": "Lucknow",
            "soundbox_device_id": "SBOX-LKO-3041",
            "soundbox_status": "ONLINE",
            "currency": "INR",
        },
    ]

    products = [
        {
            "merchant_id": "MERCH-001",
            "product_id": "PROD-101",
            "name": "Industrial Valve Kit",
            "category": "Industrial Supplies",
            "sku": "IND-VALVE-101",
            "unit_price": 6400.0,
            "unit_cost": 4100.0,
            "stock_units": 84,
        },
        {
            "merchant_id": "MERCH-001",
            "product_id": "PROD-102",
            "name": "Boiler Maintenance Pack",
            "category": "Industrial Supplies",
            "sku": "BLR-MNT-204",
            "unit_price": 7800.0,
            "unit_cost": 5400.0,
            "stock_units": 62,
        },
        {
            "merchant_id": "MERCH-001",
            "product_id": "PROD-103",
            "name": "Foodline Conveyor Kit",
            "category": "Food Processing",
            "sku": "FDP-CONV-335",
            "unit_price": 11900.0,
            "unit_cost": 8200.0,
            "stock_units": 34,
        },
        {
            "merchant_id": "MERCH-002",
            "product_id": "PROD-201",
            "name": "Handcrafted Chikankari Kurta Set",
            "category": "Festive Ethnic Wear",
            "sku": "HFS-KURTA-201",
            "unit_price": 1750.0,
            "unit_cost": 850.0,
            "stock_units": 42,
        },
        {
            "merchant_id": "MERCH-002",
            "product_id": "PROD-202",
            "name": "Bandhani Silk Dupatta",
            "category": "Ethnic Accessories",
            "sku": "HFS-DUPATTA-202",
            "unit_price": 890.0,
            "unit_cost": 420.0,
            "stock_units": 74,
        },
        {
            "merchant_id": "MERCH-002",
            "product_id": "PROD-203",
            "name": "Jaipuri Printed Anarkali",
            "category": "Festive Wear",
            "sku": "HFS-ANARKALI-203",
            "unit_price": 999.0,
            "unit_cost": 480.0,
            "stock_units": 55,
        },
        {
            "merchant_id": "MERCH-003",
            "product_id": "PROD-301",
            "name": "Organic Kesar Mango Box",
            "category": "Fresh Produce",
            "sku": "NAY-MANGO-301",
            "unit_price": 480.0,
            "unit_cost": 300.0,
            "stock_units": 120,
        },
        {
            "merchant_id": "MERCH-003",
            "product_id": "PROD-302",
            "name": "Farm Fresh Vegetable Combo",
            "category": "Fresh Produce",
            "sku": "NAY-VEG-302",
            "unit_price": 390.0,
            "unit_cost": 220.0,
            "stock_units": 180,
        },
        {
            "merchant_id": "MERCH-003",
            "product_id": "PROD-303",
            "name": "Dairy Morning Basket",
            "category": "Dairy",
            "sku": "NAY-DAIRY-303",
            "unit_price": 560.0,
            "unit_cost": 330.0,
            "stock_units": 95,
        },
    ]

    customers = [
        {
            "customer_id": "CUST-MOCK-001",
            "merchant_id": "MERCH-001",
            "customer_name": "Arun Kumar",
            "email": "arun.kumar@biotechlabs.in",
            "company": "BioTech Research Labs",
            "phone": "+91 98711-23091",
            "last_purchase_date": _iso(days=-20),
            "last_purchase_value": 85000.0,
            "lifetime_value": 245000.0,
            "interested_product": "Industrial Valve Kit",
            "last_interaction_date": _iso(days=-5),
            "quotation_status": "UNANSWERED",
            "quotation_value": 65000.0,
            "preferred_language": "en",
            "is_unsubscribed": 0,
        },
        {
            "customer_id": "CUST-MOCK-002",
            "merchant_id": "MERCH-001",
            "customer_name": "Ananya Roy",
            "email": "ananya.roy@delhicatering.com",
            "company": "Delhi Fine Confectionery",
            "phone": "+91 98102-44120",
            "last_purchase_date": _iso(days=-12),
            "last_purchase_value": 42000.0,
            "lifetime_value": 186000.0,
            "interested_product": "Foodline Conveyor Kit",
            "last_interaction_date": _iso(days=-3),
            "quotation_status": "UNANSWERED",
            "quotation_value": 52000.0,
            "preferred_language": "en",
            "is_unsubscribed": 0,
        },
        {
            "customer_id": "CUST-MOCK-003",
            "merchant_id": "MERCH-002",
            "customer_name": "Pinky Sharma",
            "email": "pinky.s@gmail.com",
            "company": "Sharma Household",
            "phone": "+91 98290-33441",
            "last_purchase_date": _iso(days=-10),
            "last_purchase_value": 2800.0,
            "lifetime_value": 14500.0,
            "interested_product": "Handcrafted Chikankari Kurta Set",
            "last_interaction_date": _iso(days=-2),
            "quotation_status": "CONVERTED",
            "quotation_value": 0.0,
            "preferred_language": "hi",
            "is_unsubscribed": 0,
        },
        {
            "customer_id": "CUST-MOCK-004",
            "merchant_id": "MERCH-002",
            "customer_name": "Rehana Begum",
            "email": "rehana.b@yahoo.co.in",
            "company": "Begum Textiles",
            "phone": "+91 98291-55662",
            "last_purchase_date": _iso(days=-18),
            "last_purchase_value": 4500.0,
            "lifetime_value": 22000.0,
            "interested_product": "Bandhani Silk Dupatta",
            "last_interaction_date": _iso(days=-4),
            "quotation_status": "CONVERTED",
            "quotation_value": 0.0,
            "preferred_language": "hi",
            "is_unsubscribed": 0,
        },
        {
            "customer_id": "CUST-MOCK-005",
            "merchant_id": "MERCH-003",
            "customer_name": "Nandini Sethi",
            "email": "nandini.sethi@greenbasket.in",
            "company": "Green Basket Hotels",
            "phone": "+91 98340-55611",
            "last_purchase_date": _iso(days=-14),
            "last_purchase_value": 4200.0,
            "lifetime_value": 29000.0,
            "interested_product": "Farm Fresh Vegetable Combo",
            "last_interaction_date": _iso(days=-6),
            "quotation_status": "SENT",
            "quotation_value": 2100.0,
            "preferred_language": "hi",
            "is_unsubscribed": 0,
        },
        {
            "customer_id": "CUST-MOCK-006",
            "merchant_id": "MERCH-003",
            "customer_name": "Manish Verma",
            "email": "manish.verma@freshharvest.co",
            "company": "Fresh Harvest Wholesale",
            "phone": "+91 98341-77144",
            "last_purchase_date": _iso(days=-29),
            "last_purchase_value": 5600.0,
            "lifetime_value": 39500.0,
            "interested_product": "Organic Kesar Mango Box",
            "last_interaction_date": _iso(days=-9),
            "quotation_status": "UNANSWERED",
            "quotation_value": 3200.0,
            "preferred_language": "en",
            "is_unsubscribed": 0,
        },
    ]

    orders = [
        {
            "order_id": "ORDER-MOCK-001",
            "customer_id": "CUST-MOCK-001",
            "order_date": _iso(days=-20),
            "order_value": 85000.0,
            "status": "COMPLETED",
            "product_summary": "Industrial Valve Kit",
        },
        {
            "order_id": "ORDER-MOCK-002",
            "customer_id": "CUST-MOCK-002",
            "order_date": _iso(days=-12),
            "order_value": 42000.0,
            "status": "COMPLETED",
            "product_summary": "Foodline Conveyor Kit",
        },
        {
            "order_id": "ORDER-MOCK-003",
            "customer_id": "CUST-MOCK-003",
            "order_date": _iso(days=-10),
            "order_value": 2800.0,
            "status": "COMPLETED",
            "product_summary": "Chikankari Kurta Set",
        },
        {
            "order_id": "ORDER-MOCK-004",
            "customer_id": "CUST-MOCK-004",
            "order_date": _iso(days=-18),
            "order_value": 4500.0,
            "status": "COMPLETED",
            "product_summary": "Bandhani Silk Dupatta",
        },
        {
            "order_id": "ORDER-MOCK-005",
            "customer_id": "CUST-MOCK-005",
            "order_date": _iso(days=-14),
            "order_value": 4200.0,
            "status": "COMPLETED",
            "product_summary": "Farm Fresh Vegetable Combo",
        },
        {
            "order_id": "ORDER-MOCK-006",
            "customer_id": "CUST-MOCK-006",
            "order_date": _iso(days=-29),
            "order_value": 5600.0,
            "status": "COMPLETED",
            "product_summary": "Organic Kesar Mango Box",
        },
    ]

    quotations = [
        {
            "quotation_id": "Q-MOCK-001",
            "customer_id": "CUST-MOCK-001",
            "product_name": "Industrial Valve Kit",
            "quotation_value": 65000.0,
            "status": "UNANSWERED",
            "issued_date": _iso(days=-8),
            "valid_until": _iso(days=7),
        },
        {
            "quotation_id": "Q-MOCK-002",
            "customer_id": "CUST-MOCK-005",
            "product_name": "Farm Fresh Vegetable Combo",
            "quotation_value": 2100.0,
            "status": "SENT",
            "issued_date": _iso(days=-5),
            "valid_until": _iso(days=10),
        },
    ]

    opportunities = [
        {
            "opportunity_id": "OPP-MOCK-001",
            "customer_id": "CUST-MOCK-001",
            "merchant_id": "MERCH-001",
            "opportunity_category": "REPEAT_CUSTOMER_RECOVERY",
            "estimated_opportunity_value": 182000.0,
            "recovery_score": 89,
            "score_breakdown_json": json.dumps({"recency": 90, "frequency": 85, "value": 92, "engagement": 80}),
            "evidence_summary": "High-value repeat buyer with strong historical order value and low recent engagement.",
            "recommended_next_action": "Send high-touch reactivation offer with margin-safe bundle.",
            "status": "IDENTIFIED",
            "created_at": _iso(days=-3),
        },
        {
            "opportunity_id": "OPP-MOCK-002",
            "customer_id": "CUST-MOCK-004",
            "merchant_id": "MERCH-002",
            "opportunity_category": "SEASONAL_REVIVAL",
            "estimated_opportunity_value": 32000.0,
            "recovery_score": 83,
            "score_breakdown_json": json.dumps({"recency": 79, "frequency": 82, "value": 86, "engagement": 81}),
            "evidence_summary": "Customer has repeat festive purchases and is active in local seasonal demand windows.",
            "recommended_next_action": "Bundle silk dupatta with festive kurta at a limited discount.",
            "status": "IDENTIFIED",
            "created_at": _iso(days=-5),
        },
    ]

    campaigns = [
        {
            "campaign_id": "CAMP-MOCK-001",
            "merchant_id": "MERCH-001",
            "title": "High-Touch Re-engagement Drive",
            "strategy_type": "TARGETED_DISCOUNT",
            "target_criteria": "Dormant high-value accounts",
            "status": "ACTIVE",
            "budget_cap": 3500.0,
            "created_at": _iso(days=-10),
        },
        {
            "campaign_id": "CAMP-MOCK-002",
            "merchant_id": "MERCH-002",
            "title": "Festive Royal Bundle",
            "strategy_type": "BUNDLE_PROMOTION",
            "target_criteria": "Festive and repeat shoppers",
            "status": "ACTIVE",
            "budget_cap": 2500.0,
            "created_at": _iso(days=-7),
        },
    ]

    voice_sessions = [
        {
            "session_id": "VSESS-MOCK-001",
            "merchant_id": "MERCH-002",
            "language_code": "hi-IN",
            "status": "ACTIVE",
            "created_at": _iso(days=-1),
            "updated_at": _iso(minutes=-10),
        }
    ]

    voice_interactions = [
        {
            "interaction_id": "VINT-MOCK-001",
            "session_id": "VSESS-MOCK-001",
            "merchant_id": "MERCH-002",
            "input_mode": "VOICE",
            "transcript": "मेरी बिक्री कम क्यों हो रही है?",
            "detected_intent": "SALES_DROP_ANALYSIS",
            "language_code": "hi-IN",
            "response_text": "आपकी बिक्री पिछले सप्ताह 22% गिर गई है, इसलिए हम Festive Royal Bundle का सुझाव दे रहे हैं.",
            "audio_response_url": None,
            "audio_base64": None,
            "structured_payload_json": json.dumps({"sales_drop_pct": 22.0, "segment": "Repeat customers"}),
            "latency_ms": 640,
            "created_at": _iso(minutes=-10),
        }
    ]

    bazaar_signal = {
        "signal_id": "SIG-MOCK-001",
        "neighbourhood_id": "NEIGHBOURHOOD-JP-01",
        "product_category": "Festive Ethnic Apparel",
        "sub_category": "Kurtas & Silk Dupattas",
        "signal_name": "Festive Ethnic Kurtas & Silk Dupattas Surge",
        "demand_trend": "SURGE",
        "growth_rate_pct": 38.5,
        "reporting_merchants_count": 7,
        "min_cohort_threshold": 5,
        "privacy_suppressed": False,
        "suppression_reason": None,
        "confidence_score": 0.94,
        "time_window": "Past 7 Days",
        "is_simulated": True,
        "provenance_note": "Model-generated mock signal for the Johari Bazaar cluster.",
        "created_at": _iso(days=-1),
    }

    return {
        "generated_at": _iso(),
        "version": "mock-business-v1",
        "merchants": merchants,
        "products": products,
        "customers": customers,
        "orders": orders,
        "quotations": quotations,
        "opportunities": opportunities,
        "campaigns": campaigns,
        "voice_sessions": voice_sessions,
        "voice_interactions": voice_interactions,
        "bazaar_signal": bazaar_signal,
    }


def seed_business_mock_data(conn) -> Dict[str, Any]:
    """Insert the business mock data into the SQLite database if not already present."""
    cur = conn.cursor()
    snapshot = generate_business_mock_data()

    for merchant in snapshot["merchants"]:
        cur.execute(
            """
            INSERT OR REPLACE INTO merchants (
                id, store_name, owner_name, email, phone, city, soundbox_device_id, soundbox_status, currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                merchant["id"],
                merchant["store_name"],
                merchant["owner_name"],
                merchant["email"],
                merchant["phone"],
                merchant["city"],
                merchant["soundbox_device_id"],
                merchant["soundbox_status"],
                merchant["currency"],
            ),
        )

    for product in snapshot["products"]:
        cur.execute(
            """
            INSERT OR REPLACE INTO products (
                product_id, merchant_id, sku, name, category, unit_price
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                product["product_id"],
                product["merchant_id"],
                product["sku"],
                product["name"],
                product["category"],
                product["unit_price"],
            ),
        )
        cur.execute(
            """
            INSERT OR REPLACE INTO merchant_inventory (
                inventory_id, merchant_id, product_id, product_name, category,
                current_stock_units, min_safety_stock, reorder_point, lead_time_days,
                unit_cost_inr, unit_selling_price_inr, stock_age_days, last_restocked_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"INV-MOCK-{product['product_id']}",
                product["merchant_id"],
                product["product_id"],
                product["name"],
                product["category"],
                product["stock_units"],
                max(5, int(product["stock_units"] * 0.12)),
                max(8, int(product["stock_units"] * 0.2)),
                4,
                product["unit_cost"],
                product["unit_price"],
                12,
                _iso(days=-45),
            ),
        )

    for customer in snapshot["customers"]:
        cur.execute(
            """
            INSERT OR REPLACE INTO customers (
                customer_id, merchant_id, customer_name, email, company, phone,
                last_purchase_date, last_purchase_value, lifetime_value,
                interested_product, last_interaction_date, quotation_status,
                quotation_value, preferred_language, is_unsubscribed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer["customer_id"],
                customer["merchant_id"],
                customer["customer_name"],
                customer["email"],
                customer["company"],
                customer["phone"],
                customer["last_purchase_date"],
                customer["last_purchase_value"],
                customer["lifetime_value"],
                customer["interested_product"],
                customer["last_interaction_date"],
                customer["quotation_status"],
                customer["quotation_value"],
                customer["preferred_language"],
                customer["is_unsubscribed"],
            ),
        )

    for order in snapshot["orders"]:
        cur.execute(
            """
            INSERT OR REPLACE INTO orders (
                order_id, customer_id, order_date, order_value, status, product_summary
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                order["order_id"],
                order["customer_id"],
                order["order_date"],
                order["order_value"],
                order["status"],
                order["product_summary"],
            ),
        )

    for quote in snapshot["quotations"]:
        cur.execute(
            """
            INSERT OR REPLACE INTO quotations (
                quotation_id, customer_id, product_name, quotation_value, status, issued_date, valid_until
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quote["quotation_id"],
                quote["customer_id"],
                quote["product_name"],
                quote["quotation_value"],
                quote["status"],
                quote["issued_date"],
                quote["valid_until"],
            ),
        )

    for opp in snapshot["opportunities"]:
        cur.execute(
            """
            INSERT OR REPLACE INTO opportunities (
                opportunity_id, customer_id, merchant_id, opportunity_category,
                estimated_opportunity_value, recovery_score, score_breakdown_json,
                evidence_summary, recommended_next_action, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opp["opportunity_id"],
                opp["customer_id"],
                opp["merchant_id"],
                opp["opportunity_category"],
                opp["estimated_opportunity_value"],
                opp["recovery_score"],
                opp["score_breakdown_json"],
                opp["evidence_summary"],
                opp["recommended_next_action"],
                opp["status"],
                opp["created_at"],
            ),
        )

    for campaign in snapshot["campaigns"]:
        cur.execute(
            """
            INSERT OR REPLACE INTO recovery_campaigns (
                campaign_id, merchant_id, title, strategy_type, target_criteria, status, budget_cap, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                campaign["campaign_id"],
                campaign["merchant_id"],
                campaign["title"],
                campaign["strategy_type"],
                campaign["target_criteria"],
                campaign["status"],
                campaign["budget_cap"],
                campaign["created_at"],
            ),
        )

    for session in snapshot["voice_sessions"]:
        cur.execute(
            """
            INSERT OR REPLACE INTO voice_sessions (
                session_id, merchant_id, language_code, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["session_id"],
                session["merchant_id"],
                session["language_code"],
                session["status"],
                session["created_at"],
                session["updated_at"],
            ),
        )

    for interaction in snapshot["voice_interactions"]:
        cur.execute(
            """
            INSERT OR REPLACE INTO voice_interactions (
                interaction_id, session_id, merchant_id, input_mode, transcript,
                detected_intent, language_code, response_text, audio_response_url,
                audio_base64, structured_payload_json, latency_ms, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                interaction["interaction_id"],
                interaction["session_id"],
                interaction["merchant_id"],
                interaction["input_mode"],
                interaction["transcript"],
                interaction["detected_intent"],
                interaction["language_code"],
                interaction["response_text"],
                interaction["audio_response_url"],
                interaction["audio_base64"],
                interaction["structured_payload_json"],
                interaction["latency_ms"],
                interaction["created_at"],
            ),
        )

    bz = snapshot["bazaar_signal"]
    cur.execute(
        """
        INSERT OR REPLACE INTO bazaar_demand_signals (
            signal_id, neighbourhood_id, product_category, sub_category,
            signal_name, demand_trend, growth_rate_pct, reporting_merchants_count,
            min_cohort_threshold, privacy_suppressed, suppression_reason, confidence_score,
            time_window, is_simulated, provenance_note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bz["signal_id"],
            bz["neighbourhood_id"],
            bz["product_category"],
            bz["sub_category"],
            bz["signal_name"],
            bz["demand_trend"],
            bz["growth_rate_pct"],
            bz["reporting_merchants_count"],
            bz["min_cohort_threshold"],
            1 if bz["privacy_suppressed"] else 0,
            bz["suppression_reason"],
            bz["confidence_score"],
            bz["time_window"],
            1 if bz["is_simulated"] else 0,
            bz["provenance_note"],
            bz["created_at"],
        ),
    )

    cur.execute(
        """
        INSERT OR REPLACE INTO bazaar_opportunity_matches (
            match_id, merchant_id, signal_id, opportunity_name,
            matching_score, relevance_status, score_breakdown_json,
            compatible_products_json, recommended_strategy_json,
            decision_twin_scenarios_json, estimated_revenue_inr,
            estimated_gross_profit_inr, stockout_risk, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "MATCH-MOCK-001",
            "MERCH-002",
            "SIG-MOCK-001",
            "Festive Royal Bundle Re-engagement",
            94.0,
            "EXCELLENT",
            json.dumps({"product_relevance": 96.0, "inventory_depth": 92.0, "margin_headroom": 95.0}),
            json.dumps([
                {"product_id": "PROD-201", "product_name": "Handcrafted Chikankari Kurta Set"},
                {"product_id": "PROD-202", "product_name": "Bandhani Silk Dupatta"},
            ]),
            json.dumps({"strategy_key": "BALANCED", "bundle_price_inr": 2299.0, "discount_pct": 8.0}),
            json.dumps({"BALANCED": {"discount_pct": 8.0, "projected_revenue_inr": 32186.0}}),
            32186.0,
            14406.0,
            "LOW",
            "AVAILABLE",
            _iso(days=-1),
        ),
    )

    conn.commit()
    return {"status": "success", "seeded_records": len(snapshot["customers"]) + len(snapshot["products"]) + len(snapshot["orders"]), "generated_at": snapshot["generated_at"]}


__all__ = ["generate_business_mock_data", "seed_business_mock_data"]
