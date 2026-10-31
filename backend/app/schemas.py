"""Paytm AI ActionMate Pydantic-Compatible Data Schemas.
Enforces strict schema validation, type checking, and serializability
for merchant business profiles, sales analytics, repeat trends, and customer segments.
Runs with zero external pip dependencies.
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime

class SchemaValidationError(Exception):
    """Raised when data fails schema type or field validation."""
    pass

class BaseSchema:
    """Base schema class providing Pydantic-like validation and serialization."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.validate()

    def validate(self):
        """Hook for subclass validation."""
        pass

    def dict(self) -> Dict[str, Any]:
        """Serializes schema instance into standard dictionary."""
        res = {}
        for k, v in self.__dict__.items():
            if isinstance(v, BaseSchema):
                res[k] = v.dict()
            elif isinstance(v, list):
                res[k] = [item.dict() if isinstance(item, BaseSchema) else item for item in v]
            else:
                res[k] = v
        return res

    def model_dump(self) -> Dict[str, Any]:
        """Alias for dict() to match Pydantic v2 API."""
        return self.dict()

class MerchantProfileSchema(BaseSchema):
    """Validates merchant profile records."""
    id: str
    store_name: str
    owner_name: str
    email: str
    phone: str
    city: str
    soundbox_device_id: str
    soundbox_status: str
    currency: str
    category: str
    business_hours: str
    gstin_demo: str

    def validate(self):
        if not self.id:
            raise SchemaValidationError("Merchant 'id' cannot be empty.")
        if not self.store_name:
            raise SchemaValidationError("Merchant 'store_name' cannot be empty.")

class DailySalesPointSchema(BaseSchema):
    """Daily sales comparison point."""
    day: str
    last_week: float
    this_week: float
    change_pct: float
    absolute_change_k: float

class SalesSummarySchema(BaseSchema):
    """Summary of weekly sales and core volume metrics."""
    merchant_id: str
    last_week_total_k: float
    this_week_total_k: float
    overall_drop_pct: float
    absolute_difference_inr: float
    total_orders_last_week: int
    total_orders_this_week: int
    aov_inr: float
    revenue_leakage_inr: float
    daily_breakdown: List[Dict[str, Any]]
    is_demo: bool = True

class RepeatAnalysisSchema(BaseSchema):
    """Repeat customer order analysis across 4 consecutive weeks."""
    cohort_name: str
    week_1_pct: float  # 41%
    week_2_pct: float  # 39%
    week_3_pct: float  # 37%
    week_4_pct: float  # 24%
    drop_percentage_points: float  # -13%
    relative_drop_pct: float       # -35.1%
    unreturned_regular_patrons: int
    revenue_at_risk_inr: float
    telemetry_device: str

    def validate(self):
        if self.week_4_pct > self.week_3_pct:
            raise SchemaValidationError("Week 4 repeat rate should reflect drop vs Week 3.")

class SalesDropDetectionSchema(BaseSchema):
    """Deterministic backend sales drop detection results."""
    is_drop_detected: bool
    drop_severity: str  # HIGH, MODERATE, LOW, NONE
    comparison_period: str
    sales_difference_inr: float
    sales_percentage_difference: float
    repeat_purchase_change_pts: float
    order_volume_change: int
    explanation: str
    supporting_evidence: List[str]

class CustomerSegmentSchema(BaseSchema):
    """Customer segment with count, LTV, and member accounts."""
    segment_key: str
    segment_name: str
    description: str
    customer_count: int
    total_segment_ltv_inr: float
    sample_customers: List[Dict[str, Any]]

class ProductPerformanceSchema(BaseSchema):
    """Product catalog sales and repeat purchase metrics."""
    product_id: str
    sku: str
    name: str
    category: str
    unit_price: float
    units_sold_30d: int
    gross_revenue_inr: float
    repeat_order_rate_pct: float

# =====================================================================
# Phase 3: Autonomous AI Orchestrator & Reasoning Engine Schemas
# =====================================================================

class PlanStepSchema(BaseSchema):
    """Individual structured step in an ActionMate execution plan."""
    step_id: str
    step_number: int
    name: str
    description: str
    tool_required: str
    input_parameters: Dict[str, Any]
    expected_output: str
    risk_level: str  # LOW, MEDIUM, HIGH
    requires_approval: bool
    status: str      # QUEUED, READY_FOR_EXECUTION, EXECUTING, COMPLETED, PENDING_APPROVAL, FAILED, SKIPPED
    execution_result: Optional[Dict[str, Any]] = None

    def validate(self):
        if not self.step_id or not self.name:
            raise SchemaValidationError("Plan step requires a non-empty step_id and name.")
        if self.risk_level not in ("LOW", "MEDIUM", "HIGH"):
            raise SchemaValidationError(f"Invalid risk_level '{self.risk_level}'. Must be LOW, MEDIUM, or HIGH.")

