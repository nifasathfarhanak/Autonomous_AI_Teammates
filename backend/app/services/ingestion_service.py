"""DealPilot AI Stage 1: Customer Data Ingestion Service.
Parses CSV uploads, validates required schemas, identifies duplicates and missing fields,
and provides preview metrics before committing to the database.
"""

import csv
import io
import re
from typing import Dict, Any, List, Tuple
from ..database import get_connection

REQUIRED_FIELDS = [
    "customer_id", "customer_name", "email", "company", "phone",
    "last_purchase_date", "last_purchase_value", "lifetime_value",
    "interested_product", "last_interaction_date", "quotation_status",
    "quotation_value", "preferred_language"
]

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def parse_and_validate_csv(csv_content: str, merchant_id: str = "MERCH-001", commit: bool = False) -> Dict[str, Any]:
    """Parses raw CSV string, validates each record against rules, and optionally commits."""
    reader = csv.DictReader(io.StringIO(csv_content.strip()))
    
    total_records = 0
    valid_records = []
    duplicate_records = []
    invalid_records = []
    missing_info_count = 0

    conn = get_connection()
    cur = conn.cursor()

    # Preload existing IDs and emails for duplicate detection
    cur.execute("SELECT customer_id, email FROM customers WHERE merchant_id = ?", (merchant_id,))
    existing_rows = cur.fetchall()
    existing_ids = {r["customer_id"] for r in existing_rows}
    existing_emails = {r["email"].lower() for r in existing_rows}

    seen_in_batch_ids = set()
    seen_in_batch_emails = set()

    for idx, row in enumerate(reader, start=1):
        total_records += 1
        cid = (row.get("customer_id") or "").strip()
        cname = (row.get("customer_name") or "").strip()
        email = (row.get("email") or "").strip().lower()

        # Check essential required fields
        if not cid or not cname or not email:
            invalid_records.append({
                "row_number": idx,
                "customer_id": cid,
                "error": "Missing mandatory primary identifier (customer_id, customer_name, or email)"
            })
            continue

        if not EMAIL_REGEX.match(email):
            invalid_records.append({
                "row_number": idx,
                "customer_id": cid,
                "error": f"Malformed email address: '{email}'"
            })
            continue

        # Check duplicate
        if cid in existing_ids or cid in seen_in_batch_ids or email in existing_emails or email in seen_in_batch_emails:
            duplicate_records.append({
                "row_number": idx,
                "customer_id": cid,
                "email": email,
                "reason": "Duplicate customer_id or email already exists in system"
            })
            continue

        seen_in_batch_ids.add(cid)
        seen_in_batch_emails.add(email)

        # Parse numeric & date fields
        try:
            last_pur_val = float(row.get("last_purchase_value", 0.0) or 0.0)
            ltv = float(row.get("lifetime_value", 0.0) or 0.0)
            q_val = float(row.get("quotation_value", 0.0) or 0.0)
        except ValueError:
            invalid_records.append({
                "row_number": idx,
                "customer_id": cid,
                "error": "Non-numeric values in financial fields"
            })
            continue

        # Missing field checks for soft warnings
        if not row.get("phone") or not row.get("interested_product") or not row.get("last_purchase_date"):
            missing_info_count += 1

        clean_record = {
            "customer_id": cid,
            "merchant_id": merchant_id,
            "customer_name": cname,
            "email": email,
            "company": (row.get("company") or "Independent").strip(),
            "phone": (row.get("phone") or "+91 00000-00000").strip(),
            "last_purchase_date": (row.get("last_purchase_date") or "").strip(),
            "last_purchase_value": last_pur_val,
            "lifetime_value": ltv,
            "interested_product": (row.get("interested_product") or "General Inquiry").strip(),
            "last_interaction_date": (row.get("last_interaction_date") or row.get("last_purchase_date") or "").strip(),
            "quotation_status": (row.get("quotation_status") or "NONE").strip().upper(),
            "quotation_value": q_val,
            "preferred_language": (row.get("preferred_language") or "en").strip().lower()
        }
        valid_records.append(clean_record)

    # If commit requested, insert into SQLite
    if commit and valid_records:
        for r in valid_records:
            cur.execute("""
            INSERT OR REPLACE INTO customers (
                customer_id, merchant_id, customer_name, email, company, phone,
                last_purchase_date, last_purchase_value, lifetime_value,
                interested_product, last_interaction_date, quotation_status,
                quotation_value, preferred_language, is_unsubscribed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                r["customer_id"], r["merchant_id"], r["customer_name"], r["email"],
                r["company"], r["phone"], r["last_purchase_date"], r["last_purchase_value"],
                r["lifetime_value"], r["interested_product"], r["last_interaction_date"],
                r["quotation_status"], r["quotation_value"], r["preferred_language"]
            ))
        conn.commit()

    conn.close()

    return {
        "total_records": total_records,
        "successfully_imported": len(valid_records) if commit else 0,
        "valid_preview_count": len(valid_records),
        "duplicate_count": len(duplicate_records),
        "invalid_count": len(invalid_records),
        "records_with_missing_optional_fields": missing_info_count,
        "duplicates": duplicate_records,
        "invalid_records": invalid_records,
        "preview_records": valid_records[:5],
        "is_committed": commit
    }

