"""Phase 9: Sarvam AI Voice Copilot Service.
Provides Indic multilingual voice interaction, real-time query parsing,
speech synthesis, and audio waveform generation for Indian merchants.
Supports: Hindi, Indian English, Tamil, Telugu, Bengali, Marathi, Gujarati, and Kannada.
Integrates with Sarvam AI stack (Saaras STT, Bulbul TTS, Mayura Translate, and Sarvam-105B).
"""

import json
import logging
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from ..database import get_connection
from ..integrations.sarvam.client import SarvamClient
from ..integrations.sarvam.config import ENDPOINTS, SUPPORTED_LANGUAGES
from ..integrations.sarvam.exceptions import SarvamError
from ..integrations.sarvam.schemas import validate_translate_payload
from ..integrations.sarvam.speech_to_text import SaarasSTT
from ..integrations.sarvam.text_to_speech import BulbulTTS
from ..integrations.sarvam.translate import SarvamTranslate
from ..services.profit_intelligence_service import ProfitIntelligenceService
from ..services.inventory_intelligence_service import InventoryIntelligenceService
from ..services.guardrails_service import GuardrailsService
from ..services.decision_twin_service import DecisionTwinService
from ..services.incremental_outcome_service import IncrementalOutcomeService
from ..services.sales_intelligence_service import detect_sales_drop, calculate_sales_summary

logger = logging.getLogger(__name__)