class EpistemicReportSchema(BaseSchema):
    """Epistemic evidence structure separating facts, interpretations, and unknowns."""
    confirmed_data: List[str]
    ai_interpretation: List[str]
    recommendations: List[str]
    unknown_information: List[str]

class TaskSchema(BaseSchema):
    """Structured autonomous task created by the Orchestrator."""
    task_id: str
    merchant_id: str
    original_request: str
    detected_intent: str
    relevant_entities: Dict[str, Any]
    required_data: List[str]
    risk_classification: str
    approval_requirements: Dict[str, Any]
    current_state: str
    plan: List[PlanStepSchema]
    findings: Dict[str, Any]
    epistemic_report: EpistemicReportSchema
    is_demo: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def validate(self):
        if not self.task_id:
            raise SchemaValidationError("Task 'task_id' cannot be empty.")
        if not self.detected_intent:
            raise SchemaValidationError("Task requires a detected_intent.")
        if not self.plan or len(self.plan) == 0:
            raise SchemaValidationError("Task plan must contain at least one step.")

class ToolDefinitionSchema(BaseSchema):
    """Metadata and execution boundaries for registered tools."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    permissions: List[str]
    risk_category: str  # READ_ONLY, REASONING, FINANCIAL_MUTATION, OUTREACH
    requires_verification: bool = False

    def validate(self):
        if not self.name or not self.description:
            raise SchemaValidationError("Tool definition must have name and description.")

class ToolExecutionResultSchema(BaseSchema):
    """Result of running a tool through the controlled tool registry."""
    tool_name: str
    status: str  # SUCCESS, PERMISSION_DENIED, VALIDATION_ERROR, FAILED
    data: Optional[Any] = None
    error_message: Optional[str] = None
    execution_duration_ms: int = 0
    verified: bool = False

# =====================================================================
# Phase 4: Campaign Recommendation, Personalisation & Execution Schemas
# =====================================================================

class CampaignRecommendationSchema(BaseSchema):
    """Structured campaign recommendation generated from sales drop analysis."""
    campaign_name: str
    business_objective: str
    reason_for_recommendation: str
    target_customer_segment: str
    suggested_campaign_duration: str
    recommended_communication_channel: str
    suggested_promotional_approach: str
    expected_operational_outcome: str
    risks_and_assumptions: str
    offer_details: Optional[Dict[str, Any]] = None
    is_demo: bool = True

    def validate(self):
        if not self.campaign_name or not self.business_objective:
            raise SchemaValidationError("Campaign recommendation requires campaign_name and business_objective.")

class AudienceBreakdownSchema(BaseSchema):
    """Target audience evaluation and exclusion details."""
    total_evaluated: int
    eligible_count: int
    excluded_count: int
    eligible_customers: List[Dict[str, Any]]
    excluded_customers: List[Dict[str, Any]]
    exclusion_reasons: Dict[str, int]
    targeting_criteria: Dict[str, Any]

class PersonalizedMessageSchema(BaseSchema):
    """Personalized marketing message rendered for a customer."""
    customer_id: Optional[str] = None
    customer_name: str
    merchant_name: str
    relevant_product: str
    offer_configured: bool
    subject: str
    body_en: str
    body_hi: str
    soundbox_voice_prompt: str
    call_to_action: str
    tone: str

class CampaignDraftSchema(BaseSchema):
    """Full campaign draft entity with target audience, offer terms, and status."""
    campaign_id: str
    merchant_id: str
    campaign_name: str
    business_objective: str
    reason_for_recommendation: str
    target_customer_segment: str
    suggested_duration: str
    communication_channel: str
    promotional_approach: str
    expected_operational_outcome: str
    risks_and_assumptions: str
    status: str = "DRAFT"
    offer_configured: bool = False
    offer_details: Optional[Dict[str, Any]] = None
    messages: Optional[Dict[str, Any]] = None
    audience_summary: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    execution_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_demo: bool = True

class SimulatedExecutionResultSchema(BaseSchema):
    """Output from the simulated execution adapter."""
    execution_id: str
    campaign_id: str
    status: str
    total_attempted: int
    delivered_count: int
    dnd_suppressed_count: int
    failed_count: int
    channels: List[str]
    executed_at: str
    recipient_statuses: List[Dict[str, Any]]
    is_demo: bool = True

# =====================================================================
# Phase 5: Human Approval, Permission Control & Audit Logging Schemas
# =====================================================================

class ApprovalRequestSchema(BaseSchema):
    """Detailed approval request presented to the merchant."""
    approval_id: str
    task_id: str
    campaign_id: str
    merchant_id: str
    merchant_name: str
    campaign_name: str
    campaign_purpose: str
    reason_for_recommendation: str
    target_audience: str
    customer_count: int
    promotional_message: Dict[str, str]
    campaign_settings: Dict[str, Any]
    execution_mode: str = "SIMULATED_DEMO"
    risks_and_assumptions: str
    ai_recommendation: Dict[str, Any]
    current_status: str = "PENDING_APPROVAL"
    message_version: int = 1
    content_hash: str = ""
    created_at: Optional[str] = None
    is_demo: bool = True

class ApprovalRecordSchema(BaseSchema):
    """Immutable record of a merchant approval decision."""
    approval_id: str
    task_id: str
    campaign_id: str
    merchant_id: str
    approver_id: str
    decision: str
    timestamp: str
    message_version: int
    content_hash: str
    reason_or_comments: str
    approval_status: str
    max_budget_authorized_inr: float = 3600.0
    auth_signature: str = ""

class AuditEventSchema(BaseSchema):
    """Tamper-evident audit event record chained with SHA-256."""
    event_id: str
    merchant_id: str
    task_id: str
    actor_id: str
    action: str
    resource: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    timestamp: str
    execution_result: str = "SUCCESS"
    metadata: Dict[str, Any] = {}
    previous_hash: str = ""
    current_hash: str = ""
    is_simulated: bool = False

class PolicyEvaluationSchema(BaseSchema):
    """Result of evaluating an action against the 3-category Risk Policy."""
    action_name: str
    category: str
    allowed: bool
    requires_human_approval: bool
    is_financial_mutation: bool
    reason: str

# =====================================================================
# Phase 6: Verification, Recovery, KPI Analytics & Reporting Schemas
# =====================================================================

class VerificationCheckItem(BaseSchema):
    """Individual verification check detail."""
    name: str
    passed: bool
    description: str
    details: Dict[str, Any] = {}

class VerificationResultSchema(BaseSchema):
    """Structured result returned by the Verification Service."""
    verification_id: str
    task_id: str
    campaign_id: str
    execution_id: str
    verification_status: str  # VERIFIED, PARTIALLY_VERIFIED, FAILED, REQUIRES_HUMAN
    verified_checks: List[str]
    failed_checks: List[str]
    checks_detail: List[VerificationCheckItem] = []
    timestamp: str
    evidence_references: Dict[str, Any] = {}
    is_demo: bool = True

class FailureRecoverySchema(BaseSchema):
    """Failure diagnostic, retry, and escalation status."""
    task_id: str
    campaign_id: str
    failure_type: str
    retry_count: int = 0
    max_retries_allowed: int = 2
    can_retry: bool = True
    escalation_status: str = "NONE"  # NONE, ESCALATED_TO_HUMAN, RESOLVED
    reason: str
    suggested_action: str
    escalated_to: Optional[str] = None
    timestamp: str

class KPISummarySchema(BaseSchema):
    """The 6 Paytm AI ActionMate KPIs calculated dynamically from database records."""
    task_completion_rate: float
    task_completion_display: str
    average_resolution_time_min: float
    average_resolution_display: str
    human_escalation_rate: float
    human_escalation_display: str
    approval_compliance: Optional[float]
    approval_compliance_display: str
    cost_per_completed_task_inr: float
    cost_per_completed_task_display: str
    campaign_engagement_rate: float
    campaign_engagement_display: str
    # Denominators and counts
    total_eligible_tasks: int
    completed_eligible_tasks: int
    failed_tasks_count: int
    escalated_tasks_count: int
    total_operating_cost_inr: float
    total_engaged_recipients: int
    total_delivered_recipients: int
    approval_violations_count: int
    # Benchmark reference (Slide targets)
    presentation_benchmarks: Dict[str, str] = {
        "task_completion_rate": "92.0%",
        "average_resolution_time": "4.0 min",
        "human_escalation_rate": "12.0%",
        "approval_compliance": "100.0%",
        "cost_per_completed_task": "₹3.00",
        "campaign_engagement": "18.0%"
    }
    period_comparison: Dict[str, Any] = {}
    calculated_at: str
    is_demo: bool = True

class TaskReportSchema(BaseSchema):
    """End-to-end task audit report for executive review and export."""
    report_id: str
    task_id: str
    merchant_id: str
    merchant_name: str
    original_request: str
    business_context: Dict[str, Any]
    sales_findings: Dict[str, Any]
    ai_interpretation: Dict[str, Any]
    recommended_campaign: Dict[str, Any]
    approval_decision: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    verification_result: Optional[Dict[str, Any]] = None
    time_taken_seconds: float
    human_involvement: Dict[str, Any]
    relevant_kpi_contribution: Dict[str, Any]
    audit_history: List[Dict[str, Any]]
    generated_at: str
    is_demo: bool = True




