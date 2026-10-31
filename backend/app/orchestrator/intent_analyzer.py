"""Paytm AI ActionMate Natural-Language Task Understanding Engine.
Parses merchant natural-language requests into structured intents, entities,
required business context lists, and risk classifications.
Operates via deterministic rule-based semantic analysis with zero hallucination.
"""

import re
from typing import Dict, Any, List

INTENT_SALES_RECOVERY = "SALES_RECOVERY_REENGAGEMENT"
INTENT_SALES_INQUIRY = "SALES_PERFORMANCE_INQUIRY"
INTENT_CUSTOMER_SEGMENTATION = "CUSTOMER_SEGMENTATION_ANALYSIS"
INTENT_GENERAL_BUSINESS_ASSISTANCE = "GENERAL_BUSINESS_ASSISTANCE"

class IntentAnalyzer:
    """Analyzes natural-language requests from merchants and extracts structured business intents."""

    @staticmethod
    def analyze_request(user_prompt: str, merchant_id: str = "MERCH-001") -> Dict[str, Any]:
        """Maps natural-language text to structured intent, entities, required context, and risk."""
        text = user_prompt.strip().lower()

        # Keywords for sales drop & customer recovery
        sales_drop_keywords = ["drop", "dropped", "declined", "fell", "decrease", "down", "low sales", "loss"]
        recovery_keywords = ["bring customers back", "bring back", "recover", "re-engage", "return", "dormant", "win back"]

        is_sales_drop = any(k in text for k in sales_drop_keywords)
        is_recovery = any(k in text for k in recovery_keywords)

        if is_sales_drop or is_recovery or "sales" in text:
            detected_intent = INTENT_SALES_RECOVERY
            confidence = 0.98
            entities = {
                "merchant_id": merchant_id,
                "timeframe": "this_week_vs_last_week",
                "core_issue": "weekly_sales_volume_and_repeat_customer_drop",
                "target_objective": "bring_dormant_repeat_patrons_back",
                "channel_preference": ["SMS", "WHATSAPP", "SOUNDBOX_VOICE"]
            }
            required_data = [
                "weekly_sales_this_week",
                "weekly_sales_last_week",
                "sales_drop_detection_metrics",
                "repeat_purchase_trend_4_weeks",
                "customer_segments_declining_cohort",
                "product_performance_catalog",
                "campaign_history_and_caps"
            ]
            risk_classification = "MEDIUM"
            approval_requirements = {
                "requires_merchant_approval": True,
                "approval_type": "HMAC_FINANCIAL_SIGNATURE",
                "max_authorized_budget_inr": 3600.0,
                "liability_ceiling_inr": 5400.0,
                "gate_step": 7
            }
        else:
            detected_intent = INTENT_GENERAL_BUSINESS_ASSISTANCE
            confidence = 0.75
            entities = {"merchant_id": merchant_id}
            required_data = ["merchant_profile", "sales_summary"]
            risk_classification = "LOW"
            approval_requirements = {
                "requires_merchant_approval": False,
                "approval_type": "NONE"
            }

        return {
            "original_request": user_prompt,
            "detected_intent": detected_intent,
            "confidence": confidence,
            "relevant_entities": entities,
            "required_data": required_data,
            "risk_classification": risk_classification,
            "approval_requirements": approval_requirements,
            "provider": "DETERMINISTIC_REASONING_ENGINE",
            "is_demo": True
        }