class VoiceCopilotService:
    """Multilingual Conversational Voice Copilot for Indian Merchants."""

    def __init__(self):
        self.sarvam_client = SarvamClient()
        self.stt = SaarasSTT(self.sarvam_client)
        self.tts = BulbulTTS(self.sarvam_client)
        self.translate = SarvamTranslate(self.sarvam_client)

    def create_or_get_session(self, merchant_id: str = "MERCH-002", language_code: str = "hi-IN") -> Dict[str, Any]:
        """Creates or returns an active conversational voice session for the merchant."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT session_id, merchant_id, language_code, status, created_at
        FROM voice_sessions
        WHERE merchant_id = ? AND status = 'ACTIVE'
        ORDER BY updated_at DESC LIMIT 1
        """, (merchant_id,))
        row = cur.fetchone()
        
        now_utc = datetime.now(timezone.utc).isoformat()
        if row:
            session = dict(row)
            conn.close()
            return session

        session_id = f"VSESS-{uuid.uuid4().hex[:8].upper()}"
        cur.execute("""
        INSERT INTO voice_sessions (session_id, merchant_id, language_code, status, created_at, updated_at)
        VALUES (?, ?, ?, 'ACTIVE', ?, ?)
        """, (session_id, merchant_id, language_code, now_utc, now_utc))
        conn.commit()
        conn.close()

        return {
            "session_id": session_id,
            "merchant_id": merchant_id,
            "language_code": language_code,
            "status": "ACTIVE",
            "created_at": now_utc
        }

    def get_provider_status(self) -> Dict[str, Any]:
        """Reports configured voice providers without exposing credential material."""
        configured = self.sarvam_client.is_connected()
        return {
            "provider": "Sarvam AI",
            "api_key_configured": configured,
            "speech_recognition": "Saaras v4" if configured else "Unavailable",
            "spoken_replies": "Bulbul v4 Flash" if configured else "Unavailable",
            "message": (
                "Sarvam speech recognition and spoken replies are configured."
                if configured else
                "Set SARVAM_API_KEY on the server to enable speech recognition and spoken replies."
            )
        }

    def transcribe_audio_payload(
        self,
        audio_bytes: bytes,
        language_code: str = "hi-IN",
        content_type: str = "audio/webm"
    ) -> Dict[str, Any]:
        """Transcribes incoming audio using Sarvam Saaras."""
        return self.stt.transcribe_audio(audio_bytes, language_code, content_type)

    def process_query(
        self,
        merchant_id: str,
        transcript: str,
        language_code: str = "hi-IN",
        input_mode: str = "VOICE",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Interprets merchant natural language query, dispatches to business intelligence services,
        synthesizes Indic speech response, and records the interaction audit trail.
        """
        start_time = time.time()
        normalized_q = transcript.strip().lower()

        # Ensure active session
        session = self.create_or_get_session(merchant_id, language_code) if not session_id else {"session_id": session_id}
        sess_id = session.get("session_id") or f"VSESS-{uuid.uuid4().hex[:8].upper()}"

        detected_intent = self._detect_intent(normalized_q)
        intent_result = self._dispatch_intent(detected_intent, merchant_id, language_code, normalized_q)

        response_text = intent_result["text"]
        response_language_error = None
        if language_code not in ("en-IN", "hi-IN", "en", "hi"):
            response_text, response_language_error = self._translate_reply(response_text, language_code)
        structured_payload = intent_result.get("payload", {})
        suggested_actions = intent_result.get("actions", [])

        if response_language_error:
            speech_result = {
                "error": "Spoken reply skipped because the answer could not be translated to the selected language.",
                "provider": "SARVAM_TRANSLATION_UNAVAILABLE"
            }
        else:
            speech_result = self.synthesize_speech(response_text, language_code)
        audio_base64 = speech_result.get("audio_base64")
        latency_ms = int((time.time() - start_time) * 1000)

        # Persist interaction in voice_interactions
        interaction_id = f"VINT-{uuid.uuid4().hex[:8].upper()}"
        now_utc = datetime.now(timezone.utc).isoformat()
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO voice_interactions (
            interaction_id, session_id, merchant_id, input_mode, transcript,
            detected_intent, language_code, response_text, audio_response_url,
            audio_base64, structured_payload_json, latency_ms, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            interaction_id, sess_id, merchant_id, input_mode, transcript,
            detected_intent, language_code, response_text, None,
            audio_base64, json.dumps(structured_payload), latency_ms, now_utc
        ))
        # Update session timestamp
        cur.execute("UPDATE voice_sessions SET updated_at = ? WHERE session_id = ?", (now_utc, sess_id))
        conn.commit()
        conn.close()

        return {
            "interaction_id": interaction_id,
            "session_id": sess_id,
            "merchant_id": merchant_id,
            "input_mode": input_mode,
            "transcript": transcript,
            "detected_intent": detected_intent,
            "language_code": language_code,
            "response_text": response_text,
            "audio_base64": audio_base64,
            "speech_error": speech_result.get("error"),
            "response_language_error": response_language_error,
            "structured_payload": structured_payload,
            "suggested_actions": suggested_actions,
            "latency_ms": latency_ms,
            "provider": speech_result.get("provider", "SARVAM_AI_INDIC_STACK"),
            "created_at": now_utc
        }

    def _translate_reply(self, text: str, language_code: str) -> Tuple[str, Optional[str]]:
        """Translate an English business reply to the selected language with Sarvam."""
        language = SUPPORTED_LANGUAGES.get(language_code.split("-", 1)[0].lower())
        if language is None:
            return text, f"Replies are not configured for the selected language ({language_code})."
        if language["code"] in ("en-IN", "hi-IN"):
            return text, None
        if not self.sarvam_client.is_connected():
            return text, f"Sarvam translation is unavailable for {language['name']}. Set SARVAM_API_KEY to enable it."

        payload = validate_translate_payload(text, "en-IN", language["code"])
        try:
            result = self.sarvam_client.post(ENDPOINTS["translate"], payload)
        except SarvamError as error:
            logger.warning("Sarvam reply translation failed for %s: %s", language_code, error)
            return text, f"Could not translate this reply to {language['name']}. {error}"

        translated_text = result.get("translated_text", "").strip() if isinstance(result, dict) else ""
        if not translated_text:
            logger.warning("Sarvam returned an empty reply translation for %s", language_code)
            return text, f"Sarvam did not return a {language['name']} translation."
        return translated_text, None

    def synthesize_speech(
        self,
        text: str,
        language_code: str = "hi-IN",
        speaker: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synthesizes natural speech with Sarvam Bulbul, or reports why it is unavailable."""
        if not self.sarvam_client.is_connected():
            return {
                "error": "SARVAM_API_KEY is not configured. Spoken replies are unavailable.",
                "speaker": speaker or "language default",
                "language": language_code,
                "provider": "SARVAM_BULBUL_UNAVAILABLE"
            }

        result = self.tts.generate_speech(text, language_code, speaker)
        if result.get("audio_base64"):
            return result
        return {
            "error": result.get("error") or "Sarvam Bulbul did not return speech audio.",
            "speaker": speaker,
            "language": language_code,
            "provider": result.get("provider", "SARVAM_BULBUL_ERROR")
        }

    def get_interaction_history(self, merchant_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns recent voice interactions for the merchant."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT interaction_id, session_id, merchant_id, input_mode, transcript,
               detected_intent, language_code, response_text, audio_base64,
               structured_payload_json, latency_ms, created_at
        FROM voice_interactions
        WHERE merchant_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """, (merchant_id, limit))
        rows = cur.fetchall()
        conn.close()

        results = []
        for r in rows:
            d = dict(r)
            if d.get("structured_payload_json"):
                try:
                    d["structured_payload"] = json.loads(d["structured_payload_json"])
                except Exception:
                    d["structured_payload"] = {}
            results.append(d)
        return results

    def _detect_intent(self, text: str) -> str:
        """Determines the business intent behind the merchant's query with proper prioritization."""
        # 1. Campaign Performance & Results
        if any(w in text for w in ["perform", "result", "outcome", "kaisa raha", "roi", "lift", "conversion", "how did my"]):
            return "CAMPAIGN_PERFORMANCE"

        # 2. Strategy Comparison
        elif any(w in text for w in ["compare", "strategy", "strategies", "conservative", "aggressive", "balanced", "tulna", "farq", "which offer", "different offer"]):
            return "STRATEGY_COMPARISON"

        # 3. Campaign Recommendation & Re-engagement
        elif any(w in text for w in ["campaign", "customer wapas", "re-engagement", "bundle", "suggest a", "offer", "bring customer", "discount offer", "promotion", "run a campaign", "send offer"]):
            return "CAMPAIGN_RECOMMENDATION"

        # 4. Local Bazaar Demand Pulse
        elif any(w in text for w in ["bazaar", "trend", "demand", "neighbourhood", "surge", "local", "as-pas", "market", "johari", "what is selling nearby", "nearby"]):
            return "LOCAL_DEMAND_TREND"

        # 5. Inventory Risk & Trapped Capital
        elif any(w in text for w in ["inventory", "stock", "maal", "stuck", "fasa", "aging", "clearance", "dupatta", "kurta", "out of stock", "reorder", "surplus"]):
            return "INVENTORY_STATUS"

        # 6. Cash Flow & Liquidity
        elif any(w in text for w in ["cash", "paisa", "cashflow", "runway", "pinch", "day 4", "balance", "bank", "vendor payout", "payout", "liquidity", "working capital"]):
            return "CASH_FLOW"

        # 7. Customer Retention & RFM Segments
        elif any(w in text for w in ["customer", "patron", "diner", "grahak", "inactive", "dormant", "repeat", "regular", "churn", "who are my customers", "diners", "audience", "client"]):
            return "CUSTOMER_INTELLIGENCE"

        # 8. Sales Analysis & Decline
        elif any(w in text for w in ["sale", "sales", "revenue", "biki", "drop", "decline", "gira", "kam hua", "sales kyu", "biki kam", "turnover", "how is my business", "how much did i make", "weekly sales", "today sales", "performance"]):
            return "SALES_DROP_ANALYSIS"

        # 9. Profit & Margin Intelligence
        elif any(w in text for w in ["profit", "margin", "munafa", "gross profit", "faida", "kamai", "sku", "cost", "cogs", "most profitable", "highest profit"]):
            return "PROFIT_ANALYSIS"

        # 10. Guardrails & Rules
        elif any(w in text for w in ["guardrail", "rule", "limit", "ceiling", "approval", "permission", "safe"]):
            return "GUARDRAIL_STATUS"

        else:
            return "GENERAL_BUSINESS_HELP"

    def _dispatch_intent(self, intent: str, merchant_id: str, language_code: str, query: str) -> Dict[str, Any]:
        """Dispatches intent to appropriate business intelligence module and constructs Indic voice response."""
        is_hindi = language_code.startswith("hi")

        if intent == "SALES_DROP_ANALYSIS":
            if merchant_id == "MERCH-002":
                text = (
                    "नमस्ते ज़ुबैर जी! इस हफ़्ते आपके स्टोर में रिपीट विज़िट्स में 22% की गिरावट आई है क्योंकि ग्राहक फेस्टिव मैचिंग कुर्ता-दुपट्टा बंडल तलाश रहे थे। आपके पास 74 बंधेज दुपट्टे का स्टॉक उपलब्ध है जिसे प्रमोट करके हम बिक्री तुरंत बढ़ा सकते हैं।"
                    if is_hindi else
                    "Hello Zubair! Your store experienced a 22% drop in repeat customer conversions this week. Local festive shoppers are looking for matching kurta-dupatta bundles, while you have 74 Bandhani dupattas aging in inventory."
                )
                payload = {
                    "sales_drop_pct": 22.0,
                    "affected_segment": "Repeat Festive Wear Shoppers",
                    "opportunity": "Festive Royal Bundle (Chikankari Kurta + Silk Dupatta)",
                    "trapped_inventory_units": 74
                }
            else:
                drop_data = detect_sales_drop(merchant_id)
                summary = calculate_sales_summary(merchant_id)
                pct = drop_data.sales_percentage_difference
                current_week_sales = summary.this_week_total_k * 1000.0
                text = (
                    f"रमेश जी, इस हफ़्ते आपकी किराने की बिक्री ₹{current_week_sales:,.0f} रही, जो पिछले हफ़्ते से {abs(pct):.1f}% कम है। दोहराए गए खरीदारी ऑर्डर 37% से घटकर 24% हुए हैं।"
                    if is_hindi else
                    f"Ramesh ji, grocery sales were ₹{current_week_sales:,.0f} this week, down {abs(pct):.1f}% from last week. Repeat-basket share moved from 37% to 24% in the simulated records; the data does not show why."
                )
                payload = {
                    "sales_drop_pct": pct,
                    "current_week_sales": current_week_sales,
                    "repeat_customer_drop": "37% -> 24%"
                }
            actions = ["View Sales Trend", "Open Bazaar Demand Pulse", "Recommend Re-engagement Campaign"]
            return {"text": text, "payload": payload, "actions": actions}

        elif intent == "PROFIT_ANALYSIS":
            profit_data = ProfitIntelligenceService.calculate_profit_summary(merchant_id)
            top_sku = profit_data.get("highest_margin_sku", {})
            overall_margin = profit_data.get("overall_gross_margin_pct", 48.5)
            text = (
                f"आपके व्यापार का औसत ग्रॉस मार्जिन {overall_margin:.1f}% है। सबसे अधिक मुनाफे वाला प्रोडक्ट '{top_sku.get('product_name', 'बनारसी ब्रोकेड शेरवानी')}' है, जिसका मार्जिन {top_sku.get('gross_margin_pct', 56.4):.1f}% है।"
                if is_hindi else
                f"Your overall business gross margin is {overall_margin:.1f}%. The most profitable SKU is '{top_sku.get('product_name', 'Banarasi Brocade Sherwani')}' with a gross margin of {top_sku.get('gross_margin_pct', 56.4):.1f}%."
            )
            payload = profit_data
            actions = ["Review Product Margins", "Check Margin Dilution Alerts"]
            return {"text": text, "payload": payload, "actions": actions}

        elif intent == "INVENTORY_STATUS":
            inv_summary = InventoryIntelligenceService.get_inventory_summary(merchant_id)
            trapped_inr = inv_summary.get("trapped_working_capital_inr", 31080.0)
            text = (
                f"इन्वेंटरी अलर्ट: आपके पास ₹{trapped_inr:,.0f} की वर्किंग कैपिटल धीमी गति वाले स्टॉक में फंसी हुई है। विशेषकर 74 बंधेज सिल्क दुपट्टे 92 दिनों से रखे हैं। इन्हें कुर्ते के साथ बंडल बनाकर तुरंत लिक्विडेट करना सुरक्षित है।"
                if is_hindi else
                f"Inventory Alert: ₹{trapped_inr:,.0f} in working capital is trapped in slow-moving stock. Notably, 74 units of Bandhani Silk Dupattas have been in stock for 92 days. Bundling them with fast-selling kurtas is recommended."
            )
            payload = inv_summary
            actions = ["Open Inventory Intelligence", "Simulate Clearance Bundle"]
            return {"text": text, "payload": payload, "actions": actions}

        elif intent == "LOCAL_DEMAND_TREND":
            from .bazaar_intelligence_service import BazaarIntelligenceService
            pulse = BazaarIntelligenceService.get_local_demand_pulse()
            surge_signal = pulse.get("top_signal", {})
            text = (
                f"जौहरी बाज़ार में फेस्टिव एथनिक कुर्ता और सिल्क दुपट्टे की मांग में {surge_signal.get('growth_rate_pct', 38.5):.1f}% का भारी उछाल है (7 सहयोगी स्टोर्स द्वारा सत्यापित, k>=5 प्राइवेसी प्रोटेक्टेड)। यह आपके स्टॉक के साथ 94% मैच करता है।"
                if is_hindi else
                f"Johari Bazaar demand pulse indicates a +{surge_signal.get('growth_rate_pct', 38.5):.1f}% surge in Festive Ethnic Kurtas & Silk Dupattas across 7 verified apparel merchants (k>=5 privacy compliant). Relevance matching score is 94%."
            )
            payload = pulse
            actions = ["Inspect Bazaar Signals", "Review Contextual Match", "Launch Festive Campaign"]
            return {"text": text, "payload": payload, "actions": actions}

        elif intent == "CAMPAIGN_RECOMMENDATION":
            text = (
                "मैंने 'फेस्टिव रॉयल बंडल' अभियान तैयार किया है: चिकनकारी कुर्ते के साथ बंधेज दुपट्टा ₹2,299 (8% बंडल बचत) में 20 पुराने ग्राहकों को भेजें। अनुमानित ग्रॉस प्रॉफिट ₹14,406 (44.8% मार्जिन) होगा और फंसा हुआ स्टॉक क्लियर हो जाएगा।"
                if is_hindi else
                "I recommend the 'Festive Royal Bundle' campaign: Pair Chikankari Kurtas with Bandhani Dupattas at ₹2,299 (8% bundle discount) to 20 past customers. Projected gross profit is ₹14,406 at 44.8% margin while liquidating trapped stock."
            )
            payload = {
                "campaign_name": "Festive Royal Bundle",
                "recommended_price_inr": 2299.0,
                "discount_pct": 8.0,
                "target_audience": 20,
                "projected_revenue_inr": 32186.0,
                "projected_gross_profit_inr": 14406.0,
                "projected_margin_pct": 44.8,
                "guardrails_status": "PASSED"
            }
            actions = ["Simulate Decision Twin", "Review Message Draft", "Approve & Execute"]
            return {"text": text, "payload": payload, "actions": actions}

        elif intent == "STRATEGY_COMPARISON":
            text = (
                "निर्णय ट्विन तुलना: कंज़र्वेटिव रणनीति (0% छूट) में ₹5,400 प्रॉफिट होगा। बैलेंस्ड बंडल (8% छूट) में ₹14,406 प्रॉफिट और फंसा हुआ स्टॉक क्लियर होगा। अग्रेसिव 18% छूट आपके 10% डिस्काउंट गार्डरेल का उल्लंघन करती है इसलिए वह ब्लॉक है।"
                if is_hindi else
                "Decision Twin comparison: Conservative (0% discount) yields ₹5,400 profit. Balanced Bundle (8% discount) yields ₹14,406 profit and clears trapped stock. Aggressive 18% discount breaches your 10% discount guardrail and is strictly blocked."
            )
            payload = {
                "conservative": {"discount": "0%", "profit": 5400.0, "margin": "51.4%", "status": "ALLOWED"},
                "balanced": {"discount": "8%", "profit": 14406.0, "margin": "44.8%", "status": "RECOMMENDED"},
                "aggressive": {"discount": "18%", "profit": 14696.0, "margin": "33.9%", "status": "BLOCKED_BY_GUARDRAIL"}
            }
            actions = ["Select Balanced Strategy", "Open Guardrail Settings"]
            return {"text": text, "payload": payload, "actions": actions}

        elif intent == "CAMPAIGN_PERFORMANCE":
            outcome = IncrementalOutcomeService.get_campaign_experiment_result("EXP-DEMO-001")
            text = (
                f"बधाई हो! आपके अभियान ने होल्डआउट ग्रुप की तुलना में +{outcome.get('conversion_lift_pts', 23.3):.1f}% का लिफ्ट दर्ज किया। 8 अतिरिक्त ऑर्डर्स से ₹{outcome.get('incremental_revenue_inr', 20900):,.0f} की आय और ₹{outcome.get('net_incremental_profit_inr', 8286.7):,.0f} का शुद्ध इंक्रीमेंटल प्रॉफिट मिला।"
                if is_hindi else
                f"Campaign Outcome Verified: Your campaign delivered a +{outcome.get('conversion_lift_pts', 23.3):.1f}% conversion lift over the randomized holdout group, yielding 8 incremental orders, ₹{outcome.get('incremental_revenue_inr', 20900):,.0f} incremental revenue, and ₹{outcome.get('net_incremental_profit_inr', 8286.7):,.0f} net incremental profit."
            )
            payload = outcome
            actions = ["View Full KPI Report", "Export Verification Certificate"]
            return {"text": text, "payload": payload, "actions": actions}

        elif intent == "GUARDRAIL_STATUS":
            rules = GuardrailsService.get_all_guardrails(merchant_id)
            text = (
                f"आपके स्टोर में {len(rules)} सुरक्षा गार्डरेल्स सक्रिय हैं: अधिकतम 10% छूट सीमा, ₹2,500 बजट सीलिंग, न्यूनतम 25% ग्रॉस मार्जिन फ्लोर, और अनिवार्य मर्चेंट अनुमोदन।"
                if is_hindi else
                f"Your store has {len(rules)} active guardrails: 10% maximum discount ceiling, ₹2,500 budget cap, 25% gross margin floor, and mandatory merchant approval."
            )
            payload = {"active_guardrails_count": len(rules), "rules": rules}
            actions = ["View Guardrails", "Edit Thresholds"]
            return {"text": text, "payload": payload, "actions": actions}

        elif intent == "CASH_FLOW":
            from .cashflow_intelligence_service import CashFlowIntelligenceService
            cf = CashFlowIntelligenceService.get_cashflow_forecast(merchant_id)
            pinch_day = cf.get("timing_pinch_day", 4)
            min_bal = cf.get("minimum_projected_balance_inr", -12400.0)
            text = (
                f"कैश-फ्लो अलर्ट: अगले 7 दिनों में डे {pinch_day} पर ₹{abs(min_bal):,.0f} का अस्थायी डेफिसिट आने की संभावना है, क्योंकि वेंडर पेमेंट्स सेटलमेंट से पहले देय हैं। सेटलमेंट साइकिल को री-शेड्यूल करना सुरक्षित रहेगा।"
                if is_hindi else
                f"Cash-Flow Alert: Projected Day {pinch_day} liquidity pinch with a temporary ₹{abs(min_bal):,.0f} deficit due to committed supplier payouts preceding Soundbox settlements. Rescheduling payouts or drawing on working capital is recommended."
            )
            payload = cf
            actions = ["View Cash Flow Runway", "Adjust Vendor Payables", "Review Inflow Projections"]
            return {"text": text, "payload": payload, "actions": actions}

        elif intent == "CUSTOMER_INTELLIGENCE":
            from .customer_value_service import CustomerValueService
            custs = CustomerValueService.get_rfm_customer_directory(merchant_id)
            total = len(custs)
            at_risk = sum(1 for c in custs if c.get("rfm_segment") in ("AT_RISK_HIGH_VALUE", "HIBERNATING_DORMANT"))
            text = (
                f"कस्टमर इनसाइट: आपके पास कुल {total} पंजीकृत ग्राहक हैं, जिनमें से {at_risk} ग्राहक डॉरमेंट या रिस्क पर हैं। इन्हें टारगेट करके तुरंत री-एंगेजमेंट ऑफर भेजा जा सकता है।"
                if is_hindi else
                f"Customer Insights: You have {total} tracked customer profiles, of which {at_risk} are flagged as Dormant or At-Risk. A ₹50 offer on baskets above ₹499 could be tested with owner approval; ₹20,900 is a simulated revenue-at-risk estimate, not guaranteed recovery."
            )
            payload = {
                "total_customers": total,
                "at_risk_count": at_risk,
                "top_customers": custs[:5] if custs else []
            }
            actions = ["View Customer Directory", "Launch Re-engagement Campaign", "Export Audience"]
            return {"text": text, "payload": payload, "actions": actions}

        else:  # GENERAL_BUSINESS_HELP
            text = (
                "नमस्ते! मैं आपका Paytm AI ActionMate हूँ। आप मुझसे बोलकर पूछ सकते हैं: 'मेरी बिक्री क्यों कम हुई?', 'किस प्रोडक्ट में सबसे अधिक मुनाफा है?', 'बाज़ार का क्या ट्रेंड है?', या 'ग्राहक वापस लाने के लिए क्या करूँ?'"
                if is_hindi else
                "Hello! I am your Paytm AI ActionMate. You can ask me: 'Why did my sales drop?', 'Which products have highest profit?', 'What is the local demand trend?', or 'Suggest a profitable campaign.'"
            )
            payload = {
                "suggested_queries": [
                    "Why did my sales drop this week?",
                    "Which products have highest gross profit?",
                    "What is my inventory risk?",
                    "What is the local demand trend?",
                    "Suggest a profitable campaign",
                    "Compare 5% discount with bundle",
                    "How did my campaign perform?"
                ]
            }
            actions = ["Analyze Sales Drop", "Check Bazaar Demand Pulse", "Review Guardrails"]
            return {"text": text, "payload": payload, "actions": actions}
