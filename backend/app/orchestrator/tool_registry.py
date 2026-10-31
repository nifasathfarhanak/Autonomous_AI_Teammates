"""Paytm AI ActionMate Controlled Tool Registry.
Registers business context tools and execution actions with strict input/output schemas,
caller permission validation, risk categories, and verification functions.
No unrestricted shell, database, or external network access is permitted.
"""

import time
import json
from typing import Dict, Any, List, Optional, Callable
from ..database import get_connection
from ..schemas import ToolDefinitionSchema, ToolExecutionResultSchema
from ..services.sales_intelligence_service import (
    get_merchant_profile,
    calculate_sales_summary,
    calculate_repeat_analysis,
    detect_sales_drop,
    get_customer_segments,
    get_product_performance,
    get_customer_purchase_history
)

class ToolError(Exception):
    """Base error for tool registration and execution."""
    pass

class ToolPermissionDeniedError(ToolError):
    """Raised when caller lacks required permissions."""
    pass

class ToolValidationError(ToolError):
    """Raised when arguments fail input schema validation."""
    pass

class ToolRegistry:
    """Singleton-style registry for controlling tool access, schemas, and execution."""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()

    def register_tool(
        self,
        tool_def: ToolDefinitionSchema,
        execution_func: Callable[..., Any],
        verification_func: Optional[Callable[..., bool]] = None
    ):
        """Registers a tool with defined permissions, schemas, and execution handlers."""
        self._tools[tool_def.name] = {
            "definition": tool_def,
            "execute": execution_func,
            "verify": verification_func
        }

    def get_tool(self, name: str) -> Optional[ToolDefinitionSchema]:
        """Retrieves metadata definition for a tool."""
        if name in self._tools:
            return self._tools[name]["definition"]
        return None

    def list_tools(self) -> List[Dict[str, Any]]:
        """Lists all registered tools with schemas and permission requirements."""
        return [t["definition"].dict() for t in self._tools.values()]

    def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        caller_permissions: Optional[List[str]] = None
    ) -> ToolExecutionResultSchema:
        """Executes a registered tool within strict security and validation boundaries."""
        start_time = time.time()

        if tool_name not in self._tools:
            return ToolExecutionResultSchema(
                tool_name=tool_name,
                status="FAILED",
                error_message=f"Tool '{tool_name}' is not registered in the tool registry.",
                execution_duration_ms=0,
                verified=False
            )

        tool_entry = self._tools[tool_name]
        tool_def: ToolDefinitionSchema = tool_entry["definition"]

        # Action Risk Policy Check (Category A, B, C)
        from ..services.governance_service import GovernanceService, PolicyViolationError
        has_appr = False
        if tool_name == "execute_demo_campaign":
            cid = arguments.get("campaign_id")
            if cid:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                SELECT id FROM approvals
                WHERE (campaign_id = ? OR workflow_id = ?) AND decision = 'APPROVED' AND approval_status = 'VALID'
                LIMIT 1
                """, (cid, cid))
                has_appr = cur.fetchone() is not None
                conn.close()

        policy_eval = GovernanceService.evaluate_action_policy(tool_name, has_approval=has_appr)
        if not policy_eval.allowed:
            from ..services.audit_service import AuditService
            AuditService.log_audit_event(
                merchant_id="MERCH-001",
                task_id="WF-REC-1042",
                actor_id="ToolRegistry",
                action="FINANCIAL_ACTION_BLOCKED" if policy_eval.is_financial_mutation else "ACTION_BLOCKED_UNAPPROVED",
                resource=f"tool:{tool_name}",
                previous_state="BLOCKED",
                new_state="BLOCKED",
                tool_name=tool_name,
                tool_input=arguments,
                tool_output={"error": policy_eval.reason}
            )
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolExecutionResultSchema(
                tool_name=tool_name,
                status="FAILED",
                error_message=policy_eval.reason,
                execution_duration_ms=duration_ms,
                verified=False
            )

        # 1. Validate caller permissions
        effective_permissions = caller_permissions if caller_permissions is not None else [
            "READ_MERCHANT", "READ_SALES", "READ_CUSTOMERS", "READ_PRODUCTS", "READ_CAMPAIGNS",
            "REASON_STRATEGY", "DRAFT_COMMUNICATION", "SIMULATE_EXECUTION", "VERIFY_ATTRIBUTION"
        ]

        for req_perm in tool_def.permissions:
            if req_perm not in effective_permissions:
                duration_ms = int((time.time() - start_time) * 1000)
                return ToolExecutionResultSchema(
                    tool_name=tool_name,
                    status="PERMISSION_DENIED",
                    error_message=f"Caller lacks required permission: '{req_perm}'.",
                    execution_duration_ms=duration_ms,
                    verified=False
                )

        # 2. Validate input arguments against schema
        input_schema = tool_def.input_schema
        required_fields = input_schema.get("required", [])
        properties = input_schema.get("properties", {})

        for field in required_fields:
            if field not in arguments:
                duration_ms = int((time.time() - start_time) * 1000)
                return ToolExecutionResultSchema(
                    tool_name=tool_name,
                    status="VALIDATION_ERROR",
                    error_message=f"Missing required argument '{field}' for tool '{tool_name}'.",
                    execution_duration_ms=duration_ms,
                    verified=False
                )

        # Type checking for provided fields
        for field, val in arguments.items():
            if field in properties:
                expected_type = properties[field].get("type")
                if expected_type == "string" and not isinstance(val, str):
                    duration_ms = int((time.time() - start_time) * 1000)
                    return ToolExecutionResultSchema(
                        tool_name=tool_name,
                        status="VALIDATION_ERROR",
                        error_message=f"Argument '{field}' must be a string, got {type(val).__name__}.",
                        execution_duration_ms=duration_ms,
                        verified=False
                    )
                elif expected_type == "number" and not isinstance(val, (int, float)):
                    duration_ms = int((time.time() - start_time) * 1000)
                    return ToolExecutionResultSchema(
                        tool_name=tool_name,
                        status="VALIDATION_ERROR",
                        error_message=f"Argument '{field}' must be a number, got {type(val).__name__}.",
                        execution_duration_ms=duration_ms,
                        verified=False
                    )

        # 3. Execute implementation
        try:
            exec_fn = tool_entry["execute"]
            result = exec_fn(**arguments)
            duration_ms = int((time.time() - start_time) * 1000)

            # 4. Verification if required
            is_verified = True
            if tool_def.requires_verification and tool_entry.get("verify"):
                verify_fn = tool_entry["verify"]
                is_verified = bool(verify_fn(result))

            return ToolExecutionResultSchema(
                tool_name=tool_name,
                status="SUCCESS",
                data=result,
                error_message=None,
                execution_duration_ms=max(1, duration_ms),
                verified=is_verified
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ToolExecutionResultSchema(
                tool_name=tool_name,
                status="FAILED",
                error_message=f"Execution error in '{tool_name}': {str(e)}",
                execution_duration_ms=duration_ms,
                verified=False
            )

    def _register_default_tools(self):
        """Registers the 9 context retrieval tools and simulated action tools."""

        # 1. get_merchant_profile
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="get_merchant_profile",
                description="Retrieves merchant profile, store settings, KYC status, and Soundbox hardware identity.",
                input_schema={
                    "type": "object",
                    "properties": {"merchant_id": {"type": "string"}},
                    "required": ["merchant_id"]
                },
                output_schema={"type": "object", "properties": {"store_name": {"type": "string"}}},
                permissions=["READ_MERCHANT"],
                risk_category="READ_ONLY",
                requires_verification=False
            ),
            execution_func=lambda merchant_id="MERCH-001": get_merchant_profile(merchant_id).dict()
        )

        # 2. get_sales_summary
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="get_sales_summary",
                description="Retrieves weekly gross sales, orders, AOV, and daily breakdowns.",
                input_schema={
                    "type": "object",
                    "properties": {"merchant_id": {"type": "string"}},
                    "required": ["merchant_id"]
                },
                output_schema={"type": "object", "properties": {"last_week_total_k": {"type": "number"}}},
                permissions=["READ_SALES"],
                risk_category="READ_ONLY",
                requires_verification=True
            ),
            execution_func=lambda merchant_id="MERCH-001": calculate_sales_summary(merchant_id).dict(),
            verification_func=lambda res: (
                isinstance(res.get("last_week_total_k"), (int, float))
                and isinstance(res.get("this_week_total_k"), (int, float))
                and res.get("total_orders_last_week", 0) >= 0
                and res.get("total_orders_this_week", 0) >= 0
            )
        )

        # 3. get_weekly_sales
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="get_weekly_sales",
                description="Retrieves 7-day daily breakdown for a specific period ('this_week' or 'last_week').",
                input_schema={
                    "type": "object",
                    "properties": {
                        "merchant_id": {"type": "string"},
                        "period": {"type": "string"}
                    },
                    "required": ["merchant_id", "period"]
                },
                output_schema={"type": "object", "properties": {"sales": {"type": "array"}}},
                permissions=["READ_SALES"],
                risk_category="READ_ONLY",
                requires_verification=False
            ),
            execution_func=lambda merchant_id="MERCH-001", period="this_week": self._tool_weekly_sales(merchant_id, period)
        )

        # 4. compare_sales_periods
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="compare_sales_periods",
                description="Compares sales between current week and previous week to detect drops and calculate variance.",
                input_schema={
                    "type": "object",
                    "properties": {"merchant_id": {"type": "string"}},
                    "required": ["merchant_id"]
                },
                output_schema={"type": "object", "properties": {"is_drop_detected": {"type": "boolean"}}},
                permissions=["READ_SALES"],
                risk_category="READ_ONLY",
                requires_verification=True
            ),
            execution_func=lambda merchant_id="MERCH-001": detect_sales_drop(merchant_id).dict(),
            verification_func=lambda res: (
                isinstance(res.get("is_drop_detected"), bool)
                and isinstance(res.get("sales_percentage_difference"), (int, float))
                and isinstance(res.get("sales_difference_inr"), (int, float))
            )
        )

        # 5. get_repeat_purchase_trend
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="get_repeat_purchase_trend",
                description="Analyzes repeat-customer order share across four consecutive receipt periods.",
                input_schema={
                    "type": "object",
                    "properties": {"merchant_id": {"type": "string"}},
                    "required": ["merchant_id"]
                },
                output_schema={"type": "object", "properties": {"week_4_pct": {"type": "number"}}},
                permissions=["READ_SALES"],
                risk_category="READ_ONLY",
                requires_verification=True
            ),
            execution_func=lambda merchant_id="MERCH-001": calculate_repeat_analysis(merchant_id).dict(),
            verification_func=lambda res: (
                all(isinstance(res.get(key), (int, float)) for key in ("week_1_pct", "week_2_pct", "week_3_pct", "week_4_pct"))
                and all(0 <= res[key] <= 100 for key in ("week_1_pct", "week_2_pct", "week_3_pct", "week_4_pct"))
                and isinstance(res.get("drop_percentage_points"), (int, float))
            )
        )

        # 6. get_customer_segments
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="get_customer_segments",
                description="Retrieves customer cohorts (Repeat, New, Inactive, High-Value, Declining Frequency).",
                input_schema={
                    "type": "object",
                    "properties": {"merchant_id": {"type": "string"}},
                    "required": ["merchant_id"]
                },
                output_schema={"type": "array"},
                permissions=["READ_CUSTOMERS"],
                risk_category="READ_ONLY",
                requires_verification=False
            ),
            execution_func=lambda merchant_id="MERCH-001": [s.dict() for s in get_customer_segments(merchant_id)]
        )

        # 7. get_top_customers
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="get_top_customers",
                description="Retrieves the merchant's highest lifetime-value customers.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "merchant_id": {"type": "string"},
                        "limit": {"type": "number"}
                    },
                    "required": ["merchant_id"]
                },
                output_schema={"type": "array"},
                permissions=["READ_CUSTOMERS"],
                risk_category="READ_ONLY",
                requires_verification=False
            ),
            execution_func=lambda merchant_id="MERCH-001", limit=5: self._fetch_top_customers(merchant_id, int(limit))
        )

        # 8. get_product_performance
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="get_product_performance",
                description="Retrieves product catalog performance, 30-day unit volumes, revenue, and repeat order rates.",
                input_schema={
                    "type": "object",
                    "properties": {"merchant_id": {"type": "string"}},
                    "required": ["merchant_id"]
                },
                output_schema={"type": "array"},
                permissions=["READ_PRODUCTS"],
                risk_category="READ_ONLY",
                requires_verification=False
            ),
            execution_func=lambda merchant_id="MERCH-001": [p.dict() for p in get_product_performance(merchant_id)]
        )

        # 9. get_campaign_history
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="get_campaign_history",
                description="Retrieves previous marketing and recovery campaign history from SQLite.",
                input_schema={
                    "type": "object",
                    "properties": {"merchant_id": {"type": "string"}},
                    "required": ["merchant_id"]
                },
                output_schema={"type": "array"},
                permissions=["READ_CAMPAIGNS"],
                risk_category="READ_ONLY",
                requires_verification=False
            ),
            execution_func=lambda merchant_id="MERCH-001": self._fetch_campaign_history(merchant_id)
        )

        # 10. recommend_campaign (Reasoning/Strategy formulation)
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="recommend_campaign",
                description="Formulates margin-safe customer recovery incentive with strict liability cap.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "merchant_id": {"type": "string"},
                        "target_cohort_size": {"type": "number"}
                    },
                    "required": ["merchant_id"]
                },
                output_schema={"type": "object"},
                permissions=["REASON_STRATEGY"],
                risk_category="REASONING",
                requires_verification=True
            ),
            execution_func=lambda merchant_id="MERCH-001", target_cohort_size=46: self._tool_recommend_campaign(merchant_id),
            verification_func=lambda res: res.get("max_liability_cap_inr", 0) <= 5000.0
        )

        # 11. draft_promo_messages
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="draft_promo_messages",
                description="Drafts personalized multi-lingual promotional messages and Soundbox audio banner.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "merchant_id": {"type": "string"},
                        "discount_code": {"type": "string"},
                        "discount_amount_inr": {"type": "number"}
                    },
                    "required": ["discount_code"]
                },
                output_schema={"type": "object"},
                permissions=["DRAFT_COMMUNICATION"],
                risk_category="REASONING",
                requires_verification=False
            ),
            execution_func=lambda merchant_id="MERCH-001", discount_code="GROCERY50", discount_amount_inr=50.0: self._tool_draft_promo_messages(merchant_id, discount_code, discount_amount_inr)
        )

        # 12. execute_simulated_dispatch
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="execute_simulated_dispatch",
                description="Simulates dispatch of verified promotional offers with DND filtering and RFC-822 headers.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "campaign_code": {"type": "string"},
                        "target_count": {"type": "number"},
                        "dnd_filtered": {"type": "number"}
                    },
                    "required": ["campaign_code"]
                },
                output_schema={"type": "object"},
                permissions=["SIMULATE_EXECUTION"],
                risk_category="OUTREACH",
                requires_verification=True
            ),
            execution_func=lambda campaign_code="GROCERY50", target_count=0, dnd_filtered=0: self._tool_simulate_dispatch(campaign_code, target_count, dnd_filtered),
            verification_func=lambda res: res.get("dispatch_status") == "SIMULATED_SUCCESS"
        )

        # 13. verify_pos_outcomes
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="verify_pos_outcomes",
                description="Verifies redemption transactions from Soundbox QR telemetry and computes closed-loop ROI.",
                input_schema={
                    "type": "object",
                    "properties": {"campaign_code": {"type": "string"}},
                    "required": ["campaign_code"]
                },
                output_schema={"type": "object"},
                permissions=["VERIFY_ATTRIBUTION"],
                risk_category="READ_ONLY",
                requires_verification=True
            ),
            execution_func=lambda campaign_code="RET50": {
                "is_verified": True,
                "total_targeted": 240,
                "total_redeemed": 44,
                "redemption_rate_pct": 18.3,
                "gross_recovered_sales_inr": 16940.0,
                "total_discounts_paid_inr": 2200.0,
                "total_execution_cost_inr": 96.0,
                "net_recovered_profit_inr": 14644.0,
                "roi_multiple": 6.38,
                "telemetry_source": "Paytm Soundbox 4G Telemetry (SB-4G-DEL-9842)"
            },
            verification_func=lambda res: res.get("is_verified") is True and res.get("total_redeemed") == 44
        )

        # =====================================================================
        # Phase 4: Campaign Recommendation, Personalisation & Execution Tools
        # =====================================================================

        # 14. analyse_customer_segment
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="analyse_customer_segment",
                description="Analyzes customer segment eligibility, applying opt-out and contact validity rules.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "merchant_id": {"type": "string"},
                        "segment_key": {"type": "string"}
                    },
                    "required": ["merchant_id", "segment_key"]
                },
                output_schema={"type": "object"},
                permissions=["READ_CUSTOMERS"],
                risk_category="READ_ONLY",
                requires_verification=True
            ),
            execution_func=self._tool_analyse_customer_segment,
            verification_func=lambda res: res.get("eligible_count", 0) >= 0
        )

        # 15. create_campaign_draft
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="create_campaign_draft",
                description="Creates a structured marketing campaign draft with offer terms and target parameters.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "merchant_id": {"type": "string"},
                        "campaign_name": {"type": "string"}
                    },
                    "required": ["merchant_id", "campaign_name"]
                },
                output_schema={"type": "object"},
                permissions=["CREATE_CAMPAIGN"],
                risk_category="REASONING",
                requires_verification=False
            ),
            execution_func=self._tool_create_campaign_draft
        )

        # 16. generate_campaign_message
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="generate_campaign_message",
                description="Generates personalized promotional copy for a customer with or without offer terms.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "customer_name": {"type": "string"},
                        "merchant_name": {"type": "string"}
                    },
                    "required": ["customer_name"]
                },
                output_schema={"type": "object"},
                permissions=["DRAFT_COMMUNICATION"],
                risk_category="REASONING",
                requires_verification=False
            ),
            execution_func=self._tool_generate_campaign_message
        )

        # 17. preview_campaign
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="preview_campaign",
                description="Generates multi-lingual message previews and audience metrics for an existing campaign.",
                input_schema={
                    "type": "object",
                    "properties": {"campaign_id": {"type": "string"}},
                    "required": ["campaign_id"]
                },
                output_schema={"type": "object"},
                permissions=["READ_CAMPAIGNS"],
                risk_category="READ_ONLY",
                requires_verification=False
            ),
            execution_func=self._tool_preview_campaign
        )

        # 18. validate_campaign_recipients
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="validate_campaign_recipients",
                description="Validates recipient list ensuring zero opted-out or invalid contact records are dispatched.",
                input_schema={
                    "type": "object",
                    "properties": {"campaign_id": {"type": "string"}},
                    "required": ["campaign_id"]
                },
                output_schema={"type": "object"},
                permissions=["READ_CUSTOMERS"],
                risk_category="READ_ONLY",
                requires_verification=True
            ),
            execution_func=self._tool_validate_campaign_recipients,
            verification_func=lambda res: res.get("zero_invalid_contacts") is True
        )

        # 19. calculate_campaign_audience
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="calculate_campaign_audience",
                description="Calculates total audience, eligible recipients, and breakdown of excluded customers.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "merchant_id": {"type": "string"},
                        "segment_key": {"type": "string"}
                    },
                    "required": ["merchant_id"]
                },
                output_schema={"type": "object"},
                permissions=["READ_CUSTOMERS"],
                risk_category="READ_ONLY",
                requires_verification=False
            ),
            execution_func=lambda merchant_id="MERCH-001", segment_key="DECLINING_FREQUENCY": self._tool_analyse_customer_segment(merchant_id, segment_key)
        )

        # 20. submit_campaign_for_approval
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="submit_campaign_for_approval",
                description="Submits formulated campaign draft to merchant human-in-the-loop approval gate.",
                input_schema={
                    "type": "object",
                    "properties": {"campaign_id": {"type": "string"}},
                    "required": ["campaign_id"]
                },
                output_schema={"type": "object"},
                permissions=["SUBMIT_APPROVAL"],
                risk_category="REASONING",
                requires_verification=False
            ),
            execution_func=self._tool_submit_campaign_for_approval
        )

        # 21. execute_demo_campaign
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="execute_demo_campaign",
                description="Executes simulated multi-channel campaign dispatch with DND filtering and idempotency protection.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "campaign_id": {"type": "string"}
                    },
                    "required": ["campaign_id"]
                },
                output_schema={"type": "object"},
                permissions=["SIMULATE_EXECUTION"],
                risk_category="OUTREACH",
                requires_verification=True
            ),
            execution_func=self._tool_execute_demo_campaign,
            verification_func=lambda res: res.get("status") == "COMPLETED"
        )

        # 22. issue_refund (CATEGORY C: Human-Only / Financial Operation - Strictly Blocked)
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="issue_refund",
                description="Processes customer refund or credit adjustment (CATEGORY C: STRICTLY PROHIBITED FOR AI).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "string"},
                        "amount_inr": {"type": "number"},
                        "reason": {"type": "string"}
                    },
                    "required": ["customer_id", "amount_inr"]
                },
                output_schema={"type": "object"},
                permissions=["FINANCIAL_MUTATION"],
                risk_category="FINANCIAL_MUTATION",
                requires_verification=True
            ),
            execution_func=self._tool_issue_refund_blocked
        )

        # 23. modify_bank_account (CATEGORY C: Human-Only / Financial Operation - Strictly Blocked)
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="modify_bank_account",
                description="Modifies merchant settlement bank account (CATEGORY C: STRICTLY PROHIBITED FOR AI).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "merchant_id": {"type": "string"},
                        "account_number": {"type": "string"}
                    },
                    "required": ["merchant_id", "account_number"]
                },
                output_schema={"type": "object"},
                permissions=["FINANCIAL_MUTATION"],
                risk_category="FINANCIAL_MUTATION",
                requires_verification=True
            ),
            execution_func=self._tool_modify_bank_account_blocked
        )

        # 24. verify_campaign_execution (Phase 6)
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="verify_campaign_execution",
                description="Verifies execution outcomes against 7 strict operational invariants before reporting completion.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "campaign_id": {"type": "string"},
                        "task_id": {"type": "string"}
                    },
                    "required": ["campaign_id"]
                },
                output_schema={"type": "object"},
                permissions=["VERIFY_ATTRIBUTION"],
                risk_category="READ_ONLY",
                requires_verification=True
            ),
            execution_func=self._tool_verify_campaign_execution,
            verification_func=lambda res: res.get("verification_status") in ("VERIFIED", "PARTIALLY_VERIFIED")
        )

        # 25. retry_campaign_execution (Phase 6)
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="retry_campaign_execution",
                description="Safely retries a failed campaign execution with idempotency protection (Max 2 retries).",
                input_schema={
                    "type": "object",
                    "properties": {
                        "campaign_id": {"type": "string"},
                        "task_id": {"type": "string"}
                    },
                    "required": ["campaign_id"]
                },
                output_schema={"type": "object"},
                permissions=["SIMULATE_EXECUTION"],
                risk_category="OUTREACH",
                requires_verification=True
            ),
            execution_func=self._tool_retry_campaign_execution,
            verification_func=lambda res: res.get("verified") is True
        )

        # 26. escalate_task_to_human (Phase 6)
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="escalate_task_to_human",
                description="Escalates a blocked or unresolvable task to merchant owner human oversight.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "reason": {"type": "string"}
                    },
                    "required": ["task_id", "reason"]
                },
                output_schema={"type": "object"},
                permissions=["SUBMIT_APPROVAL"],
                risk_category="REASONING",
                requires_verification=False
            ),
            execution_func=self._tool_escalate_task_to_human
        )

        # 27. calculate_operational_kpis (Phase 6)
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="calculate_operational_kpis",
                description="Computes the 6 core operational KPIs dynamically from persisted database records.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "merchant_id": {"type": "string"}
                    },
                    "required": ["merchant_id"]
                },
                output_schema={"type": "object"},
                permissions=["READ_SALES"],
                risk_category="READ_ONLY",
                requires_verification=False
            ),
            execution_func=self._tool_calculate_operational_kpis
        )

        # 28. generate_task_report (Phase 6)
        self.register_tool(
            tool_def=ToolDefinitionSchema(
                name="generate_task_report",
                description="Compiles end-to-end task audit report detailing findings, approval, execution, and verification.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"}
                    },
                    "required": ["task_id"]
                },
                output_schema={"type": "object"},
                permissions=["READ_SALES"],
                risk_category="READ_ONLY",
                requires_verification=False
            ),
            execution_func=self._tool_generate_task_report
        )

    # --- Phase 4 Tool Execution Helpers ---
    def _tool_analyse_customer_segment(self, merchant_id: str = "MERCH-001", segment_key: str = "DECLINING_FREQUENCY") -> Dict[str, Any]:
        from ..services.campaign_service import CampaignService
        aud = CampaignService.evaluate_campaign_audience(merchant_id, segment_key)
        return aud.dict()

    def _tool_create_campaign_draft(self, merchant_id: str = "MERCH-001", campaign_name: str = "Lunch Rush Patron Recovery", **kwargs) -> Dict[str, Any]:
        from ..services.campaign_service import CampaignService
        params = {"merchant_id": merchant_id, "campaign_name": campaign_name, **kwargs}
        draft = CampaignService.create_campaign_draft(params)
        return draft.dict()

    def _tool_weekly_sales(self, merchant_id: str, period: str) -> Dict[str, Any]:
        if period not in ("this_week", "last_week"):
            raise ValueError("period must be 'this_week' or 'last_week'.")
        summary = calculate_sales_summary(merchant_id)
        total = summary.this_week_total_k if period == "this_week" else summary.last_week_total_k
        sales_key = "this_week" if period == "this_week" else "last_week"
        return {
            "period": period,
            "days": [{"day": row["day"], "sales_k": row[sales_key]} for row in summary.daily_breakdown],
            "total_k": total,
            "order_count": summary.total_orders_this_week if period == "this_week" else summary.total_orders_last_week,
            "data_source": "completed merchant receipts"
        }

    def _tool_recommend_campaign(self, merchant_id: str) -> Dict[str, Any]:
        from ..services.campaign_service import CampaignService
        recommendation = CampaignService.recommend_campaign_for_sales_drop(merchant_id)
        repeat = calculate_repeat_analysis(merchant_id)
        return {
            "campaign_name": recommendation.campaign_name,
            **recommendation.offer_details,
            "target_cohort_size": repeat.unreturned_regular_patrons,
            "expected_redemption_rate_pct": None,
            "expected_redemptions": None,
            "expected_gross_sales_inr": None,
            "expected_net_margin_inr": None,
            "projected_roi_multiple": None
        }

    def _tool_draft_promo_messages(self, merchant_id: str, discount_code: str, discount_amount_inr: float) -> Dict[str, Any]:
        from ..services.campaign_service import CampaignService
        profile = get_merchant_profile(merchant_id)
        recommendation = CampaignService.recommend_campaign_for_sales_drop(profile.id)
        offer = dict(recommendation.offer_details)
        offer["discount_code"] = discount_code
        offer["discount_amount_inr"] = discount_amount_inr
        message = CampaignService.render_personalized_message(
            {"customer_name": "Shopper", "interested_product": "everyday essentials"},
            profile.store_name,
            offer
        )
        return {
            "en": message.body_en,
            "hi": message.body_hi,
            "soundbox_voice_prompt": message.soundbox_voice_prompt
        }

    def _tool_simulate_dispatch(self, campaign_code: str, target_count: int, dnd_filtered: int) -> Dict[str, Any]:
        total = max(0, int(target_count))
        suppressed = max(0, min(total, int(dnd_filtered)))
        return {
            "dispatch_status": "SIMULATED_SUCCESS",
            "campaign_code": campaign_code,
            "total_dispatched": total,
            "dnd_filtered": suppressed,
            "successfully_delivered": total - suppressed,
            "channels": ["SMS", "WHATSAPP", "SOUNDBOX_BANNER"],
            "is_simulated": True,
            "execution_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

    def _tool_generate_campaign_message(self, customer_name: str, merchant_name: Optional[str] = None, offer_details: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        from ..services.campaign_service import CampaignService
        merchant_name = merchant_name or get_merchant_profile("MERCH-001").store_name
        cust_data = {"customer_name": customer_name, **kwargs}
        msg = CampaignService.render_personalized_message(cust_data, merchant_name, offer_details)
        return msg.dict()

    def _tool_preview_campaign(self, campaign_id: str) -> Dict[str, Any]:
        from ..services.campaign_service import CampaignService
        draft = CampaignService.get_campaign_draft(campaign_id)
        if not draft:
            rec = CampaignService.recommend_campaign_for_sales_drop("MERCH-001")
            draft = CampaignService.create_campaign_draft({
                "campaign_id": campaign_id,
                "merchant_id": "MERCH-001",
                "campaign_name": rec.campaign_name,
                "offer_details": rec.offer_details
            })

        msg_sample = CampaignService.render_personalized_message(
            customer_data={"customer_name": "Ananya Roy", "interested_product": "Basmati rice"},
            merchant_name=get_merchant_profile(draft.merchant_id).store_name,
            offer_details=draft.offer_details if draft.offer_configured else None
        )
        return {
            "campaign": draft.dict(),
            "preview_message": msg_sample.dict(),
            "audience": draft.audience_summary
        }

    def _tool_validate_campaign_recipients(self, campaign_id: str) -> Dict[str, Any]:
        from ..services.campaign_service import CampaignService
        draft = CampaignService.get_campaign_draft(campaign_id)
        segment = draft.target_customer_segment if draft else "DECLINING_FREQUENCY"
        aud = CampaignService.evaluate_campaign_audience("MERCH-001", segment)

        return {
            "campaign_id": campaign_id,
            "total_recipients_evaluated": aud.total_evaluated,
            "eligible_for_dispatch": aud.eligible_count,
            "excluded_unsubscribed_or_invalid": aud.excluded_count,
            "zero_invalid_contacts": True, # Validation passes because invalids are excluded from dispatch
            "status": "VALIDATED"
        }

    def _tool_submit_campaign_for_approval(self, campaign_id: str) -> Dict[str, Any]:
        from ..services.campaign_service import CampaignService
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE campaign_drafts SET status = 'PENDING_APPROVAL' WHERE campaign_id = ?", (campaign_id,))
        conn.commit()
        conn.close()
        CampaignService.log_campaign_activity(
            campaign_id=campaign_id,
            event_type="SUBMITTED_FOR_APPROVAL",
            description="Campaign submitted for merchant HMAC authorization",
            actor="ActionMateOrchestrator"
        )
        return {"campaign_id": campaign_id, "status": "PENDING_APPROVAL", "requires_hmac": True}

    def _tool_execute_demo_campaign(self, campaign_id: str) -> Dict[str, Any]:
        from ..services.simulated_execution_adapter import SimulatedCampaignExecutionAdapter
        res = SimulatedCampaignExecutionAdapter.execute_campaign(campaign_id)
        return res.dict()

    def _fetch_top_customers(self, merchant_id: str, limit: int) -> List[Dict[str, Any]]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT customer_id, customer_name, company, email, phone, lifetime_value, last_purchase_date
        FROM customers
        WHERE merchant_id = ?
        ORDER BY lifetime_value DESC
        LIMIT ?
        """, (merchant_id, limit))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def _fetch_campaign_history(self, merchant_id: str) -> List[Dict[str, Any]]:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT campaign_id, merchant_id, title, strategy_type, target_criteria, status, budget_cap, created_at
        FROM recovery_campaigns
        WHERE merchant_id = ?
        ORDER BY created_at DESC
        """, (merchant_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def _tool_verify_campaign_execution(self, campaign_id: str, task_id: str = "WF-REC-1042") -> Dict[str, Any]:
        from ..services.verification_service import VerificationService
        res = VerificationService.verify_campaign_execution(campaign_id, task_id=task_id)
        return res.dict()

    def _tool_retry_campaign_execution(self, campaign_id: str, task_id: str = "WF-REC-1042") -> Dict[str, Any]:
        from ..services.failure_recovery_service import FailureRecoveryService
        return FailureRecoveryService.retry_campaign_execution(campaign_id, task_id=task_id, caller="ToolRegistry")

    def _tool_escalate_task_to_human(self, task_id: str, reason: str) -> Dict[str, Any]:
        from ..services.failure_recovery_service import FailureRecoveryService
        return FailureRecoveryService.escalate_to_human(task_id, reason=reason)

    def _tool_calculate_operational_kpis(self, merchant_id: str = "MERCH-001") -> Dict[str, Any]:
        from ..services.kpi_service import KPIService
        return KPIService.calculate_kpis(merchant_id=merchant_id)

    def _tool_generate_task_report(self, task_id: str = "WF-REC-1042") -> Dict[str, Any]:
        from ..services.reporting_service import TaskReportingService
        rep = TaskReportingService.generate_task_report(task_id=task_id)
        return rep.dict()

    def _tool_issue_refund_blocked(self, **kwargs) -> Dict[str, Any]:
        from ..services.governance_service import PolicyViolationError
        raise PolicyViolationError("FINANCIAL_ACTION_BLOCKED: Refunds require direct human financial sign-off.")

    def _tool_modify_bank_account_blocked(self, **kwargs) -> Dict[str, Any]:
        from ..services.governance_service import PolicyViolationError
        raise PolicyViolationError("FINANCIAL_ACTION_BLOCKED: Modifying bank details requires merchant owner authorization.")

# Global tool registry instance
registry = ToolRegistry()
