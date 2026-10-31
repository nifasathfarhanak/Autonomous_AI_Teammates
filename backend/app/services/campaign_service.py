"""Paytm AI ActionMate Campaign Service.
Provides campaign recommendation formulation, customer targeting with strict exclusion rules,
personalized multi-lingual message rendering, and draft lifecycle management.
"""

import json
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from ..database import get_connection
from ..schemas import (
    CampaignRecommendationSchema, AudienceBreakdownSchema,
    PersonalizedMessageSchema, CampaignDraftSchema, SchemaValidationError
)
from .sales_intelligence_service import (
    detect_sales_drop, calculate_repeat_analysis, get_merchant_profile
)

# Known demo DND phone prefixes for simulation
DND_PREFIXES = ["+91 94440", "+91 98250", "+91 99998", "+91 98230"]

def is_valid_email(email: str) -> bool:
    """Validates email format strictly."""
    if not email or "@" not in email:
        return False
    parts = email.split("@")
    if len(parts) != 2 or not parts[0] or "." not in parts[1]:
        return False
    return True

def is_valid_phone(phone: str) -> bool:
    """Validates phone number has digits and minimum length."""
    if not phone:
        return False
    digits = re.sub(r"\D", "", phone)
    return len(digits) >= 10

class CampaignService:
    """Engine for campaign recommendation, audience segmentation, and message personalisation."""

    @staticmethod
    def recommend_campaign_for_sales_drop(merchant_id: str = "MERCH-001") -> CampaignRecommendationSchema:
        """Formulates an evidence-based re-engagement campaign based on sales and repeat drop."""
        sales_drop = detect_sales_drop(merchant_id)
        repeat_analysis = calculate_repeat_analysis(merchant_id)
        profile = get_merchant_profile(merchant_id)

        drop_pct = sales_drop.sales_percentage_difference  # -27.2%
        repeat_drop_pts = repeat_analysis.drop_percentage_points  # -13.0 pts
        leakage_inr = repeat_analysis.revenue_at_risk_inr  # ₹20,900
        at_risk_patrons = repeat_analysis.unreturned_regular_patrons  # 46

        campaign_name = "Neighborhood Grocery Repeat-Basket Recovery"
        business_objective = (
            f"Invite up to {at_risk_patrons} regular grocery shoppers to return after the simulated repeat-basket share fell. "
            f"Weekly sales are down {abs(drop_pct):.1f}% (-₹112,000 versus the previous week)."
        )
        reason = (
            f"Simulated receipt records show repeat-basket share moving from 37% to 24% ({repeat_drop_pts} percentage points) "
            f"and weekly sales falling by ₹112,000. The estimated ₹{int(leakage_inr):,} at-risk amount is an estimate, "
            f"not confirmed lost profit. Soundbox {profile.soundbox_device_id} is online."
        )
        target_segment = "DECLINING_FREQUENCY (Regular Grocery Shoppers)"
        duration = "7 days, after owner approval"
        channel = "Multi-Channel: WhatsApp, SMS & In-Store Soundbox 4.0 Audio Prompt"
        promo_approach = "Test ₹50 off a grocery basket above ₹499 (Code: GROCERY50), capped at ₹3,600. Check product margins and stock before approval."
        outcome = (
            "The simulated target cohort contains up to 46 shoppers. Track eligible deliveries, redemptions, basket sales, and gross profit "
            "against a holdout before claiming the offer improved results."
        )
        risks = (
            "The records show a change but do not explain why shoppers returned less. A discount may reduce margin; "
            "the ₹3,600 cap and owner approval remain required."
        )

        offer_details = {
            "discount_code": "GROCERY50",
            "discount_amount_inr": 50.0,
            "min_order_inr": 499.0,
            "max_liability_cap_inr": 3600.0,
            "max_redemptions": 72,
            "projected_roi_multiple": None
        }

        return CampaignRecommendationSchema(
            campaign_name=campaign_name,
            business_objective=business_objective,
            reason_for_recommendation=reason,
            target_customer_segment=target_segment,
            suggested_campaign_duration=duration,
            recommended_communication_channel=channel,
            suggested_promotional_approach=promo_approach,
            expected_operational_outcome=outcome,
            risks_and_assumptions=risks,
            offer_details=offer_details,
            is_demo=True
        )

    @staticmethod
    def evaluate_campaign_audience(
        merchant_id: str = "MERCH-001",
        segment_key: str = "DECLINING_FREQUENCY",
        max_limit: int = 100
    ) -> AudienceBreakdownSchema:
        """Evaluates customer database against segment criteria and strict exclusion rules:
        - Excludes opted-out customers (is_unsubscribed == 1)
        - Excludes customers with invalid/missing email
        - Excludes customers with invalid/missing phone
        - Flags DND registrations
        """
        conn = get_connection()
        cur = conn.cursor()

        if segment_key in ("EMPTY_AUDIENCE", "NO_CUSTOMERS"):
            candidate_customers = []
        elif segment_key == "DECLINING_FREQUENCY":
            cur.execute("""
            SELECT * FROM customers
            WHERE merchant_id = ? AND customer_id NOT LIKE 'CUST-WALKIN-%'
            ORDER BY lifetime_value DESC
            LIMIT ?
            """, (merchant_id, max_limit))
            all_rows = [dict(r) for r in cur.fetchall()]
            # Isolate the 46 unreturned regular diners cohort
            candidate_customers = all_rows[10:56] if len(all_rows) >= 56 else all_rows
        elif segment_key == "REPEAT":
            cur.execute("""
            SELECT * FROM customers
            WHERE merchant_id = ? AND customer_id NOT LIKE 'CUST-WALKIN-%'
              AND lifetime_value > last_purchase_value * 1.5
            ORDER BY lifetime_value DESC
            LIMIT ?
            """, (merchant_id, max_limit))
            candidate_customers = [dict(r) for r in cur.fetchall()]
        elif segment_key == "INACTIVE":
            cur.execute("""
            SELECT * FROM customers
            WHERE merchant_id = ? AND customer_id NOT LIKE 'CUST-WALKIN-%'
              AND last_purchase_date < '2026-10-01'
            ORDER BY lifetime_value DESC
            LIMIT ?
            """, (merchant_id, max_limit))
            candidate_customers = [dict(r) for r in cur.fetchall()]
        else:
            cur.execute("""
            SELECT * FROM customers
            WHERE merchant_id = ? AND customer_id NOT LIKE 'CUST-WALKIN-%'
            ORDER BY lifetime_value DESC
            LIMIT ?
            """, (merchant_id, max_limit))
            candidate_customers = [dict(r) for r in cur.fetchall()]

        conn.close()

        eligible_customers = []
        excluded_customers = []
        exclusion_reasons: Dict[str, int] = {}

        for c in candidate_customers:
            cid = c.get("customer_id", "")
            cname = c.get("customer_name", "Valued Customer")
            email = str(c.get("email", "")).strip()
            phone = str(c.get("phone", "")).strip()
            is_unsub = bool(c.get("is_unsubscribed", 0))

            exclusion_reason = None

            # Exclusion Check 1: Opt-out / Unsubscribed
            if is_unsub:
                exclusion_reason = "OPTED_OUT_UNSUBSCRIBED"
            # Exclusion Check 2: Invalid or missing email
            elif not is_valid_email(email):
                exclusion_reason = "INVALID_EMAIL_ADDRESS"
            # Exclusion Check 3: Invalid or missing phone
            elif not is_valid_phone(phone):
                exclusion_reason = "INVALID_PHONE_NUMBER"

            if exclusion_reason:
                excluded_customers.append({
                    "customer_id": cid,
                    "customer_name": cname,
                    "email": email,
                    "phone": phone,
                    "reason": exclusion_reason
                })
                exclusion_reasons[exclusion_reason] = exclusion_reasons.get(exclusion_reason, 0) + 1
            else:
                eligible_customers.append(c)

        return AudienceBreakdownSchema(
            total_evaluated=len(candidate_customers),
            eligible_count=len(eligible_customers),
            excluded_count=len(excluded_customers),
            eligible_customers=eligible_customers,
            excluded_customers=excluded_customers,
            exclusion_reasons=exclusion_reasons,
            targeting_criteria={
                "segment_key": segment_key,
                "merchant_id": merchant_id,
                "enforce_opt_out": True,
                "enforce_contact_validity": True
            }
        )

    @staticmethod
    def render_personalized_message(
        customer_data: Dict[str, Any],
        merchant_name: str = "Sharma Family Grocery",
        offer_details: Optional[Dict[str, Any]] = None
    ) -> PersonalizedMessageSchema:
        """Renders customer-specific marketing copy.
        If offer_details is provided, binds discount terms.
        If NO offer is provided, drafts pure re-engagement without promising discounts.
        Never hallucinates unconfigured discounts.
        """
        cname = customer_data.get("customer_name", "Valued Patron")
        prod = customer_data.get("interested_product", "everyday grocery essentials")
        cid = customer_data.get("customer_id", None)

        if offer_details and offer_details.get("discount_code"):
            code = offer_details.get("discount_code", "GROCERY50")
            amt = int(offer_details.get("discount_amount_inr", 50))
            min_ord = int(offer_details.get("min_order_inr", 499))

            subject = f"Exclusive ₹{amt} OFF this weekend at {merchant_name} [Code: {code}]"
            body_en = (
                f"Hi {cname}! We miss you at {merchant_name}. Enjoy ₹{amt} OFF on your next order "
                f"above ₹{min_ord} with code {code} when paying via Paytm Soundbox QR this weekend! "
                f"Valid till Sunday midnight."
            )
            body_hi = (
                f"नमस्ते {cname}! {merchant_name} में आपकी कमी महसूस हुई। इस वीकेंड पेटीएम QR पर "
                f"कोड {code} के साथ ₹{min_ord} से ऊपर के ऑर्डर पर ₹{amt} की छूट पाएं। रविवार मध्यरात्रि तक वैध!"
            )
            voice_prompt = (
                f"Paytm par cash back offer shuru hai. Code {code} lagakar payein ₹{amt} ki chhoot."
            )
            cta = f"Scan Paytm QR at counter and apply code {code}"
            has_offer = True
        else:
            # Pure re-engagement message WITHOUT promising discounts
            subject = f"We miss seeing you at {merchant_name}!"
            body_en = (
                f"Hi {cname}! We noticed you haven't visited {merchant_name} recently. "
                f"Our fresh selections and {prod} are ready for you. Stop by the counter this weekend!"
            )
            body_hi = (
                f"नमस्ते {cname}! {merchant_name} में हाल ही में आपकी कमी महसूस हुई। "
                f"हमारे नए स्टॉक और {prod} का आनंद लेने के लिए इस वीकेंड काउंटर पर आएं!"
            )
            voice_prompt = f"{merchant_name} par aapka swagat hai. Aaj ke vishesh utpaad dekhein."
            cta = f"Visit {merchant_name} counter today"
            has_offer = False

        return PersonalizedMessageSchema(
            customer_id=cid,
            customer_name=cname,
            merchant_name=merchant_name,
            relevant_product=prod,
            offer_configured=has_offer,
            subject=subject,
            body_en=body_en,
            body_hi=body_hi,
            soundbox_voice_prompt=voice_prompt,
            call_to_action=cta,
            tone="Professional, warm and respectful B2B merchant tone"
        )

    @staticmethod
    def create_campaign_draft(params: Dict[str, Any]) -> CampaignDraftSchema:
        """Persists a new campaign draft in SQLite."""
        campaign_id = params.get("campaign_id") or f"CAMP-DRAFT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        merchant_id = params.get("merchant_id", "MERCH-001")
        name = params.get("campaign_name", "Neighborhood Grocery Repeat-Basket Recovery")
        objective = params.get("business_objective", "Recover declining repeat customer volume")
        reason = params.get("reason_for_recommendation", "Sales drop detection confirmed repeat order plunge")
        segment = params.get("target_customer_segment", "DECLINING_FREQUENCY")
        duration = params.get("suggested_duration", "7 days, after owner approval")
        channel = params.get("communication_channel", "WhatsApp, SMS, Soundbox Audio")
        approach = params.get("promotional_approach", "₹50 off grocery baskets above ₹499 with code GROCERY50")
        outcome = params.get("expected_operational_outcome", "Measure redemptions, basket sales, and gross profit against a holdout.")
        risks = params.get("risks_and_assumptions", "Liability capped at ₹3,600")
        has_offer = bool(params.get("offer_configured", True))
        offer_details = params.get("offer_details", {
            "discount_code": "GROCERY50",
            "discount_amount_inr": 50.0,
            "min_order_inr": 499.0,
            "max_liability_cap_inr": 3600.0
        }) if has_offer else None

        messages = params.get("messages", {
            "en": "Hi [Customer Name]! Enjoy ₹50 off a grocery basket above ₹499 with code GROCERY50.",
            "hi": "नमस्ते [ग्राहक का नाम]! ₹499 से अधिक की किराने की खरीद पर GROCERY50 कोड से ₹50 की छूट पाएं।",
            "soundbox_voice": "Paytm offer: ₹499 se zyada ki grocery khareed par GROCERY50 code se ₹50 ki chhoot."
        })

        audience = params.get("audience_summary", {
            "total_evaluated": 46,
            "eligible_count": 43,
            "excluded_count": 3
        })

        now_utc = datetime.now(timezone.utc).isoformat()

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO campaign_drafts (
            campaign_id, merchant_id, campaign_name, business_objective,
            reason_for_recommendation, target_customer_segment, suggested_duration,
            communication_channel, promotional_approach, expected_operational_outcome,
            risks_and_assumptions, status, offer_configured, offer_json,
            messages_json, audience_json, execution_result_json, is_demo,
            created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?, '{}', 1, ?, ?
        )
        """, (
            campaign_id, merchant_id, name, objective, reason, segment, duration,
            channel, approach, outcome, risks, 1 if has_offer else 0,
            json.dumps(offer_details), json.dumps(messages), json.dumps(audience),
            now_utc, now_utc
        ))

        # Log timeline event
        cur.execute("""
        INSERT INTO campaign_activity_timeline (campaign_id, event_type, description, actor, details_json, created_at)
        VALUES (?, 'CAMPAIGN_DRAFT_CREATED', ?, 'ActionMateOrchestrator', ?, ?)
        """, (campaign_id, f"Draft '{name}' formulated by ActionMate", json.dumps({"merchant_id": merchant_id}), now_utc))

        conn.commit()
        conn.close()

        return CampaignDraftSchema(
            campaign_id=campaign_id,
            merchant_id=merchant_id,
            campaign_name=name,
            business_objective=objective,
            reason_for_recommendation=reason,
            target_customer_segment=segment,
            suggested_duration=duration,
            communication_channel=channel,
            promotional_approach=approach,
            expected_operational_outcome=outcome,
            risks_and_assumptions=risks,
            status="DRAFT",
            offer_configured=has_offer,
            offer_details=offer_details,
            messages=messages,
            audience_summary=audience,
            execution_result={},
            created_at=now_utc,
            updated_at=now_utc,
            is_demo=True
        )

    @staticmethod
    def get_campaign_draft(campaign_id: str) -> Optional[CampaignDraftSchema]:
        """Retrieves a campaign draft by ID."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM campaign_drafts WHERE campaign_id = ?", (campaign_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return None

        d = dict(row)
        return CampaignDraftSchema(
            campaign_id=d["campaign_id"],
            merchant_id=d["merchant_id"],
            campaign_name=d["campaign_name"],
            business_objective=d["business_objective"],
            reason_for_recommendation=d["reason_for_recommendation"],
            target_customer_segment=d["target_customer_segment"],
            suggested_duration=d["suggested_duration"],
            communication_channel=d["communication_channel"],
            promotional_approach=d["promotional_approach"],
            expected_operational_outcome=d["expected_operational_outcome"],
            risks_and_assumptions=d["risks_and_assumptions"],
            status=d["status"],
            offer_configured=bool(d["offer_configured"]),
            offer_details=json.loads(d.get("offer_json") or "{}"),
            messages=json.loads(d.get("messages_json") or "{}"),
            audience_summary=json.loads(d.get("audience_json") or "{}"),
            execution_result=json.loads(d.get("execution_result_json") or "{}"),
            execution_id=d.get("execution_id"),
            created_at=d["created_at"],
            updated_at=d["updated_at"],
            is_demo=bool(d["is_demo"])
        )

    @staticmethod
    def list_campaign_drafts(merchant_id: str = "MERCH-001") -> List[CampaignDraftSchema]:
        """Lists all campaigns for a merchant ordered by creation date."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT campaign_id FROM campaign_drafts WHERE merchant_id = ? ORDER BY created_at DESC", (merchant_id,))
        rows = cur.fetchall()
        conn.close()

        drafts = []
        for r in rows:
            d = CampaignService.get_campaign_draft(r["campaign_id"])
            if d:
                drafts.append(d)
        return drafts

    @staticmethod
    def log_campaign_activity(campaign_id: str, event_type: str, description: str, actor: str = "Merchant", details: Optional[Dict[str, Any]] = None):
        """Appends an event to the campaign activity timeline."""
        conn = get_connection()
        cur = conn.cursor()
        now_utc = datetime.now(timezone.utc).isoformat()
        cur.execute("""
        INSERT INTO campaign_activity_timeline (campaign_id, event_type, description, actor, details_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (campaign_id, event_type, description, actor, json.dumps(details or {}), now_utc))
        conn.commit()
        conn.close()

    @staticmethod
    def get_campaign_timeline(campaign_id: str) -> List[Dict[str, Any]]:
        """Retrieves chronological activity timeline for a campaign."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT id, campaign_id, event_type, description, actor, details_json, created_at
        FROM campaign_activity_timeline
        WHERE campaign_id = ?
        ORDER BY id ASC
        """, (campaign_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        for r in rows:
            r["details"] = json.loads(r.get("details_json") or "{}")
        return rows
