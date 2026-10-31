"""DealPilot AI Email Dispatch and RFC-822 Deliverability Service.
Builds multipart HTML/Plain-text email payloads with tracking headers and preview inspection.
"""

import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Dict, Any, List
from ..database import get_connection

def generate_email_mime(customer_name: str, recipient_email: str, discount_code: str,
                        discount_amount: float, min_order: float, store_name: str) -> Dict[str, Any]:
    """Generates an RFC-822 compliant MIME email object with full deliverability headers."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Exclusive: ₹{int(discount_amount)} OFF your next visit at {store_name}!"
    msg["From"] = f"{store_name} via DealPilot AI <offers@sharmasweets.in>"
    msg["To"] = f"{customer_name} <{recipient_email}>"
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="sharmasweets.in")
    msg["X-Campaign-ID"] = f"DEALPILOT-RET-{discount_code}"
    msg["X-Mailer"] = "DealPilot Autonomous AI Engine v2.4"
    msg["List-Unsubscribe"] = "<mailto:unsubscribe@sharmasweets.in?subject=unsubscribe>"

    # Plain text version
    plain_text = f"""Hi {customer_name},

We missed you at {store_name}!
As a valued patron, here is an exclusive discount code for you:

PROMO CODE: {discount_code}
OFFER: ₹{int(discount_amount)} OFF on orders above ₹{int(min_order)}
VALIDITY: This weekend only (Till Sunday midnight)
HOW TO REDEEM: Simply scan our Paytm Soundbox QR code at Counter 1 or 2 when paying.

Sharma Sweets & Cafe, Connaught Place, New Delhi.
To unsubscribe, reply with 'STOP'.
"""

    # HTML Responsive Template
    html_text = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 0; padding: 0; background-color: #F8FAFC; color: #1E293B; }}
    .email-container {{ max-width: 580px; margin: 24px auto; background: #FFFFFF; border-radius: 12px; overflow: hidden; border: 1px solid #E2E8F0; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
    .header {{ background: #002E6E; padding: 24px 32px; text-align: center; color: #FFFFFF; }}
    .header h1 {{ margin: 0; font-size: 22px; font-weight: 800; }}
    .header p {{ margin: 6px 0 0 0; font-size: 13px; color: #00BAF2; }}
    .body-content {{ padding: 32px; }}
    .coupon-card {{ background: #F0F9FF; border: 2px dashed #00BAF2; border-radius: 10px; padding: 20px; text-align: center; margin: 24px 0; }}
    .coupon-code {{ font-size: 28px; font-weight: 800; color: #002E6E; letter-spacing: 2px; }}
    .coupon-desc {{ font-size: 15px; color: #0369A1; font-weight: 600; margin-top: 6px; }}
    .btn {{ display: inline-block; background: #00BAF2; color: #002E6E; text-decoration: none; font-weight: 800; padding: 12px 24px; border-radius: 6px; margin-top: 16px; }}
    .footer {{ background: #F1F5F9; padding: 18px 32px; font-size: 11.5px; color: #64748B; text-align: center; }}
  </style>
</head>
<body>
  <div class="email-container">
    <div class="header">
      <h1>{store_name}</h1>
      <p>Paytm Soundbox Verified Offer</p>
    </div>
    <div class="body-content">
      <h2 style="font-size: 18px; margin-top: 0;">Hi {customer_name},</h2>
      <p style="font-size: 14.5px; line-height: 1.6; color: #334155;">
        We noticed you haven't visited us for lunch recently! Our team prepared a special weekend treat just for you.
      </p>
      <div class="coupon-card">
        <div class="coupon-code">{discount_code}</div>
        <div class="coupon-desc">₹{int(discount_amount)} OFF on orders above ₹{int(min_order)}</div>
        <p style="font-size: 12px; color: #64748B; margin-bottom: 0;">Scan Paytm QR code at our counter to auto-apply</p>
      </div>
      <p style="font-size: 13.5px; color: #64748B;">
        Valid until this Sunday midnight. Cannot be combined with other offers.
      </p>
    </div>
    <div class="footer">
      Sharma Sweets & Cafe, Connaught Place, New Delhi · Powered by DealPilot AI<br>
      You are receiving this because you transacted with us previously. <a href="#unsubscribe" style="color: #64748B;">Unsubscribe</a>
    </div>
  </div>
</body>
</html>"""

    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_text, "html", "utf-8"))

    return {
        "headers": {k: v for k, v in msg.items()},
        "plain_text": plain_text,
        "html_text": html_text,
        "raw_mime": msg.as_string()
    }

def execute_batch_dispatch(workflow_id: str, limit: int = 240) -> Dict[str, Any]:
    """Simulates real dispatch of emails to the 240 cohort and logs each in the dispatches table."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
    wf = cur.fetchone()
    if not wf:
        conn.close()
        return {"status": "ERROR", "message": "Workflow not found"}

    cur.execute("SELECT * FROM customers WHERE merchant_id = ? ORDER BY quotation_value DESC, lifetime_value DESC LIMIT ?",
                (wf["merchant_id"], limit))
    customers = cur.fetchall()

    dispatched_count = 0
    for c in customers:
        disp_id = f"DISP-{c['customer_id']}"
        cur.execute("""
        INSERT OR REPLACE INTO dispatches (id, workflow_id, customer_id, channel,
                                           recipient_email, recipient_phone_masked, language_code,
                                           dispatch_status, delivery_receipt_id)
        VALUES (?, ?, ?, 'EMAIL', ?, ?, ?, 'DELIVERED', ?)
        """, (disp_id, workflow_id, c["customer_id"], c["email"], c["phone"], c["preferred_language"], f"RCPT-PAYTM-{c['customer_id']}"))
        dispatched_count += 1

    # Update roi_metrics
    cur.execute("""
    UPDATE roi_metrics
    SET total_delivered = ?, total_execution_cost_inr = ?
    WHERE workflow_id = ?
    """, (dispatched_count, dispatched_count * 0.40, workflow_id))

    conn.commit()
    conn.close()
    return {
        "status": "SUCCESS",
        "workflow_id": workflow_id,
        "dispatched_count": dispatched_count,
        "channel": "EMAIL_AND_WHATSAPP"
    }
