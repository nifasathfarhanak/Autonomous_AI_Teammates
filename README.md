# Paytm AI ActionMate: Autonomous AI Teammates for Merchant Operations
> **"From conversations to completed actions."**  
> **Track 3 — Autonomous AI Teammates | Paytm AI Hackathon**  
> **Team SingaSpark:** Thanya R G · Nagarajan R · Nifasath Farhana K

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Zero External Pip Dependencies](https://img.shields.io/badge/dependencies-Standard%20Library%20Only-brightgreen.svg)](#zero-external-pip-dependencies)
[![Test Suite](https://img.shields.io/badge/tests-87%20passed%20%2F%20100%25-success.svg)](#automated-testing--verification)
[![Verification Engine](https://img.shields.io/badge/verification-7--Point%20Closed--Loop-blueviolet.svg)](#7-point-verification-engine)
[![Security Policy](https://img.shields.io/badge/governance-3--Tier%20Risk%20Policy-orange.svg)](#action-risk-policy--human-approval)

---

## 🎯 Executive Product Overview

Small and medium merchants across India face acute business operational challenges:
1. **Sales Drop Blindspots:** Daily footfall and repeat transaction drops often go unnoticed until working capital is strained.
2. **Analysis Paralysis:** Merchants lack analytical tooling to distinguish between normal weekly fluctuation and severe customer dormancy.
3. **Execution Friction:** Designing, translating, segmenting, and launching promotional campaigns across WhatsApp, SMS, and Paytm Soundbox takes days of manual effort.
4. **Chatbot Frustration:** Conventional AI chatbots only output conversational text without verifying inventory, checking customer contact validity, enforcing budgets, or executing verified actions.

**Paytm AI ActionMate** is an enterprise autonomous AI teammate built specifically for Paytm merchants. ActionMate transforms natural-language merchant conversations into verified, multi-step business workflows with strict human governance.

### The Signature Merchant Prompt:
> *"My sales have dropped this week. Help me bring customers back."*

ActionMate does not simply respond with conversational suggestions. It autonomously:
1. **Understands Intent:** Decodes the request into a structured re-engagement workflow.
2. **Retrieves Business Context:** Pulls store profile, catalog, and device telemetry (Paytm Soundbox 4G).
3. **Analyzes Sales Trends:** Detects the ₹112,000 (-27.2%) sales drop from Last Week (₹412k) to This Week (₹300k).
4. **Diagnoses Repeat Decline:** Flags repeat-purchase collapse from 41% down to 24% (-17 percentage points).
5. **Formulates Campaign:** Designs a targeted reactivation sprint with code `RET50` (₹50 discount on orders > ₹249).
6. **Filters Audience:** Evaluates 46 candidate customers, deterministically suppressing DND opt-outs and invalid contacts to isolate 43 eligible recipients.
7. **Personalizes Copy:** Drafts native English, Indic Hindi, and Soundbox Audio voice scripts.
8. **Enforces Governance:** Blocks Category C financial actions (refunds/bank changes) and mandates merchant HMAC approval for Category B outbound messages.
9. **Executes & Logs:** Dispatches simulated multi-channel promotions with recipient logging and idempotency keys.
10. **Verifies Outcomes:** Runs a 7-point cryptographic verification engine before declaring completion.

---

## 🏗️ Architecture & Component Topology

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Paytm AI ActionMate UI                                │
│          React + TypeScript + Tailwind CSS (Fintech Navy/Cyan/Emerald)          │
│   Overview | AI Assistant | Sales | Customers | Campaigns | Approvals | KPIs   │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │ REST / HTTP (port 8000)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    Enterprise Multi-Threaded HTTP Server                        │
│                           (backend/app/server.py)                               │
└──────┬───────────────────────────────┬───────────────────────────────────┬──────┘
       │                               │                                   │
       ▼                               ▼                                   ▼
┌──────────────────────┐   ┌────────────────────────┐   ┌─────────────────────────┐
│ Orchestrator Engine  │   │ Sales Intelligence     │   │ Campaign Engine         │
│ • Intent Analyzer    │   │ • calculate_summary()  │   │ • recommend_campaign()  │
│ • Reasoning Engine   │   │ • detect_sales_drop()  │   │ • evaluate_audience()   │
│ • 10-Step Planner    │   │ • repeat_analysis()    │   │ • render_personalized() │
│ • 14-State FSM       │   │ • customer_segments()  │   │ • simulated_adapter()   │
└──────┬───────────────┘   └───────────┬────────────┘   └──────────┬──────────────┘
       │                               │                           │
       ▼                               ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      Safety, Governance & Verification Layer                     │
│  • Action Risk Policy (Cat A: Auto, Cat B: Approval Req, Cat C: Blocked)        │
│  • Cryptographic HMAC-SHA256 Approvals & Anti-Tamper Copy Verification          │
│  • 7-Point Closed-Loop Verification Engine (VerificationService)                │
│  • Safe Idempotent Retries & Human Escalation (FailureRecoveryService)          │
│  • Tamper-Evident SHA-256 Chained Audit Ledger (AuditService)                   │
│  • Dynamic Operational KPI Framework (KPIService)                               │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │ WAL Mode & Foreign Keys
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       SQLite Master Persistence (34 Tables)                     │
│    merchants, orders, order_items, customers, tasks, campaign_drafts,           │
│    campaign_recipient_statuses, approvals, verifications, audit_trail, etc.     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Action Risk Policy & Human Approval

ActionMate operates under a strict **3-Tier Action Risk Policy** to guarantee safe autonomous behavior:

| Category | Risk Level | Description & Examples | Execution Policy |
| :--- | :--- | :--- | :--- |
| **Category A** | **Low / Read-Only** | Sales lookups, analytics calculation, repeat trend assessment, customer segmentation, draft copy preparation. | **Fully Autonomous:** Executed automatically by AI agents without human intervention. |
| **Category B** | **Medium / Outbound** | Customer-facing communications, promotional campaign dispatch via SMS/WhatsApp/Soundbox, discount code activation. | **Human Approval Mandatory:** Strictly requires merchant owner sign-off with HMAC-SHA256 signature and budget ceiling. |
| **Category C** | **High / Financial** | Customer refunds, bank account modification, payout destination changes, merchant credit lines. | **Strictly Blocked for AI:** Permanently prohibited from AI execution (`FINANCIAL_ACTION_BLOCKED` HTTP 403). Requires manual merchant portal action. |

### Cryptographic Security & Anti-Tamper Enforcements
1. **HMAC-SHA256 Approval Signatures:** Every approval generates a verifiable digital signature binding the approver ID, timestamp, and budget ceiling.
2. **Zero Content-Drift Policy:** When a campaign copy is approved, a SHA-256 hash of the exact message content is stamped. If any copy is modified post-approval, prior approval is **automatically invalidated** (`CONTENT_DRIFT_DETECTED`), preventing unauthorized message alterations.
3. **Chained Audit Ledger:** All actions, tool calls, and state transitions are appended to a tamper-evident blockchain-style ledger where each block hashes the prior block (`current_hash = SHA256(prev_hash + payload)`). Any database mutation breaks chain verification.

---

## 🔍 7-Point Verification Engine

ActionMate adheres to a foundational rule: **The system never displays "Done" simply because an AI model generated a response.**

Before a task transition to `COMPLETED`, the `VerificationService` evaluates 7 strict invariants:

1. **`check_approval`:** Confirms valid human approval exists with an active `APPROVED` status.
2. **`check_adapter_acceptance`:** Verifies the simulated execution adapter formally accepted the dispatch request.
3. **`check_execution_record`:** Confirms execution timestamp, execution ID, and outcome status are persisted.
4. **`check_execution_id`:** Verifies execution ID format matches `EXEC-SIM-*` and is non-empty.
5. **`check_recipient_processing`:** Confirms recipient records were generated matching eligible audience count.
6. **`check_statuses_recorded`:** Verifies every processed recipient has a deterministic status (`DELIVERED`, `DND_SUPPRESSED`, `FAILED`).
7. **`check_workflow_match`:** Cross-checks that executed campaign parameters match the approved task configuration.

If any check fails, ActionMate flags the task as `PARTIALLY_VERIFIED`, `REQUIRES_HUMAN`, or `FAILED` and engages the `FailureRecoveryService`.

---

## 📊 Operational KPIs & Reporting

ActionMate provides a dynamic 6-KPI executive analytics framework accessible via `/app/analytics`:

1. **Task Completion Rate:** Verifiable tasks completed vs total initiated (Target: > 90%).
2. **Average Resolution Time:** End-to-end duration from prompt to verified completion (Target: < 5.0 min).
3. **Human Escalation Rate:** Percentage of workflows requiring human review (Target: < 15%).
4. **Approval Compliance:** Zero unauthorized executions (Target: 100.0%).
5. **Cost per Completed Task:** Illustrative operational compute & SMS cost (Target: < ₹5.00).
6. **Campaign Engagement:** Simulated message delivery and customer response rates.

Merchants can filter KPIs by **Time Window (7D, 30D, 90D, All)** and **Task Status**, compare current performance against prior period benchmarks, and export an **Executive Task Audit Report** formatted in GitHub Flavored Markdown with one click.

---

## 🚀 Getting Started & Demo Walkthrough

### Zero External Pip Dependencies
ActionMate is built exclusively with Python's standard library (`sqlite3`, `http.server`, `json`, `hashlib`, `hmac`, `urllib`). No external pip dependencies, virtual environments, or heavy packages are required.

### 1. Start the Backend Server
```bash
python3 backend/app/server.py
```
*The server initializes the 34-table SQLite database, seeds realistic demo data for merchant `MERCH-001`, and starts on `http://127.0.0.1:8000`.*

### 2. Access the Merchant Dashboard
Open your browser and navigate to:
```
http://127.0.0.1:8000/app/overview
```

### 3. Demo Walkthrough: 20-Step Journey
1. **Open AI Assistant (`/app/assistant`):** Select or type: *"My sales have dropped this week. Help me bring customers back."*
2. **View AI Plan & Reasoning:** Observe the 10-step plan, intent classification, and sales analysis showing the -27.2% decline.
3. **Review Sales Dashboard (`/app/sales`):** View the daily comparison chart (Last Week: ₹412k vs This Week: ₹300k) and repeat-purchase trend (41% → 24%).
4. **Inspect Campaign Draft (`/app/campaigns`):** Review the recommended campaign, Indic multilingual copy (English, Hindi, Soundbox Voice), offer `RET50`, and audience segmentation (43 eligible, 3 DND/invalid excluded).
5. **Approve Campaign (`/app/approvals`):** Review campaign parameters and click **"Approve & Execute Campaign"** to generate the HMAC-SHA256 signature.
6. **Watch Real-Time Verification:** Watch the execution adapter dispatch simulated messages, record recipient logs, and execute the 7-point verification audit.
7. **Inspect Audit Ledger (`/app/activity`):** Verify the cryptographic chained ledger blocks with SHA-256 hashes.
8. **View KPIs & Export Report (`/app/analytics`):** View updated KPI cards, target benchmark comparisons, and click **"Export Audit Report (.md)"** to download the signed executive summary.
9. **One-Click Safe Demo Reset:** Click **"Reset Demo Environment"** in the top navigation bar or trigger `POST /api/demo/reset` to reset the demo workflow cleanly without corrupting the master database.

---

## 🧪 Automated Testing & Verification

ActionMate includes a comprehensive 87-test automated verification suite covering unit logic, integration journeys, security constraints, and boundary edge cases:

```bash
python3 -m unittest discover backend/tests -v
```

### Test Coverage Highlights:
- **`test_phase7_e2e_and_errors.py` (16 tests):** Complete 20-step end-to-end journey and the 15-scenario error/boundary matrix.
- **`test_verification_and_kpis_phase6.py` (12 tests):** 7-point verification engine, partial verification, retry limits, 6 KPIs, and markdown reporting.
- **`test_safety_and_governance_phase5.py` (10 tests):** 3-tier risk policy, Category C blocked tools, HMAC authorization, copy drift invalidation, and chained ledger.
- **`test_campaign_execution_phase4.py` (10 tests):** Audience targeting, DND/invalid exclusions, Indic multilingual rendering, tool registry, and idempotency.
- **`test_orchestrator_phase3.py` (8 tests):** Intent analyzer, reasoning engine, 10-step planner, and 14-state task FSM.
- **`test_sales_intelligence_phase2.py` (9 tests):** Fictional merchant data, 4-week sales trends, repeat purchase drops, and database persistence.
- **`test_actionmate_phase1.py` (5 tests):** Phase 1 application foundation and UI endpoints.
- **`test_enterprise_suite.py` & `test_workflow.py` (17 tests):** DealPilot AI agent workflows, CSV ingestion, scoring model, and revenue attribution.

**Result: 87 passed / 0 failed / 100% pass rate.**

---

## 🗺️ Product Roadmap: Prototype vs. Pilot vs. Scale

| Dimension | Phase 1–7 Hackathon Prototype (Current) | Merchant Pilot (Next 90 Days) | Production Scale (12–18 Months) |
| :--- | :--- | :--- | :--- |
| **Merchant Environment** | Single demo merchant (`MERCH-001`, Jaipur), realistic seeded catalogs and orders. | 500 invited retail merchants across Delhi-NCR and Jaipur. | Multi-tenant across 10M+ Paytm merchants nationwide. |
| **Data Storage** | SQLite with WAL mode, foreign keys, and 34 normalized tables. | PostgreSQL with TimescaleDB for time-series telemetry and Redis caching. | Distributed CockroachDB / Cloud Spanner with sharded tenant databases. |
| **AI Reasoning Engine** | Deterministic rule engine + mock Sarvam LLM provider with fallback. | Hybrid Sarvam-105B Indic LLM + specialized fine-tuned merchant reasoning models. | Sovereign multi-modal agent clusters with low-latency edge inference on Soundbox devices. |
| **Action Execution** | Simulated multi-channel execution adapter with delivery latency emulation. | Live Paytm SMS Gateway, WhatsApp Business Cloud API, and Soundbox 4G push notifications. | Real-time omnichannel orchestration engine with automated carrier fallback and dynamic rate-limiting. |
| **Payment & Financial Ops** | Category C financial operations strictly blocked (`FINANCIAL_ACTION_BLOCKED`). | Category C remains human-only; read-only settlement reconciliation. | Automated dispute resolution with multi-party merchant authorization workflows. |
| **Governance & Audit** | Local SHA-256 chained audit ledger and HMAC-SHA256 signatures. | Cryptographically signed ledger replicated to merchant-accessible cloud storage. | Immutable zero-knowledge audit trail with regulatory compliance reporting for RBI guidelines. |

---

## 👥 Hackathon Team SingaSpark

- **Thanya R G** — AI Strategy & Product Design
- **Nagarajan R** — Full-Stack Architecture & Verification Systems
- **Nifasath Farhana K** — Autonomous Agents & Merchant Experience

*Built with passion for Track 3 — Autonomous AI Teammates at Paytm AI Hackathon.*
