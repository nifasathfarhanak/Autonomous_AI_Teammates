"""DealPilot AI Enterprise Database Schema and Seeding.
Provides full relational persistence across 24 enterprise tables:
1. organizations / merchants
2. users
3. organization_members
4. customers
5. products
6. orders
7. quotations
8. customer_interactions
9. opportunities (recovery_opportunities)
10. recovery_campaigns
11. campaign_customers
12. ai_agents
13. agent_executions
14. agent_execution_logs
15. customer_research (customer_research_reports)
16. recovery_strategies (recovery_recommendations)
17. approvals (approval_requests)
18. executions (email_messages)
19. followup_schedules (scheduled_followups)
20. customer_replies
21. verified_purchases (revenue_attributions)
22. integration_connections
23. audit_trail (audit_events)
24. organization_policies (organization_settings)
"""

import sqlite3
import json
import os
import random
from datetime import datetime, timedelta, timezone
from .config import DB_PATH

def get_connection():
    """Returns an active SQLite connection configured with WAL mode and foreign keys."""
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Creates all 24 required enterprise tables and seeds realistic data."""
    conn = get_connection()
    cur = conn.cursor()

    # 1. Organizations / Merchants
    cur.execute("""
    CREATE TABLE IF NOT EXISTS merchants (
        id TEXT PRIMARY KEY,
        store_name TEXT NOT NULL,
        owner_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        city TEXT NOT NULL,
        soundbox_device_id TEXT NOT NULL,
        soundbox_status TEXT DEFAULT 'ONLINE',
        currency TEXT DEFAULT 'INR',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Users Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT DEFAULT 'SALES_MANAGER',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # 3. Organization Members Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS organization_members (
        id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        status TEXT DEFAULT 'ACTIVE',
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)

    # 4. Customers Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        customer_name TEXT NOT NULL,
        email TEXT NOT NULL,
        company TEXT,
        phone TEXT NOT NULL,
        last_purchase_date TEXT,
        last_purchase_value REAL DEFAULT 0.0,
        lifetime_value REAL DEFAULT 0.0,
        interested_product TEXT,
        last_interaction_date TEXT,
        quotation_status TEXT DEFAULT 'NONE',
        quotation_value REAL DEFAULT 0.0,
        preferred_language TEXT DEFAULT 'en',
        is_unsubscribed BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # 5. Products Catalog
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        sku TEXT NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        unit_price REAL NOT NULL,
        in_stock BOOLEAN DEFAULT 1,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # 6. Historical Orders Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        order_date TEXT NOT NULL,
        order_value REAL NOT NULL,
        status TEXT DEFAULT 'COMPLETED',
        product_summary TEXT,
        FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
    );
    """)

    # 6b. Order Items Table
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

    # 7. Quotations Records
    cur.execute("""
    CREATE TABLE IF NOT EXISTS quotations (
        quotation_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        product_name TEXT NOT NULL,
        quotation_value REAL NOT NULL,
        status TEXT DEFAULT 'UNANSWERED',
        issued_date TEXT NOT NULL,
        valid_until TEXT,
        FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
    );
    """)

    # 8. Customer Interaction Logs
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customer_interactions (
        interaction_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        channel TEXT NOT NULL,
        summary TEXT NOT NULL,
        sentiment TEXT DEFAULT 'NEUTRAL',
        interaction_date TEXT NOT NULL,
        FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
    );
    """)

    # 9. Opportunities (Agent 1: Revenue Intelligence)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS opportunities (
        opportunity_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        merchant_id TEXT NOT NULL,
        opportunity_category TEXT NOT NULL,
        estimated_opportunity_value REAL NOT NULL,
        recovery_score INTEGER NOT NULL,
        score_breakdown_json JSON NOT NULL,
        evidence_summary TEXT NOT NULL,
        recommended_next_action TEXT NOT NULL,
        status TEXT DEFAULT 'IDENTIFIED',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
    );
    """)

    # 10. Recovery Campaigns
    cur.execute("""
    CREATE TABLE IF NOT EXISTS recovery_campaigns (
        campaign_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        title TEXT NOT NULL,
        strategy_type TEXT NOT NULL,
        target_criteria TEXT,
        status TEXT DEFAULT 'ACTIVE',
        budget_cap REAL DEFAULT 10000.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # 11. Campaign Customers
    cur.execute("""
    CREATE TABLE IF NOT EXISTS campaign_customers (
        campaign_id TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        current_stage TEXT DEFAULT 'QUEUED',
        enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(campaign_id, customer_id),
        FOREIGN KEY(campaign_id) REFERENCES recovery_campaigns(campaign_id),
        FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
    );
    """)

    # 12. AI Agents Registry
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ai_agents (
        agent_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role_title TEXT NOT NULL,
        description TEXT NOT NULL,
        model_name TEXT NOT NULL,
        status TEXT DEFAULT 'ONLINE',
        tasks_completed INTEGER DEFAULT 0,
        tasks_failed INTEGER DEFAULT 0,
        success_rate REAL DEFAULT 98.4,
        last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 13. Agent Executions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS agent_executions (
        execution_id TEXT PRIMARY KEY,
        agent_id TEXT NOT NULL,
        task_name TEXT NOT NULL,
        customer_id TEXT,
        status TEXT DEFAULT 'COMPLETED',
        duration_ms INTEGER DEFAULT 180,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(agent_id) REFERENCES ai_agents(agent_id)
    );
    """)

    # 14. Agent Execution Logs (Tool Calls)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS agent_execution_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        execution_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        input_json JSON NOT NULL,
        output_json JSON NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(execution_id) REFERENCES agent_executions(execution_id)
    );
    """)

    # 15. Customer Research Reports (Agent 2: Customer Research)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customer_research (
        report_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        confirmed_facts JSON NOT NULL,
        inferred_observations JSON NOT NULL,
        missing_information JSON NOT NULL,
        unverified_assumptions JSON NOT NULL,
        previous_commitments TEXT,
        unresolved_complaints TEXT,
        research_summary TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(opportunity_id),
        FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
    );
    """)

    # 16. Recovery Strategy Recommendations (Agent 3: Recovery Strategy)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS recovery_strategies (
        strategy_id TEXT PRIMARY KEY,
        opportunity_id TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        strategy_type TEXT NOT NULL,
        selected_tone TEXT NOT NULL,
        communication_language TEXT NOT NULL,
        email_subject TEXT NOT NULL,
        email_body TEXT NOT NULL,
        customer_specific_context TEXT NOT NULL,
        strategy_justification TEXT NOT NULL,
        potential_commercial_value REAL NOT NULL,
        recommended_follow_up_date TEXT NOT NULL,
        is_user_edited BOOLEAN DEFAULT 0,
        approval_status TEXT DEFAULT 'PENDING_APPROVAL',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(opportunity_id),
        FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
    );
    """)

    # 17. Human-in-the-Loop Approvals
    cur.execute("""
    CREATE TABLE IF NOT EXISTS approvals (
        id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        task_id TEXT,
        campaign_id TEXT,
        merchant_id TEXT DEFAULT 'MERCH-001',
        approver_id TEXT DEFAULT 'USER-001',
        decision TEXT NOT NULL,
        approved_by TEXT NOT NULL,
        max_budget_authorized_inr REAL NOT NULL,
        message_override TEXT,
        message_version INTEGER DEFAULT 1,
        content_hash TEXT,
        reason_or_comments TEXT,
        approval_status TEXT DEFAULT 'VALID',
        auth_signature TEXT NOT NULL,
        decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 18. Executions & Email Messages (Agent 4: Execution & Follow-up)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS executions (
        execution_id TEXT PRIMARY KEY,
        strategy_id TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        channel TEXT DEFAULT 'EMAIL',
        recipient_email TEXT NOT NULL,
        sent_subject TEXT NOT NULL,
        sent_body TEXT NOT NULL,
        dispatch_status TEXT NOT NULL,
        delivery_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        response_classification TEXT DEFAULT 'NO_RESPONSE',
        response_notes TEXT,
        next_recommended_action TEXT,
        verified_recovered_revenue REAL DEFAULT 0.0,
        is_revenue_verified BOOLEAN DEFAULT 0,
        FOREIGN KEY(strategy_id) REFERENCES recovery_strategies(strategy_id),
        FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
    );
    """)

    # 19. Persistent Follow-up Schedules (Day 0, Day 3, Day 7)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS followup_schedules (
        schedule_id TEXT PRIMARY KEY,
        strategy_id TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        step_number INTEGER NOT NULL,
        interval_days INTEGER NOT NULL,
        planned_date TEXT NOT NULL,
        status TEXT DEFAULT 'SCHEDULED',
        cancellation_reason TEXT,
        subject TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(strategy_id) REFERENCES recovery_strategies(strategy_id),
        FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
    );
    """)

    # 20. Customer Replies
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customer_replies (
        reply_id TEXT PRIMARY KEY,
        execution_id TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        reply_text TEXT NOT NULL,
        classification TEXT NOT NULL,
        intent_confidence REAL DEFAULT 0.95,
        detected_language TEXT DEFAULT 'en',
        received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(execution_id) REFERENCES executions(execution_id),
        FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
    );
    """)

    # 21. Verified Purchases & Revenue Attribution (4 strict categories)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS verified_purchases (
        purchase_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        order_id TEXT NOT NULL,
        product TEXT NOT NULL,
        purchase_amount REAL NOT NULL,
        currency TEXT DEFAULT 'INR',
        purchase_date TEXT NOT NULL,
        associated_recovery_campaign TEXT NOT NULL,
        evidence_source TEXT NOT NULL,
        attribution_confidence TEXT NOT NULL,
        revenue_category TEXT NOT NULL,
        baseline_comparison_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
    );
    """)

    # 22. Integration Connections (Sarvam, Gmail, etc.)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS integration_connections (
        connection_id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        status TEXT NOT NULL,
        account_email TEXT,
        last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata_json JSON
    );
    """)

    # 23. Tamper-Evident Audit Ledger (SHA-256 Chaining)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_trail (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT,
        merchant_id TEXT DEFAULT 'MERCH-001',
        task_id TEXT,
        workflow_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        actor_id TEXT DEFAULT 'system',
        action_type TEXT NOT NULL,
        resource TEXT,
        previous_state TEXT,
        new_state TEXT,
        tool_name TEXT NOT NULL,
        tool_input_json JSON NOT NULL,
        tool_output_json JSON NOT NULL,
        execution_duration_ms INTEGER NOT NULL,
        is_simulated BOOLEAN DEFAULT 0,
        previous_hash TEXT NOT NULL,
        current_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 24. Organization Policies & Automation Settings
    cur.execute("""
    CREATE TABLE IF NOT EXISTS organization_policies (
        policy_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        require_approval_by_default BOOLEAN DEFAULT 1,
        authorized_automation_policy_enabled BOOLEAN DEFAULT 0,
        followup_day_1 INTEGER DEFAULT 0,
        followup_day_2 INTEGER DEFAULT 3,
        followup_day_3 INTEGER DEFAULT 7,
        weight_historical_val REAL DEFAULT 0.25,
        weight_purchase_intent REAL DEFAULT 0.25,
        weight_recency REAL DEFAULT 0.20,
        weight_quotation REAL DEFAULT 0.20,
        weight_engagement REAL DEFAULT 0.10,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # Legacy workflows & roi_metrics for full backward compatibility
    cur.execute("""
    CREATE TABLE IF NOT EXISTS workflows (
        id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        title TEXT NOT NULL,
        workflow_type TEXT NOT NULL,
        current_state TEXT NOT NULL,
        detected_leakage_inr REAL NOT NULL,
        target_cohort_count INTEGER NOT NULL,
        discount_code TEXT NOT NULL,
        discount_amount_inr REAL NOT NULL,
        min_order_inr REAL NOT NULL,
        max_liability_cap_inr REAL NOT NULL,
        anomaly_payload JSON NOT NULL,
        strategy_payload JSON NOT NULL,
        messages_payload JSON NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS roi_metrics (
        workflow_id TEXT PRIMARY KEY,
        total_targeted INTEGER NOT NULL,
        total_delivered INTEGER DEFAULT 0,
        total_redeemed INTEGER DEFAULT 0,
        gross_recovered_sales_inr REAL DEFAULT 0.0,
        total_discounts_paid_inr REAL DEFAULT 0.0,
        total_execution_cost_inr REAL DEFAULT 0.0,
        net_recovered_profit_inr REAL DEFAULT 0.0,
        roi_multiple REAL DEFAULT 0.0,
        is_verified BOOLEAN DEFAULT FALSE,
        last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 24. ActionMate Autonomous Tasks (Phase 3)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        original_request TEXT NOT NULL,
        detected_intent TEXT NOT NULL,
        current_state TEXT NOT NULL,
        risk_classification TEXT NOT NULL,
        requires_approval BOOLEAN DEFAULT 1,
        entities_json JSON,
        required_data_json JSON,
        plan_json JSON,
        findings_json JSON,
        epistemic_report_json JSON,
        recommendations_json JSON,
        approval_details_json JSON,
        execution_result_json JSON,
        is_demo BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # 25. Task State History & Audit Ledger
    cur.execute("""
    CREATE TABLE IF NOT EXISTS task_state_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL,
        from_state TEXT NOT NULL,
        to_state TEXT NOT NULL,
        transitioned_by TEXT NOT NULL,
        reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(task_id) REFERENCES tasks(task_id)
    );
    """)

    # 26. Campaign Drafts (Phase 4)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS campaign_drafts (
        campaign_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        campaign_name TEXT NOT NULL,
        business_objective TEXT NOT NULL,
        reason_for_recommendation TEXT NOT NULL,
        target_customer_segment TEXT NOT NULL,
        suggested_duration TEXT NOT NULL,
        communication_channel TEXT NOT NULL,
        promotional_approach TEXT NOT NULL,
        expected_operational_outcome TEXT NOT NULL,
        risks_and_assumptions TEXT NOT NULL,
        status TEXT DEFAULT 'DRAFT',
        offer_configured BOOLEAN DEFAULT 0,
        offer_json JSON,
        messages_json JSON,
        audience_json JSON,
        execution_result_json JSON,
        execution_id TEXT,
        idempotency_key TEXT UNIQUE,
        is_demo BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # 27. Campaign Recipient Simulated Statuses
    cur.execute("""
    CREATE TABLE IF NOT EXISTS campaign_recipient_statuses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id TEXT NOT NULL,
        execution_id TEXT NOT NULL,
        customer_id TEXT NOT NULL,
        customer_name TEXT NOT NULL,
        channel TEXT NOT NULL,
        contact_destination TEXT NOT NULL,
        message_rendered TEXT NOT NULL,
        simulated_status TEXT NOT NULL,
        exclusion_reason TEXT,
        simulated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(campaign_id) REFERENCES campaign_drafts(campaign_id),
        FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
    );
    """)

    # 28. Campaign Activity Timeline
    cur.execute("""
    CREATE TABLE IF NOT EXISTS campaign_activity_timeline (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        description TEXT NOT NULL,
        actor TEXT NOT NULL,
        details_json JSON,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(campaign_id) REFERENCES campaign_drafts(campaign_id)
    );
    """)

    # 29. Verification Engine Records (Phase 6)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS verifications (
        verification_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        campaign_id TEXT NOT NULL,
        execution_id TEXT NOT NULL,
        verification_status TEXT NOT NULL,
        verified_checks_json JSON NOT NULL,
        failed_checks_json JSON NOT NULL,
        checks_detail_json JSON NOT NULL,
        evidence_references_json JSON NOT NULL,
        is_demo BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(campaign_id) REFERENCES campaign_drafts(campaign_id)
    );
    """)

    # 30. Task Failure & Human Escalations (Phase 6)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS task_escalations (
        escalation_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        campaign_id TEXT,
        escalation_reason TEXT NOT NULL,
        suggested_action TEXT NOT NULL,
        escalated_to TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING_HUMAN',
        resolution_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP
    );
    """)

    # 31. Phase 8: Merchant Inventory Intelligence Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS merchant_inventory (
        inventory_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        product_id TEXT NOT NULL,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        current_stock_units INTEGER NOT NULL,
        min_safety_stock INTEGER NOT NULL,
        reorder_point INTEGER NOT NULL,
        lead_time_days INTEGER NOT NULL,
        unit_cost_inr REAL NOT NULL,
        unit_selling_price_inr REAL NOT NULL,
        stock_age_days INTEGER NOT NULL,
        holding_cost_rate REAL DEFAULT 0.02,
        last_restocked_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id),
        FOREIGN KEY(product_id) REFERENCES products(product_id)
    );
    """)

    # 32. Phase 8: Merchant Operational Expenses Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS merchant_expenses (
        expense_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        category TEXT NOT NULL,
        vendor_name TEXT NOT NULL,
        description TEXT,
        amount_inr REAL NOT NULL,
        due_date TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING',
        payment_method TEXT DEFAULT 'BANK_TRANSFER',
        is_recurring BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # 33. Phase 8: Merchant Inflow Settlements Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS merchant_settlements (
        settlement_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        settlement_date TEXT NOT NULL,
        expected_amount_inr REAL NOT NULL,
        channel TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING',
        gross_sales_inr REAL NOT NULL,
        fee_deducted_inr REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # 34. Phase 8: No-Regret Merchant Guardrails Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS merchant_guardrails (
        rule_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        rule_code TEXT NOT NULL,
        rule_name TEXT NOT NULL,
        parameter_value REAL NOT NULL,
        unit TEXT NOT NULL,
        description TEXT NOT NULL,
        enforcement_level TEXT DEFAULT 'HARD_BLOCK',
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id),
        UNIQUE(merchant_id, rule_code)
    );
    """)

    # 35. Phase 8: Decision Twin Simulations Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS decision_simulations (
        simulation_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        task_id TEXT,
        scenario_key TEXT NOT NULL,
        strategy_name TEXT NOT NULL,
        strategy_description TEXT NOT NULL,
        target_segment TEXT NOT NULL,
        audience_count INTEGER NOT NULL,
        offer_details_json JSON,
        estimated_revenue_inr REAL NOT NULL,
        estimated_gross_profit_inr REAL NOT NULL,
        estimated_margin_pct REAL NOT NULL,
        marketing_cost_inr REAL NOT NULL,
        discount_cost_inr REAL NOT NULL,
        net_contribution_inr REAL NOT NULL,
        expected_roi_multiple REAL NOT NULL,
        inventory_impact_units INTEGER NOT NULL,
        customer_impact_score REAL NOT NULL,
        operational_risk_level TEXT NOT NULL,
        confidence_level REAL NOT NULL,
        guardrails_passed BOOLEAN DEFAULT 1,
        guardrail_warnings_json JSON,
        calculation_assumptions_json JSON,
        is_recommended BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # 36. Phase 8: Incremental Outcome & Holdout Experiments Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS outcome_experiments (
        experiment_id TEXT PRIMARY KEY,
        campaign_id TEXT NOT NULL,
        merchant_id TEXT NOT NULL,
        experiment_name TEXT NOT NULL,
        time_window_days INTEGER DEFAULT 7,
        treatment_count INTEGER NOT NULL,
        holdout_count INTEGER NOT NULL,
        treatment_conversions INTEGER NOT NULL,
        holdout_conversions INTEGER NOT NULL,
        treatment_conversion_rate REAL NOT NULL,
        holdout_conversion_rate REAL NOT NULL,
        conversion_lift_pts REAL NOT NULL,
        incremental_orders INTEGER NOT NULL,
        incremental_revenue_inr REAL NOT NULL,
        incremental_gross_profit_inr REAL NOT NULL,
        campaign_expenditure_inr REAL NOT NULL,
        net_incremental_profit_inr REAL NOT NULL,
        incremental_roi_multiple REAL NOT NULL,
        causal_confidence_score REAL NOT NULL,
        outcome_status TEXT DEFAULT 'SIMULATED_DEMO',
        disclaimer TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # 37. Phase 8: Proactive Business Opportunities Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS business_opportunities (
        opportunity_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        category TEXT NOT NULL,
        title TEXT NOT NULL,
        problem_statement TEXT NOT NULL,
        evidence_json JSON NOT NULL,
        financial_impact_inr REAL NOT NULL,
        recommended_action TEXT NOT NULL,
        expected_cost_inr REAL NOT NULL,
        expected_benefit_inr REAL NOT NULL,
        urgency_level TEXT NOT NULL,
        confidence_level REAL NOT NULL,
        required_permission TEXT NOT NULL,
        verification_method TEXT NOT NULL,
        status TEXT DEFAULT 'OPEN',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # 38. Phase 9: Voice Copilot Sessions Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS voice_sessions (
        session_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        language_code TEXT DEFAULT 'hi-IN',
        status TEXT DEFAULT 'ACTIVE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # 39. Phase 9: Voice Copilot Interactions Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS voice_interactions (
        interaction_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        merchant_id TEXT NOT NULL,
        input_mode TEXT DEFAULT 'VOICE',
        transcript TEXT NOT NULL,
        detected_intent TEXT NOT NULL,
        language_code TEXT DEFAULT 'hi-IN',
        response_text TEXT NOT NULL,
        audio_response_url TEXT,
        audio_base64 TEXT,
        structured_payload_json JSON,
        latency_ms INTEGER DEFAULT 350,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(session_id) REFERENCES voice_sessions(session_id),
        FOREIGN KEY(merchant_id) REFERENCES merchants(id)
    );
    """)

    # 40. Phase 9: Bazaar Participating Merchants Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bazaar_participating_merchants (
        merchant_id TEXT PRIMARY KEY,
        store_name TEXT NOT NULL,
        category TEXT NOT NULL,
        sub_category TEXT,
        neighbourhood_id TEXT NOT NULL,
        neighbourhood_name TEXT NOT NULL,
        city TEXT NOT NULL,
        consent_opt_in BOOLEAN DEFAULT 1,
        participating_since TEXT,
        annual_turnover_tier TEXT,
        reputation_score REAL DEFAULT 4.8,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 41. Phase 9: Bazaar Aggregated Demand Signals Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bazaar_demand_signals (
        signal_id TEXT PRIMARY KEY,
        neighbourhood_id TEXT NOT NULL,
        product_category TEXT NOT NULL,
        sub_category TEXT NOT NULL,
        signal_name TEXT NOT NULL,
        demand_trend TEXT NOT NULL,
        growth_rate_pct REAL NOT NULL,
        reporting_merchants_count INTEGER NOT NULL,
        min_cohort_threshold INTEGER DEFAULT 5,
        privacy_suppressed BOOLEAN DEFAULT 0,
        suppression_reason TEXT,
        confidence_score REAL DEFAULT 0.92,
        time_window TEXT DEFAULT 'Past 7 Days',
        is_simulated BOOLEAN DEFAULT 1,
        provenance_note TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 42. Phase 9: Bazaar Opportunity Matches Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bazaar_opportunity_matches (
        match_id TEXT PRIMARY KEY,
        merchant_id TEXT NOT NULL,
        signal_id TEXT NOT NULL,
        opportunity_name TEXT NOT NULL,
        matching_score REAL NOT NULL,
        relevance_status TEXT NOT NULL,
        score_breakdown_json JSON NOT NULL,
        compatible_products_json JSON NOT NULL,
        recommended_strategy_json JSON NOT NULL,
        decision_twin_scenarios_json JSON NOT NULL,
        estimated_revenue_inr REAL NOT NULL,
        estimated_gross_profit_inr REAL NOT NULL,
        stockout_risk TEXT DEFAULT 'LOW',
        status TEXT DEFAULT 'AVAILABLE',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(merchant_id) REFERENCES merchants(id),
        FOREIGN KEY(signal_id) REFERENCES bazaar_demand_signals(signal_id)
    );
    """)

    # Phase 5 & 6 Safe Column Migrations for Approvals, Audit Trail, Tasks, and Campaigns
    for col, col_def in [
        ("task_id", "TEXT"),
        ("campaign_id", "TEXT"),
        ("merchant_id", "TEXT DEFAULT 'MERCH-001'"),
        ("approver_id", "TEXT DEFAULT 'USER-001'"),
        ("message_version", "INTEGER DEFAULT 1"),
        ("content_hash", "TEXT"),
        ("reason_or_comments", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'VALID'")
    ]:
        try:
            cur.execute(f"ALTER TABLE approvals ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    for col, col_def in [
        ("event_id", "TEXT"),
        ("merchant_id", "TEXT DEFAULT 'MERCH-001'"),
        ("task_id", "TEXT"),
        ("actor_id", "TEXT DEFAULT 'system'"),
        ("resource", "TEXT"),
        ("previous_state", "TEXT"),
        ("new_state", "TEXT"),
        ("is_simulated", "BOOLEAN DEFAULT 0")
    ]:
        try:
            cur.execute(f"ALTER TABLE audit_trail ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    for col, col_def in [
        ("completed_at", "TIMESTAMP"),
        ("duration_seconds", "REAL DEFAULT 240.0"),
        ("escalated_to", "TEXT"),
        ("retry_count", "INTEGER DEFAULT 0"),
        ("operating_cost_inr", "REAL DEFAULT 3.10"),
        ("is_verified", "BOOLEAN DEFAULT 0")
    ]:
        try:
            cur.execute(f"ALTER TABLE tasks ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    for col, col_def in [
        ("verification_status", "TEXT DEFAULT 'UNVERIFIED'"),
        ("verification_id", "TEXT"),
        ("retry_count", "INTEGER DEFAULT 0"),
        ("escalated_to", "TEXT")
    ]:
        try:
            cur.execute(f"ALTER TABLE campaign_drafts ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    for col, col_def in [
        ("simulated_engaged", "BOOLEAN DEFAULT 0"),
        ("simulated_engagement_type", "TEXT")
    ]:
        try:
            cur.execute(f"ALTER TABLE campaign_recipient_statuses ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    conn.commit()
    seed_enterprise_data(conn)
    conn.close()

def _seed_100_customers(cur):
    """Internal helper to seed 100 enterprise accounts."""
    primary_customers = [
        ("CUST-1001", "MERCH-001", "Arun Kumar", "arun.kumar@biotechlabs.in", "BioTech Research Labs", "+91 98711-23091",
         "2026-08-19", 85000.0, 245000.0, "Laboratory reactor accessories & thermal units", "2026-08-19",
         "UNANSWERED", 65000.0, "en", 0),
        ("CUST-1002", "MERCH-001", "Ananya Roy", "ananya.roy@delhicatering.com", "Delhi Fine Confectionery", "+91 98102-44120",
         "2026-10-02", 42000.0, 186000.0, "Festive gourmet corporate sweet gift hampers", "2026-10-14",
         "UNANSWERED", 52000.0, "en", 0),
        ("CUST-1003", "MERCH-001", "Rajesh Sharma", "rajesh.sharma@apexinfra.org", "Apex Engineering Infra", "+91 98230-11980",
         "2026-07-10", 112000.0, 390000.0, "Industrial boiler spare components & valves", "2026-08-04",
         "SENT", 94000.0, "hi", 0),
        ("CUST-1004", "MERCH-001", "Priya Venkatesh", "priya.v@chennaimetalworks.com", "Chennai Precision Metalworks", "+91 94440-88219",
         "2026-09-28", 34000.0, 98000.0, "Custom CNC precision brass fittings (500 units)", "2026-10-18",
         "NONE", 0.0, "ta", 0),
        ("CUST-1005", "MERCH-001", "Vikram Patel", "vpatel@gujaratchemicals.co.in", "Gujarat Specialty Polymers", "+91 98250-77341",
         "2026-06-15", 145000.0, 480000.0, "High-density polymer drums & chemical valves", "2026-07-20",
         "EXPIRED", 120000.0, "gu", 0),
        ("CUST-1006", "MERCH-001", "Kavita Reddy", "kavita.reddy@hyderabadfoodtech.in", "Hyderabad Foodtech Ventures", "+91 99890-55412",
         "2026-09-12", 28000.0, 74000.0, "Commercial food packaging machines (Grade 304)", "2026-10-01",
         "UNANSWERED", 48000.0, "te", 0),
        ("CUST-1007", "MERCH-001", "Amit Banerjee", "amit.b@kolkatapharma.net", "Kolkata Allied Pharmaceuticals", "+91 98310-99234",
         "2026-08-30", 67000.0, 210000.0, "Cleanroom sterilization packs & filters", "2026-09-22",
         "SENT", 58000.0, "bn", 0),
        ("CUST-1008", "MERCH-001", "Sunita Deshmukh", "sunita.d@puneauto.co.in", "Pune Automotive Die Castings", "+91 98220-33418",
         "2026-07-22", 95000.0, 310000.0, "Precision automotive gasket sheets & seals", "2026-08-28",
         "NONE", 0.0, "mr", 0),
        ("CUST-1009", "MERCH-001", "Rohan Mehta", "rohan@delhidistributors.in", "North India FMCG Distributors", "+91 98118-77123",
         "2026-10-08", 54000.0, 160000.0, "Festive gourmet corporate sweet gift hampers", "2026-10-21",
         "UNANSWERED", 36000.0, "en", 0),
        ("CUST-1010", "MERCH-001", "Sneha Joshi", "sneha.j@mumbaicorporategifts.com", "Mumbai Corporate Hospitality", "+91 98201-66789",
         "2026-09-05", 78000.0, 290000.0, "Festive gourmet corporate sweet gift hampers", "2026-09-29",
         "UNANSWERED", 75000.0, "en", 0),
    ]

    for c in primary_customers:
        cur.execute("""
        INSERT OR REPLACE INTO customers (customer_id, merchant_id, customer_name, email, company, phone,
                               last_purchase_date, last_purchase_value, lifetime_value,
                               interested_product, last_interaction_date, quotation_status,
                               quotation_value, preferred_language, is_unsubscribed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, c)

    first_names = ["Siddharth", "Meenakshi", "Girish", "Deepa", "Manish", "Shweta", "Naveen", "Archana",
                   "Harish", "Bhavna", "Alok", "Pallavi", "Vivek", "Rashmi", "Chetan", "Sandhya", "Pranav", "Nandini"]
    last_names = ["Nair", "Iyer", "Kulkarni", "Aggarwal", "Sengupta", "Verma", "Pillai", "Choudhury",
                  "Bhattacharya", "Trivedi", "Rao", "Shetty", "Menon", "Jain", "Bhatia", "Gowda"]
    companies = ["Southern Precision Tools", "Bangalore Biotech Systems", "Universal Packaging Corp",
                 "Himalaya Pharma Equipment", "Deccan Automation Solutions", "Maruti Die Works",
                 "Godavari Agro Processors", "Western Engineering Works", "Zenith Cleanroom Tech",
                 "Sterling Instruments & Labs", "Matrix Industrial Supply", "Supreme Polymer Products"]
    products_pool = [
        "Laboratory reactor accessories & thermal units",
        "Industrial boiler spare components & valves",
        "Commercial food packaging machines (Grade 304)",
        "Cleanroom sterilization packs & filters",
        "Custom CNC precision brass fittings (500 units)",
        "High-density polymer drums & chemical valves",
        "Festive gourmet corporate sweet gift hampers",
        "Precision automotive gasket sheets & seals"
    ]
    langs = ["en", "hi", "kn", "ta", "te", "bn", "mr", "gu"]

    random.seed(42)
    for i in range(11, 101):
        cid = f"CUST-{1000 + i}"
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        name = f"{fn} {ln}"
        domain = random.choice(["enterprise.in", "industries.com", "technologies.org", "supplies.co.in"])
        email = f"{fn.lower()}.{ln.lower()}{random.randint(10,99)}@{domain}"
        comp = random.choice(companies)
        phone = f"+91 9{random.randint(1000, 9999)}-{random.randint(10000, 99999)}"
        prod = random.choice(products_pool)
        lang = random.choice(langs)

        is_inactive = (i <= 40)
        has_quote = (15 <= i <= 35)
        is_high_value = (i % 6 == 0)

        if is_inactive:
            days_ago = random.randint(65, 120)
        else:
            days_ago = random.randint(15, 55)

        ref_date = datetime(2026, 10, 30)
        last_int_dt = (ref_date - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        last_pur_dt = (ref_date - timedelta(days=days_ago + random.randint(10, 40))).strftime("%Y-%m-%d")

        if is_high_value:
            ltv = float(random.randint(210000, 650000))
            last_pur_val = float(random.randint(75000, 180000))
        else:
            ltv = float(random.randint(45000, 195000))
            last_pur_val = float(random.randint(15000, 60000))

        if has_quote:
            q_status = "UNANSWERED" if random.random() > 0.3 else "SENT"
            q_val = float(random.randint(35000, 110000))
        else:
            q_status = "NONE"
            q_val = 0.0

        # Inject realistic exclusion cases for targeting tests:
        # CUST-1045 is unsubscribed; CUST-1046 has invalid email; CUST-1047 has missing phone
        unsub = 1 if i == 45 else 0
        if i == 46:
            email = "invalid_email_format_no_at"
        elif i == 47:
            phone = ""

        cur.execute("""
        INSERT OR REPLACE INTO customers (customer_id, merchant_id, customer_name, email, company, phone,
                               last_purchase_date, last_purchase_value, lifetime_value,
                               interested_product, last_interaction_date, quotation_status,
                               quotation_value, preferred_language, is_unsubscribed)
        VALUES (?, 'MERCH-001', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (cid, name, email, comp, phone, last_pur_dt, last_pur_val, ltv, prod, last_int_dt, q_status, q_val, lang, unsub))

def seed_enterprise_data(conn):
    """Seeds 100 enterprise customers across 4 distinct B2B sectors,
    the 4 AI teammates, product catalog, initial opportunities, and integrations."""
    cur = conn.cursor()

    # Seed Merchant Profile
    cur.execute("SELECT id FROM merchants WHERE id = 'MERCH-001'")
    if not cur.fetchone():
        cur.execute("""
        INSERT INTO merchants (id, store_name, owner_name, email, phone, city, soundbox_device_id, soundbox_status, currency)
        VALUES ('MERCH-001', 'Sharma Commercial & Industrial Supplies', 'Ramesh Sharma', 'ramesh@sharmasupplies.in', '+91 98110-23456', 'Connaught Place, New Delhi', 'SB-4G-DEL-9842', 'ONLINE', 'INR')
        """)

    # Seed Users
    cur.execute("SELECT id FROM users WHERE id = 'USER-001'")
    if not cur.fetchone():
        cur.execute("""
        INSERT INTO users (id, merchant_id, email, full_name, role)
        VALUES ('USER-001', 'MERCH-001', 'ramesh@sharmasupplies.in', 'Ramesh Sharma', 'OWNER')
        """)

    # Seed AI Agents
    agents = [
        ("AGENT-001", "Revenue Intelligence Agent", "Opportunity Discovery Specialist",
         "Discovers missed revenue, inactive accounts, and cold quotations using 5-factor mathematical scoring.",
         "sarvam-105b", "ONLINE", 142, 2, 98.6),
        ("AGENT-002", "Customer Research Agent", "Customer Intelligence Specialist",
         "Builds objective epistemic research reports distinguishing confirmed facts, inferences, and missing data.",
         "sarvam-105b", "ONLINE", 128, 1, 99.2),
        ("AGENT-003", "Recovery Strategy Agent", "Sales Strategy Specialist",
         "Decides the best recovery action, selects consultative tone, and writes localized Indic copy via Sarvam AI.",
         "sarvam-105b + Mayura:v1", "ONLINE", 119, 3, 97.5),
        ("AGENT-004", "Execution & Follow-up Agent", "Customer Engagement Specialist",
         "Dispatches verified communications, enforces opt-out safeguards, monitors replies, and records verified purchases.",
         "Gmail API / Demo Adapter", "ONLINE", 98, 0, 100.0)
    ]
    for a in agents:
        cur.execute("""
        INSERT OR REPLACE INTO ai_agents (agent_id, name, role_title, description, model_name, status, tasks_completed, tasks_failed, success_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, a)

    # Seed Products Catalog
    products = [
        ("PROD-001", "MERCH-001", "LAB-RCT-01", "Laboratory reactor accessories & thermal units", "Biotech & Laboratory", 65000.0),
        ("PROD-002", "MERCH-001", "IND-BLR-02", "Industrial boiler spare components & valves", "Industrial Engineering", 94000.0),
        ("PROD-003", "MERCH-001", "PKG-FOD-03", "Commercial food packaging machines (Grade 304)", "Food & Confectionery", 48000.0),
        ("PROD-004", "MERCH-001", "MED-STR-04", "Cleanroom sterilization packs & filters", "Medical & Pharma", 58000.0),
        ("PROD-005", "MERCH-001", "CNC-BRS-05", "Custom CNC precision brass fittings (500 units)", "Industrial Engineering", 34000.0),
        ("PROD-006", "MERCH-001", "POL-DRM-06", "High-density polymer drums & chemical valves", "Chemicals", 120000.0),
        ("PROD-007", "MERCH-001", "FST-HAM-07", "Festive gourmet corporate sweet gift hampers", "Food & Confectionery", 75000.0),
        ("PROD-008", "MERCH-001", "AUT-GSK-08", "Precision automotive gasket sheets & seals", "Automotive", 45000.0),
    ]
    for p in products:
        cur.execute("""
        INSERT OR REPLACE INTO products (product_id, merchant_id, sku, name, category, unit_price)
        VALUES (?, ?, ?, ?, ?, ?)
        """, p)

    # Seed customers if not already present
    cur.execute("SELECT COUNT(*) FROM customers")
    if cur.fetchone()[0] < 100:
        _seed_100_customers(cur)

    # Deterministic exclusion accounts for Phase 4 targeting tests
    cur.execute("UPDATE customers SET is_unsubscribed = 1 WHERE customer_id = 'CUST-1045'")
    cur.execute("UPDATE customers SET email = 'invalid-email-format' WHERE customer_id = 'CUST-1046'")
    cur.execute("UPDATE customers SET phone = '' WHERE customer_id = 'CUST-1047'")

    # Seed Default Integrations
    integrations = [
        ("INT-001", "Sarvam AI Indic Sovereign Platform", "CONNECTED", "api.sarvam.ai (Mayura, 105B, Bulbul, Saaras)",
         json.dumps({"models": ["sarvam-105b", "mayura:v1", "bulbul:v1", "saaras:v2"], "languages": 8, "health": "OPERATIONAL"})),
        ("INT-002", "Gmail API OAuth Gateway", "CONFIGURED_DEMO_ADAPTER", "offers@sharmasupplies.in",
         json.dumps({"provider": "Gmail API", "mode": "DEMO_EMAIL_ADAPTER", "status": "READY_FOR_RFC822_DISPATCH"})),
        ("INT-003", "CSV Data Ingestion Engine", "CONNECTED", "Local Workspace File System",
         json.dumps({"supported_formats": [".csv", ".tsv"], "max_batch_size": 5000}))
    ]
    for integ in integrations:
        cur.execute("""
        INSERT OR REPLACE INTO integration_connections (connection_id, provider, status, account_email, metadata_json)
        VALUES (?, ?, ?, ?, ?)
        """, integ)

    # Seed Organization Policy
    cur.execute("""
    INSERT OR REPLACE INTO organization_policies (
        policy_id, merchant_id, require_approval_by_default, authorized_automation_policy_enabled,
        followup_day_1, followup_day_2, followup_day_3,
        weight_historical_val, weight_purchase_intent, weight_recency, weight_quotation, weight_engagement
    ) VALUES ('POL-MERCH-001', 'MERCH-001', 1, 0, 0, 3, 7, 0.25, 0.25, 0.20, 0.20, 0.10)
    """)

    # Seed Legacy Workflows and ROI Metrics
    cur.execute("SELECT id FROM workflows WHERE id = 'WF-REC-1042'")
    if not cur.fetchone():
        anomaly_payload = {
            "event_type": "TELEMETRY_ANOMALY_REPEAT_PURCHASE_DROP",
            "soundbox_device_id": "SB-4G-DEL-9842",
            "drop_percentage": 18.4,
            "revenue_leakage_inr": 20900.0,
            "missing_patrons_count": 46,
            "target_dormant_cohort_size": 240,
            "period": "Thursday & Friday Lunch Window"
        }
        strategy_payload = {
            "discount_code": "RET50",
            "discount_amount_inr": 50.0,
            "min_order_inr": 249.0,
            "max_liability_cap_inr": 3600.0,
            "expected_redemption_rate_pct": 18.2,
            "expected_gross_sales_inr": 28500.0
        }
        messages_payload = {
            "en": "Hi [Customer Name]! We miss you at Sharma Sweets. Enjoy ₹50 OFF on your next order above ₹249 this weekend with code RET50 on Paytm Soundbox / QR. Valid till Sunday midnight!",
            "hi": "नमस्ते [ग्राहक का नाम]! शर्मा स्वीट्स में आपकी कमी महसूस हुई। इस वीकेंड पेटीएम QR पर कोड RET50 के साथ ₹249 से ऊपर के ऑर्डर पर ₹50 की छूट पाएं। रविवार मध्यरात्रि तक वैध!"
        }
        cur.execute("""
        INSERT INTO workflows (id, merchant_id, title, workflow_type, current_state,
                               detected_leakage_inr, target_cohort_count, discount_code,
                               discount_amount_inr, min_order_inr, max_liability_cap_inr,
                               anomaly_payload, strategy_payload, messages_payload)
        VALUES ('WF-REC-1042', 'MERCH-001', 'Recover 240 Dormant Repeat Diners', 'REVENUE_RECOVERY',
                'AWAITING_APPROVAL', 20900.0, 240, 'RET50', 50.0, 249.0, 3600.0,
                ?, ?, ?)
        """, (json.dumps(anomaly_payload), json.dumps(strategy_payload), json.dumps(messages_payload)))

    cur.execute("""
    INSERT OR IGNORE INTO roi_metrics (workflow_id, total_targeted, total_delivered, total_redeemed,
                            gross_recovered_sales_inr, total_discounts_paid_inr,
                            total_execution_cost_inr, net_recovered_profit_inr, roi_multiple, is_verified)
    VALUES ('WF-REC-1042', 240, 0, 0, 0.0, 0.0, 96.0, 0.0, 0.0, 0)
    """)

    # Seed Historical Recovery Campaigns
    cur.execute("SELECT COUNT(*) FROM recovery_campaigns")
    if cur.fetchone()[0] == 0:
        cur.execute("""
        INSERT INTO recovery_campaigns (campaign_id, merchant_id, title, strategy_type, target_criteria, status, budget_cap)
        VALUES ('CAMP-2026-SEP-01', 'MERCH-001', 'Late Summer Machinery Spare Parts Rebate', 'TARGETED_DISCOUNT', 'Inactive accounts > 45 days', 'COMPLETED', 15000.0)
        """)
        cur.execute("""
        INSERT INTO recovery_campaigns (campaign_id, merchant_id, title, strategy_type, target_criteria, status, budget_cap)
        VALUES ('CAMP-2026-AUG-15', 'MERCH-001', 'Independence Day Wholesale High-Volume Promo', 'VOLUME_DISCOUNT', 'Orders exceeding ₹50k', 'COMPLETED', 25000.0)
        """)

    
    for col, col_def in [
        ("task_id", "TEXT"),
        ("campaign_id", "TEXT"),
        ("merchant_id", "TEXT DEFAULT 'MERCH-001'"),
        ("approver_id", "TEXT DEFAULT 'USER-001'"),
        ("message_version", "INTEGER DEFAULT 1"),
        ("content_hash", "TEXT"),
        ("reason_or_comments", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'VALID'")
    ]:
        try:
            cur.execute(f"ALTER TABLE approvals ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    for col, col_def in [
        ("event_id", "TEXT"),
        ("merchant_id", "TEXT DEFAULT 'MERCH-001'"),
        ("task_id", "TEXT"),
        ("actor_id", "TEXT DEFAULT 'system'"),
        ("resource", "TEXT"),
        ("previous_state", "TEXT"),
        ("new_state", "TEXT"),
        ("is_simulated", "BOOLEAN DEFAULT 0")
    ]:
        try:
            cur.execute(f"ALTER TABLE audit_trail ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    # Phase 5 Safe Column Migrations for Approvals & Audit Trail
    for col, col_def in [
        ("task_id", "TEXT"),
        ("campaign_id", "TEXT"),
        ("merchant_id", "TEXT DEFAULT 'MERCH-001'"),
        ("approver_id", "TEXT DEFAULT 'USER-001'"),
        ("message_version", "INTEGER DEFAULT 1"),
        ("content_hash", "TEXT"),
        ("reason_or_comments", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'VALID'")
    ]:
        try:
            cur.execute(f"ALTER TABLE approvals ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    for col, col_def in [
        ("event_id", "TEXT"),
        ("merchant_id", "TEXT DEFAULT 'MERCH-001'"),
        ("task_id", "TEXT"),
        ("actor_id", "TEXT DEFAULT 'system'"),
        ("resource", "TEXT"),
        ("previous_state", "TEXT"),
        ("new_state", "TEXT"),
        ("is_simulated", "BOOLEAN DEFAULT 0")
    ]:
        try:
            cur.execute(f"ALTER TABLE audit_trail ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    conn.commit()

    # Seed Sales Transactions, Order Items, Quotations, and Interactions
    try:
        from .services.sales_intelligence_service import seed_sales_transactions
        seed_sales_transactions(conn)
    except Exception as e:
        print(f"Warning: Failed to seed sales transactions: {e}")

    # Seed Phase 8 Business Innovation Data
    try:
        _seed_phase8_data(conn)
    except Exception as e:
        print(f"Warning: Failed to seed Phase 8 business innovation data: {e}")

    # Seed Phase 9 Voice Copilot & Bazaar Intelligence Data
    try:
        _seed_phase9_data(conn)
    except Exception as e:
        print(f"Warning: Failed to seed Phase 9 data: {e}")

def _seed_phase8_data(conn):
    """Seeds realistic Phase 8 inventory, expenses, settlements, guardrails, and business opportunities."""
    cur = conn.cursor()
    now_utc = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc)

    # 1. Seed Inventory (8 SKUs)
    cur.execute("SELECT COUNT(*) FROM merchant_inventory")
    if cur.fetchone()[0] == 0:
        inventory_items = [
            ("INV-001", "MERCH-001", "PROD-001", "Laboratory reactor accessories & thermal units", "Laboratory Equipment", 14, 5, 8, 4, 55000.0, 85000.0, 18),
            ("INV-002", "MERCH-001", "PROD-002", "Industrial boiler spare components & valves", "Thermal Equipment", 28, 10, 15, 3, 32000.0, 48000.0, 25),
            ("INV-003", "MERCH-001", "PROD-003", "Commercial food packaging machines (Grade 304)", "Machinery", 6, 3, 5, 5, 85000.0, 125000.0, 14),
            ("INV-004", "MERCH-001", "PROD-004", "Cleanroom sterilization packs & filters", "Sterilization", 65, 20, 30, 2, 1800.0, 3200.0, 15),
            ("INV-005", "MERCH-001", "PROD-005", "Custom CNC precision brass fittings (500 units)", "Precision Hardware", 19, 4, 6, 6, 42000.0, 58000.0, 95),
            ("INV-006", "MERCH-001", "PROD-006", "High-density polymer drums & chemical valves", "General Supplies", 4, 6, 10, 3, 4200.0, 7500.0, 8),
            ("INV-007", "MERCH-001", "PROD-007", "Festive gourmet corporate sweet gift hampers", "Corporate Gifts", 45, 15, 25, 2, 650.0, 1200.0, 12),
            ("INV-008", "MERCH-001", "PROD-008", "Precision automotive gasket sheets & seals", "Automotive Seals", 9, 3, 5, 7, 58000.0, 75000.0, 82)
        ]
        for item in inventory_items:
            cur.execute("""
            INSERT OR REPLACE INTO merchant_inventory (
                inventory_id, merchant_id, product_id, product_name, category,
                current_stock_units, min_safety_stock, reorder_point, lead_time_days,
                unit_cost_inr, unit_selling_price_inr, stock_age_days, last_restocked_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (*item, (today - timedelta(days=item[11])).strftime("%Y-%m-%d")))

    # 2. Seed Operational Expenses
    cur.execute("SELECT COUNT(*) FROM merchant_expenses")
    if cur.fetchone()[0] == 0:
        expenses = [
            ("EXP-001", "MERCH-001", "SUPPLIER_INVOICE", "Kavita Glassware & Scientific Ltd", "Procurement invoice for borosilicate reactors", 22000.0, (today + timedelta(days=3)).strftime("%Y-%m-%d"), "PENDING"),
            ("EXP-002", "MERCH-001", "UTILITIES", "Jaipur Vidyut Vitran Nigam", "Warehouse commercial electricity bill", 8000.0, (today + timedelta(days=5)).strftime("%Y-%m-%d"), "PENDING"),
            ("EXP-003", "MERCH-001", "EQUIPMENT_MAINTENANCE", "Precision Calibration Services", "Scale and sensor calibration retainer", 6500.0, (today + timedelta(days=8)).strftime("%Y-%m-%d"), "PENDING"),
            ("EXP-004", "MERCH-001", "RENT", "Connaught Commercial Properties", "Showroom and sales office commercial lease", 45000.0, (today + timedelta(days=15)).strftime("%Y-%m-%d"), "SCHEDULED")
        ]
        for exp in expenses:
            cur.execute("""
            INSERT OR REPLACE INTO merchant_expenses (
                expense_id, merchant_id, category, vendor_name, description, amount_inr, due_date, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, exp)

    # 3. Seed Inflow Settlements
    cur.execute("SELECT COUNT(*) FROM merchant_settlements")
    if cur.fetchone()[0] == 0:
        settlements = [
            ("SETTL-001", "MERCH-001", (today + timedelta(days=1)).strftime("%Y-%m-%d"), 18500.0, "PAYTM_SOUNDBOX", "PENDING", 18500.0, 0.0),
            ("SETTL-002", "MERCH-001", (today + timedelta(days=2)).strftime("%Y-%m-%d"), 12800.0, "PAYTM_QR", "PENDING", 12800.0, 0.0),
            ("SETTL-003", "MERCH-001", (today + timedelta(days=4)).strftime("%Y-%m-%d"), 24000.0, "CARD", "PENDING", 24300.0, 300.0),
            ("SETTL-004", "MERCH-001", (today + timedelta(days=6)).strftime("%Y-%m-%d"), 16200.0, "PAYTM_SOUNDBOX", "PENDING", 16200.0, 0.0)
        ]
        for st in settlements:
            cur.execute("""
            INSERT OR REPLACE INTO merchant_settlements (
                settlement_id, merchant_id, settlement_date, expected_amount_inr, channel, status, gross_sales_inr, fee_deducted_inr
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, st)

    # 4. Seed No-Regret Merchant Guardrails
    cur.execute("SELECT COUNT(*) FROM merchant_guardrails WHERE merchant_id = 'MERCH-001'")
    if cur.fetchone()[0] == 0:
        guardrails = [
            ("RULE-01", "MERCH-001", "MAX_DISCOUNT_PERCENT", "Maximum Promotional Discount", 10.0, "PERCENT", "Promotional campaigns cannot offer discounts exceeding 10.0%", "HARD_BLOCK"),
            ("RULE-02", "MERCH-001", "MAX_CAMPAIGN_BUDGET_INR", "Maximum Campaign Budget", 3600.0, "INR", "Autonomous campaign execution cannot commit marketing spend > ₹3,600", "HARD_BLOCK"),
            ("RULE-03", "MERCH-001", "MIN_GROSS_MARGIN_PERCENT", "Minimum Product Gross Margin Floor", 25.0, "PERCENT", "Discounts cannot reduce gross product margin below 25.0%", "HARD_BLOCK"),
            ("RULE-04", "MERCH-001", "INVENTORY_SAFETY_STOCK_DAYS", "Minimum Stock Days for Promotion", 5.0, "DAYS", "Cannot promote products with fewer than 5 days of inventory on hand", "HARD_BLOCK"),
            ("RULE-05", "MERCH-001", "CUSTOMER_FREQUENCY_CAP_PER_MONTH", "Max Customer Contact Frequency", 2.0, "MESSAGES", "No single customer can receive more than 2 promotional messages in a calendar month", "HARD_BLOCK"),
            ("RULE-06", "MERCH-001", "MANDATORY_HUMAN_APPROVAL", "Human Approval Gate Enforcement", 1.0, "BOOLEAN", "Customer-facing promotional messages strictly require merchant owner sign-off", "HARD_BLOCK")
        ]
        for g in guardrails:
            cur.execute("""
            INSERT OR REPLACE INTO merchant_guardrails (
                rule_id, merchant_id, rule_code, rule_name, parameter_value, unit, description, enforcement_level, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, g)

    # 5. Seed Proactive Business Opportunities
    cur.execute("SELECT COUNT(*) FROM business_opportunities")
    if cur.fetchone()[0] == 0:
        opportunities = [
            ("OPP-001", "MERCH-001", "PROFITABILITY", "High-Revenue SKU Has Margin Dilution (PROD-008)",
             "Autoclaves generate ₹75k sales but unit margin is 22.7%, below the 25% merchant floor.",
             json.dumps({"product_id": "PROD-008", "selling_price": 75000.0, "unit_cost": 58000.0, "margin_pct": 22.7, "floor_pct": 25.0}),
             34000.0, "Renegotiate supplier procurement PO or bundle with high-margin Reagents (40.9% margin)",
             0.0, 34000.0, "HIGH", 0.92, "CATEGORY_A", "Supplier contract margin recalculation"),
            ("OPP-002", "MERCH-001", "INVENTORY", "Imminent Stockout on Top Performer (PROD-006)",
             "Magnetic Stirrers are down to 4 units with a 3-day lead time. Estimated stockout in 2 days.",
             json.dumps({"product_id": "PROD-006", "current_stock": 4, "daily_velocity": 2.0, "lead_time_days": 3}),
             15000.0, "Trigger supplier reorder for 20 units immediately to prevent ₹15k in lost sales.",
             0.0, 15000.0, "HIGH", 0.95, "CATEGORY_A", "Inventory PO tracking"),
            ("OPP-003", "MERCH-001", "INVENTORY", "Slow-Moving Capital Trapped in Ovens (PROD-005)",
             "19 units of Industrial Ovens have been in stock for 95 days. ₹798,000 working capital is trapped.",
             json.dumps({"product_id": "PROD-005", "stock_units": 19, "age_days": 95, "trapped_capital_inr": 798000.0}),
             110000.0, "Create a bundled equipment package with high-demand consumables to release liquidity.",
             1200.0, 110000.0, "MEDIUM", 0.88, "CATEGORY_B", "Inventory clearance velocity measurement"),
            ("OPP-004", "MERCH-001", "CASH_FLOW", "Upcoming Cash-Flow Pinch Window (Days 3-5)",
             "Committed supplier payments (₹22,000) and power utility (₹8,000) will absorb 96% of early inflows.",
             json.dumps({"committed_outflows": 30000.0, "expected_inflows_early": 31300.0, "liquidity_buffer": 1300.0}),
             30000.0, "Review upcoming supplier payment schedule or prioritize Soundbox cash collections.",
             0.0, 30000.0, "HIGH", 0.90, "CATEGORY_A", "Settlement and bank statement reconciliation"),
            ("OPP-005", "MERCH-001", "CUSTOMER_RETENTION", "Repeat Lunch Customer Dormancy (46 Patrons)",
             "Repeat customer orders dropped from 41% to 24% over 4 weeks, creating ₹20,900 revenue leakage.",
             json.dumps({"week_1_pct": 41.0, "week_4_pct": 24.0, "unreturned_patrons": 46, "revenue_leakage": 20900.0}),
             20900.0, "Execute approved WhatsApp, SMS & Soundbox reactivation sprint with code RET50.",
             133.30, 20900.0, "HIGH", 0.94, "CATEGORY_B", "Closed-loop 7-point execution verification"),
            ("OPP-006", "MERCH-001", "CUSTOMER_RETENTION", "12 High-Value Accounts Inactive for > 45 Days",
             "12 enterprise accounts with historical LTV > ₹150k have had zero interaction in the last 45 days.",
             json.dumps({"inactive_vip_count": 12, "combined_ltv_inr": 1850000.0}),
             48000.0, "Dispatch personalized relationship-manager check-in without discounting.",
             0.0, 48000.0, "MEDIUM", 0.85, "CATEGORY_B", "Customer re-order tracking")
        ]
        for opp in opportunities:
            cur.execute("""
            INSERT OR REPLACE INTO business_opportunities (
                opportunity_id, merchant_id, category, title, problem_statement, evidence_json,
                financial_impact_inr, recommended_action, expected_cost_inr, expected_benefit_inr,
                urgency_level, confidence_level, required_permission, verification_method, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
            """, (*opp, now_utc, now_utc))

    # 6. Seed Initial Outcome Experiment (Treatment vs Holdout)
    cur.execute("SELECT COUNT(*) FROM outcome_experiments")
    if cur.fetchone()[0] == 0:
        cur.execute("""
        INSERT OR REPLACE INTO outcome_experiments (
            experiment_id, campaign_id, merchant_id, experiment_name, time_window_days,
            treatment_count, holdout_count, treatment_conversions, holdout_conversions,
            treatment_conversion_rate, holdout_conversion_rate, conversion_lift_pts,
            incremental_orders, incremental_revenue_inr, incremental_gross_profit_inr,
            campaign_expenditure_inr, net_incremental_profit_inr, incremental_roi_multiple,
            causal_confidence_score, outcome_status, disclaimer
        ) VALUES (
            'EXP-DEMO-001', 'CAMP-REC-1042', 'MERCH-001', 'Weekend Lunch Rush Recovery: Treatment vs Holdout',
            7, 43, 7, 10, 0, 23.3, 0.0, 23.3, 8, 20900.0, 8420.0, 133.30, 8286.70, 62.16, 0.88,
            'SIMULATED_DEMO',
            'SIMULATED OUTCOME: Randomized holdout comparison simulates 85% treatment / 15% holdout. True causal impact requires merchant-wide field experimentation.'
        )
        """)

    conn.commit()

def _seed_phase9_data(conn):
    """Seeds Phase 9 Hussain Fashion Store (MERCH-002), Johari Bazaar participating merchants, demand signals, and opportunity match."""
    cur = conn.cursor()
    now_utc = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc)

    # 1. Seed Merchant MERCH-002 (Hussain Fashion Store)
    cur.execute("SELECT COUNT(*) FROM merchants WHERE id = 'MERCH-002'")
    if cur.fetchone()[0] == 0:
        cur.execute("""
        INSERT OR REPLACE INTO merchants (
            id, store_name, owner_name, email, phone, city, soundbox_device_id, soundbox_status, currency
        ) VALUES (
            'MERCH-002', 'Hussain Fashion Store', 'Zubair Hussain', 'zubair@hussainfashion.in',
            '+91 98290-11234', 'Jaipur', 'SBOX-JP-8891', 'ONLINE', 'INR'
        )
        """)

    # 2. Seed Products for MERCH-002
    hfs_products = [
        ("PROD-HFS-001", "MERCH-002", "SKU-HFS-001", "Handcrafted Chikankari Kurta Set", "Festive Ethnic Wear", 1750.0),
        ("PROD-HFS-002", "MERCH-002", "SKU-HFS-002", "Surplus Bandhani Pure Silk Dupattas", "Ethnic Accessories", 890.0),
        ("PROD-HFS-003", "MERCH-002", "SKU-HFS-003", "Banarasi Brocade Festive Sherwani", "Wedding & Festive Wear", 5500.0),
        ("PROD-HFS-004", "MERCH-002", "SKU-HFS-004", "Jaipuri Printed Cotton Anarkali", "Casual & Festive Wear", 999.0),
        ("PROD-HFS-005", "MERCH-002", "SKU-HFS-005", "Embroidered Velvet Festive Shawl", "Winter Ethnic Wear", 1650.0),
        ("PROD-HFS-006", "MERCH-002", "SKU-HFS-006", "Zari Work Georgette Saree", "Ethnic Sarees", 2450.0),
        ("PROD-HFS-007", "MERCH-002", "SKU-HFS-007", "Gota Patti Festive Kurti", "Festive Ethnic Wear", 799.0),
        ("PROD-HFS-008", "MERCH-002", "SKU-HFS-008", "Handblock Indigo Dabu Stole", "Ethnic Accessories", 450.0)
    ]
    for p in hfs_products:
        cur.execute("""
        INSERT OR REPLACE INTO products (
            product_id, merchant_id, sku, name, category, unit_price
        ) VALUES (?, ?, ?, ?, ?, ?)
        """, p)

    # 3. Seed Inventory for MERCH-002 in merchant_inventory
    hfs_inventory = [
        ("INV-HFS-001", "MERCH-002", "PROD-HFS-001", "Handcrafted Chikankari Kurta Set", "Festive Ethnic Wear", 42, 10, 15, 3, 850.0, 1750.0, 14),
        ("INV-HFS-002", "MERCH-002", "PROD-HFS-002", "Surplus Bandhani Pure Silk Dupattas", "Ethnic Accessories", 74, 15, 20, 4, 420.0, 890.0, 92),
        ("INV-HFS-003", "MERCH-002", "PROD-HFS-003", "Banarasi Brocade Festive Sherwani", "Wedding & Festive Wear", 15, 5, 8, 5, 2400.0, 5500.0, 35),
        ("INV-HFS-004", "MERCH-002", "PROD-HFS-004", "Jaipuri Printed Cotton Anarkali", "Casual & Festive Wear", 55, 12, 18, 3, 480.0, 999.0, 22),
        ("INV-HFS-005", "MERCH-002", "PROD-HFS-005", "Embroidered Velvet Festive Shawl", "Winter Ethnic Wear", 28, 8, 12, 4, 750.0, 1650.0, 48),
        ("INV-HFS-006", "MERCH-002", "PROD-HFS-006", "Zari Work Georgette Saree", "Ethnic Sarees", 32, 10, 15, 3, 1100.0, 2450.0, 19),
        ("INV-HFS-007", "MERCH-002", "PROD-HFS-007", "Gota Patti Festive Kurti", "Festive Ethnic Wear", 60, 15, 20, 2, 380.0, 799.0, 16),
        ("INV-HFS-008", "MERCH-002", "PROD-HFS-008", "Handblock Indigo Dabu Stole", "Ethnic Accessories", 40, 10, 15, 3, 210.0, 450.0, 41)
    ]
    for inv in hfs_inventory:
        cur.execute("""
        INSERT OR REPLACE INTO merchant_inventory (
            inventory_id, merchant_id, product_id, product_name, category,
            current_stock_units, min_safety_stock, reorder_point, lead_time_days,
            unit_cost_inr, unit_selling_price_inr, stock_age_days, last_restocked_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (*inv, (today - timedelta(days=inv[11])).strftime("%Y-%m-%d")))

    # 4. Seed Guardrails for MERCH-002
    hfs_guardrails = [
        ("RULE-HFS-01", "MERCH-002", "MAX_CAMPAIGN_BUDGET_INR", "Maximum Campaign Budget", 2500.0, "INR", "Campaigns cannot exceed ₹2,500 total marketing spend", "HARD_BLOCK"),
        ("RULE-HFS-02", "MERCH-002", "MAX_DISCOUNT_PERCENT", "Maximum Promotional Discount", 10.0, "PERCENT", "Promotional discounts cannot exceed 10.0%", "HARD_BLOCK"),
        ("RULE-HFS-03", "MERCH-002", "MIN_GROSS_MARGIN_PERCENT", "Minimum Product Gross Margin Floor", 25.0, "PERCENT", "Discounts cannot reduce gross product margin below 25.0%", "HARD_BLOCK"),
        ("RULE-HFS-04", "MERCH-002", "INVENTORY_SAFETY_STOCK_DAYS", "Minimum Stock Days for Promotion", 5.0, "DAYS", "Cannot promote products with fewer than 5 days of inventory on hand", "HARD_BLOCK"),
        ("RULE-HFS-05", "MERCH-002", "CUSTOMER_FREQUENCY_CAP_PER_MONTH", "Max Customer Contact Frequency", 2.0, "MESSAGES", "No single customer can receive more than 2 promotional messages in a calendar month", "HARD_BLOCK"),
        ("RULE-HFS-06", "MERCH-002", "MANDATORY_HUMAN_APPROVAL", "Human Approval Gate Enforcement", 1.0, "BOOLEAN", "Customer-facing promotional messages strictly require merchant owner sign-off", "HARD_BLOCK")
    ]
    for g in hfs_guardrails:
        cur.execute("""
        INSERT OR REPLACE INTO merchant_guardrails (
            rule_id, merchant_id, rule_code, rule_name, parameter_value, unit, description, enforcement_level, is_active
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, g)

    # 5. Seed Customers for MERCH-002
    hfs_customers = [
        ("CUST-HFS-001", "MERCH-002", "Pinky Sharma", "pinky.s@gmail.com", "Sharma Household", "+91 98290-33441", "2026-10-05", 2800.0, 14500.0, "Chikankari Kurtas", "2026-10-18", "CONVERTED", 0.0, "hi", 0),
        ("CUST-HFS-002", "MERCH-002", "Rehana Begum", "rehana.b@yahoo.co.in", "Begum Textiles", "+91 98291-55662", "2026-09-28", 4500.0, 22000.0, "Silk Dupattas & Kurtis", "2026-10-12", "CONVERTED", 0.0, "hi", 0),
        ("CUST-HFS-003", "MERCH-002", "Sunita Agarwal", "sunita.agarwal@outlook.com", "Agarwal Jewellers Family", "+91 98292-77883", "2026-10-10", 3500.0, 18200.0, "Festive Ethnic Sets", "2026-10-20", "CONVERTED", 0.0, "en", 0),
        ("CUST-HFS-004", "MERCH-002", "Pooja Rathore", "pooja.rathore@jaipurarts.in", "Rathore Heritage", "+91 98293-99004", "2026-09-15", 1950.0, 9400.0, "Bandhani Dupattas", "2026-10-02", "CONVERTED", 0.0, "hi", 0),
        ("CUST-HFS-005", "MERCH-002", "Meenakshi Joshi", "meenakshi.j@gmail.com", "Joshi Residency", "+91 98294-11225", "2026-10-02", 5200.0, 28500.0, "Zari Sarees & Kurtas", "2026-10-15", "CONVERTED", 0.0, "hi", 0),
        ("CUST-HFS-006", "MERCH-002", "Kavita Singhal", "kavita.singhal@rediffmail.com", "Singhal Exports", "+91 98295-33446", "2026-09-20", 2400.0, 11800.0, "Anarkali Sets", "2026-10-08", "CONVERTED", 0.0, "en", 0),
        ("CUST-HFS-007", "MERCH-002", "Anjali Pareek", "anjali.pareek@gmail.com", "Pareek Boutique", "+91 98296-55667", "2026-10-08", 3800.0, 16900.0, "Chikankari & Bandhani", "2026-10-22", "CONVERTED", 0.0, "hi", 0),
        ("CUST-HFS-008", "MERCH-002", "Deepika Shekhawat", "deepika.s@jaipurroyal.org", "Shekhawat Palace", "+91 98297-77888", "2026-09-12", 6800.0, 36000.0, "Festive Sherwanis & Sarees", "2026-10-01", "CONVERTED", 0.0, "en", 0),
        ("CUST-HFS-009", "MERCH-002", "Farhana Qureshi", "farhana.q@gmail.com", "Qureshi Design Studio", "+91 98298-99009", "2026-10-01", 2100.0, 8900.0, "Silk Dupattas", "2026-10-14", "CONVERTED", 0.0, "hi", 0),
        ("CUST-HFS-010", "MERCH-002", "Neelam Khandelwal", "neelam.k@khandelwalgems.com", "Khandelwal Gem Store", "+91 98299-11220", "2026-09-25", 4100.0, 21500.0, "Festive Kurtas", "2026-10-11", "CONVERTED", 0.0, "hi", 0)
    ]
    for c in hfs_customers:
        cur.execute("""
        INSERT OR REPLACE INTO customers (
            customer_id, merchant_id, customer_name, email, company, phone,
            last_purchase_date, last_purchase_value, lifetime_value,
            interested_product, last_interaction_date, quotation_status,
            quotation_value, preferred_language, is_unsubscribed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, c)

    # 6. Seed Bazaar Participating Merchants (14 merchants in Johari Bazaar cluster)
    bazaar_merchants = [
        # 7 Clothing & Apparel (Cohort size = 7 >= 5 -> PUBLISHED)
        ("MERCH-002", "Hussain Fashion Store", "Festive Ethnic Apparel", "Kurtas & Silk Dupattas", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2025-01-10", "TIER_2_GROWING", 4.9),
        ("MERCH-JP-003", "Meena Bazaar Jaipur", "Festive Ethnic Apparel", "Wedding & Bridal Wear", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2024-11-05", "TIER_1_ESTABLISHED", 4.8),
        ("MERCH-JP-004", "Royal Rajasthani Silks", "Festive Ethnic Apparel", "Pure Silk Sarees", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2025-02-14", "TIER_2_GROWING", 4.7),
        ("MERCH-JP-005", "Jaipur Kurti Emporium", "Festive Ethnic Apparel", "Handcrafted Kurtis", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2025-03-01", "TIER_2_GROWING", 4.6),
        ("MERCH-JP-006", "Gulab Chand Prints", "Festive Ethnic Apparel", "Jaipuri Block Prints", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2024-09-12", "TIER_1_ESTABLISHED", 4.8),
        ("MERCH-JP-007", "Kuber Ethnic Fab", "Festive Ethnic Apparel", "Mens Ethnic & Sherwanis", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2025-04-20", "TIER_3_EMERGING", 4.5),
        ("MERCH-JP-008", "Zari Mahal", "Festive Ethnic Apparel", "Embroidered Festive Gowns", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2024-12-01", "TIER_2_GROWING", 4.7),
        # 5 Jewellery & Gem (Cohort size = 5 >= 5 -> PUBLISHED)
        ("MERCH-JP-009", "Surana Jewellers", "Jewellery & Gems", "Polki & Kundan", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2024-08-15", "TIER_1_ESTABLISHED", 4.9),
        ("MERCH-JP-010", "Kothari Gems", "Jewellery & Gems", "Emeralds & Gemstones", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2024-10-10", "TIER_1_ESTABLISHED", 4.8),
        ("MERCH-JP-011", "Johari Silver Palace", "Jewellery & Gems", "Sterling Silver Ornaments", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2025-01-25", "TIER_2_GROWING", 4.7),
        ("MERCH-JP-012", "Shri Krishna Polki", "Jewellery & Gems", "Bridal Polki Sets", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2025-03-15", "TIER_2_GROWING", 4.6),
        ("MERCH-JP-013", "Riddhi Siddhi Ornaments", "Jewellery & Gems", "Traditional Jadau", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2025-05-02", "TIER_3_EMERGING", 4.5),
        # 2 Blue Pottery & Handicrafts (Cohort size = 2 < 5 -> PRIVACY SUPPRESSED)
        ("MERCH-JP-014", "Jaipur Blue Art", "Ceramics & Handicrafts", "Glazed Blue Pottery", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2025-02-18", "TIER_3_EMERGING", 4.6),
        ("MERCH-JP-015", "Royal Handicrafts", "Ceramics & Handicrafts", "Marble & Brass Crafts", "NEIGHBOURHOOD-JP-01", "Johari Bazaar, Jaipur", "Jaipur", 1, "2025-04-11", "TIER_3_EMERGING", 4.4)
    ]
    for bm in bazaar_merchants:
        cur.execute("""
        INSERT OR REPLACE INTO bazaar_participating_merchants (
            merchant_id, store_name, category, sub_category, neighbourhood_id,
            neighbourhood_name, city, consent_opt_in, participating_since,
            annual_turnover_tier, reputation_score, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (*bm, now_utc))

    # 7. Seed Bazaar Aggregated Demand Signals
    bazaar_signals = [
        (
            "SIG-JP-001", "NEIGHBOURHOOD-JP-01", "Festive Ethnic Apparel", "Kurtas & Silk Dupattas",
            "Festive Ethnic Kurtas & Silk Dupattas Surge", "SURGE", 38.5, 7, 5, 0, None, 0.94,
            "Past 7 Days", 1,
            "Aggregated from 7 participating apparel merchants in Johari Bazaar cluster. Cohort k=7 exceeds privacy threshold k>=5. No individual merchant sales or customer PII exposed."
        ),
        (
            "SIG-JP-002", "NEIGHBOURHOOD-JP-01", "Ceramics & Handicrafts", "Glazed Blue Pottery",
            "Traditional Glazed Blue Pottery Surge", "SURGE", 24.0, 2, 5, 1,
            "Small Cell Suppression: Cohort size (2 merchants) is below minimum privacy threshold k=5. Aggregation blocked to prevent reverse-engineering individual store sales.",
            0.88, "Past 7 Days", 1,
            "Signal suppressed under k-anonymity privacy rule (k=2 < 5). Raw counts withheld."
        ),
        (
            "SIG-JP-003", "NEIGHBOURHOOD-JP-01", "Jewellery & Gems", "Polki & Kundan",
            "Festive Bridal Polki & Kundan Ornaments Surge", "GROWING", 19.2, 5, 5, 0, None, 0.91,
            "Past 7 Days", 1,
            "Aggregated from 5 participating jewellery merchants in Johari Bazaar cluster. Cohort k=5 meets privacy threshold k>=5. No individual store sales or ticket sizes exposed."
        )
    ]
    for bs in bazaar_signals:
        cur.execute("""
        INSERT OR REPLACE INTO bazaar_demand_signals (
            signal_id, neighbourhood_id, product_category, sub_category,
            signal_name, demand_trend, growth_rate_pct, reporting_merchants_count,
            min_cohort_threshold, privacy_suppressed, suppression_reason, confidence_score,
            time_window, is_simulated, provenance_note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (*bs, now_utc))

    # 8. Seed Bazaar Contextual Opportunity Match for Hussain Fashion Store
    opp_matches = [
        (
            "MATCH-HFS-001", "MERCH-002", "SIG-JP-001",
            "Festive Royal Bundle Re-engagement", 94.0, "EXCELLENT",
            json.dumps({
                "product_relevance": 96.0,
                "inventory_depth": 92.0,
                "margin_headroom": 95.0,
                "local_demand_momentum": 93.0,
                "explanation": "High local demand surge (+38.5%) matches fast-selling Chikankari Kurtas (42 units, 51.4% margin) paired with slow-moving Silk Dupattas (74 units, 92 days aging, ₹31,080 trapped capital)."
            }),
            json.dumps([
                {"product_id": "PROD-HFS-001", "product_name": "Handcrafted Chikankari Kurta Set", "current_stock": 42, "unit_cost_inr": 850.0, "selling_price_inr": 1750.0, "margin_pct": 51.4},
                {"product_id": "PROD-HFS-002", "product_name": "Surplus Bandhani Pure Silk Dupattas", "current_stock": 74, "unit_cost_inr": 420.0, "selling_price_inr": 890.0, "margin_pct": 52.8, "stock_age_days": 92, "trapped_capital_inr": 31080.0}
            ]),
            json.dumps({
                "strategy_key": "BALANCED",
                "name": "Festive Royal Bundle (Recommended)",
                "description": "Pair trending Chikankari Kurta with slow-moving Silk Dupatta at ₹2,299 (8% bundle savings). Unlocks ₹31k trapped capital while preserving 44.8% gross margin.",
                "bundle_price_inr": 2299.0,
                "discount_pct": 8.0,
                "marketing_budget_inr": 450.0,
                "target_audience_count": 20
            }),
            json.dumps({
                "CONSERVATIVE": {
                    "strategy_key": "CONSERVATIVE",
                    "name": "VIP Festive Preview",
                    "description": "Exclusive preview of new festive arrivals for top 10 repeat customers with zero discounting.",
                    "discount_pct": 0.0,
                    "target_audience": 10,
                    "projected_orders": 6,
                    "projected_revenue_inr": 10500.0,
                    "projected_gross_profit_inr": 5400.0,
                    "projected_margin_pct": 51.4,
                    "marketing_cost_inr": 150.0,
                    "net_contribution_inr": 5250.0,
                    "roi_multiple": 35.0,
                    "guardrails_passed": True,
                    "violations": []
                },
                "BALANCED": {
                    "strategy_key": "BALANCED",
                    "name": "Festive Royal Bundle (Recommended)",
                    "description": "Pair trending Chikankari Kurta with slow-moving Silk Dupatta at ₹2,299 (8% bundle discount). Releases ₹31k trapped capital.",
                    "discount_pct": 8.0,
                    "target_audience": 20,
                    "projected_orders": 14,
                    "projected_revenue_inr": 32186.0,
                    "projected_gross_profit_inr": 14406.0,
                    "projected_margin_pct": 44.8,
                    "marketing_cost_inr": 450.0,
                    "net_contribution_inr": 13956.0,
                    "roi_multiple": 31.0,
                    "guardrails_passed": True,
                    "violations": []
                },
                "AGGRESSIVE": {
                    "strategy_key": "AGGRESSIVE",
                    "name": "Storewide Clearance Sprint",
                    "description": "Aggressive 18% storewide discount blast across 30 contacts. Breaches merchant guardrail RULE-HFS-02 (max 10% discount).",
                    "discount_pct": 18.0,
                    "target_audience": 30,
                    "projected_orders": 20,
                    "projected_revenue_inr": 43296.0,
                    "projected_gross_profit_inr": 14696.0,
                    "projected_margin_pct": 33.9,
                    "marketing_cost_inr": 900.0,
                    "net_contribution_inr": 13796.0,
                    "roi_multiple": 15.3,
                    "guardrails_passed": False,
                    "violations": [
                        "RULE-HFS-02: Discount 18.0% exceeds maximum permitted discount of 10.0%",
                        "RULE-HFS-04: Inventory velocity risk on fast-moving Kurta sets"
                    ]
                }
            }),
            32186.0, 14406.0, "LOW", "AVAILABLE"
        )
    ]
    for om in opp_matches:
        cur.execute("""
        INSERT OR REPLACE INTO bazaar_opportunity_matches (
            match_id, merchant_id, signal_id, opportunity_name,
            matching_score, relevance_status, score_breakdown_json,
            compatible_products_json, recommended_strategy_json,
            decision_twin_scenarios_json, estimated_revenue_inr,
            estimated_gross_profit_inr, stockout_risk, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (*om, now_utc))

    conn.commit()

def reset_database():
    """Drops and re-initializes clean database with fresh seed records."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = OFF")
    tables = [
        "merchants", "users", "organization_members", "customers", "products", "orders", "order_items",
        "quotations", "customer_interactions", "opportunities", "recovery_campaigns",
        "campaign_customers", "ai_agents", "agent_executions", "agent_execution_logs",
        "customer_research", "recovery_strategies", "approvals", "executions",
        "followup_schedules", "customer_replies", "verified_purchases",
        "integration_connections", "audit_trail", "organization_policies", "workflows", "roi_metrics",
        "tasks", "task_state_history",
        "campaign_drafts", "campaign_recipient_statuses", "campaign_activity_timeline",
        "verifications", "task_escalations",
        "merchant_inventory", "merchant_expenses", "merchant_settlements", "merchant_guardrails",
        "decision_simulations", "outcome_experiments", "business_opportunities",
        "voice_sessions", "voice_interactions", "bazaar_participating_merchants",
        "bazaar_demand_signals", "bazaar_opportunity_matches"
    ]
    for t in tables:
        cur.execute(f"DROP TABLE IF EXISTS {t}")
    cur.execute("PRAGMA foreign_keys = ON")
    
    for col, col_def in [
        ("task_id", "TEXT"),
        ("campaign_id", "TEXT"),
        ("merchant_id", "TEXT DEFAULT 'MERCH-001'"),
        ("approver_id", "TEXT DEFAULT 'USER-001'"),
        ("message_version", "INTEGER DEFAULT 1"),
        ("content_hash", "TEXT"),
        ("reason_or_comments", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'VALID'")
    ]:
        try:
            cur.execute(f"ALTER TABLE approvals ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    for col, col_def in [
        ("event_id", "TEXT"),
        ("merchant_id", "TEXT DEFAULT 'MERCH-001'"),
        ("task_id", "TEXT"),
        ("actor_id", "TEXT DEFAULT 'system'"),
        ("resource", "TEXT"),
        ("previous_state", "TEXT"),
        ("new_state", "TEXT"),
        ("is_simulated", "BOOLEAN DEFAULT 0")
    ]:
        try:
            cur.execute(f"ALTER TABLE audit_trail ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    # Phase 5 Safe Column Migrations for Approvals & Audit Trail
    for col, col_def in [
        ("task_id", "TEXT"),
        ("campaign_id", "TEXT"),
        ("merchant_id", "TEXT DEFAULT 'MERCH-001'"),
        ("approver_id", "TEXT DEFAULT 'USER-001'"),
        ("message_version", "INTEGER DEFAULT 1"),
        ("content_hash", "TEXT"),
        ("reason_or_comments", "TEXT"),
        ("approval_status", "TEXT DEFAULT 'VALID'")
    ]:
        try:
            cur.execute(f"ALTER TABLE approvals ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    for col, col_def in [
        ("event_id", "TEXT"),
        ("merchant_id", "TEXT DEFAULT 'MERCH-001'"),
        ("task_id", "TEXT"),
        ("actor_id", "TEXT DEFAULT 'system'"),
        ("resource", "TEXT"),
        ("previous_state", "TEXT"),
        ("new_state", "TEXT"),
        ("is_simulated", "BOOLEAN DEFAULT 0")
    ]:
        try:
            cur.execute(f"ALTER TABLE audit_trail ADD COLUMN {col} {col_def}")
        except Exception:
            pass

    conn.commit()
    conn.close()
    init_db()

def generate_sample_csv_text() -> str:
    """Returns sample CSV format matching required fields."""
    headers = [
        "customer_id", "customer_name", "email", "company", "phone",
        "last_purchase_date", "last_purchase_value", "lifetime_value",
        "interested_product", "last_interaction_date", "quotation_status",
        "quotation_value", "preferred_language"
    ]
    rows = [
        ["CUST-2001", "Arun Kumar", "arun.kumar@biotechlabs.in", "BioTech Research Labs", "+91 98711-23091", "2026-08-19", "85000", "245000", "Laboratory reactor accessories", "2026-09-15", "UNANSWERED", "65000", "en"],
        ["CUST-2002", "Ananya Roy", "ananya.roy@delhicatering.com", "Delhi Fine Confectionery", "+91 98102-44120", "2026-10-02", "42000", "186000", "Festive gourmet sweet gift hampers", "2026-10-14", "UNANSWERED", "52000", "en"],
        ["CUST-2003", "Rajesh Sharma", "rajesh.sharma@apexinfra.org", "Apex Engineering Infra", "+91 98230-11980", "2026-07-10", "112000", "390000", "Industrial boiler spare components", "2026-08-04", "SENT", "94000", "hi"],
        ["CUST-2004", "Priya Venkatesh", "priya.v@chennaimetalworks.com", "Chennai Metalworks", "+91 94440-88219", "2026-09-28", "34000", "98000", "Custom CNC fittings", "2026-10-18", "NONE", "0", "ta"],
        ["CUST-2005", "Vikram Patel", "vpatel@gujaratchemicals.co.in", "Gujarat Polymers", "+91 98250-77341", "2026-06-15", "145000", "480000", "Polymer drums & valves", "2026-07-20", "EXPIRED", "120000", "gu"]
    ]
    lines = [",".join(headers)]
    for r in rows:
        lines.append(",".join(r))
    return "\n".join(lines)
