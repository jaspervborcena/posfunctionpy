"""
Local backfill script: Firestore orders -> BigQuery (prod)

Run from the functions/ directory:
    python backfill_orders.py

Optional args:
    --start 2025-01-01   Start date (inclusive). Default: all history.
    --end   2026-04-06   End date   (inclusive). Default: today.
    --dry-run            Print counts but don't insert.
    --store STORE_ID     Limit to one store.
"""
import sys
import argparse
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import bigquery
from google.oauth2 import service_account

# ── Config ──────────────────────────────────────────────────────────────────
SA_FILE          = "service-account.json"          # prod service account
BQ_PROJECT       = "jasperpos-1dfd5"
BQ_DATASET       = "tovrika_pos"
ORDERS_TABLE     = f"{BQ_PROJECT}.{BQ_DATASET}.orders"
FIRESTORE_COLL   = "orders"
BATCH_SIZE       = 200                             # rows per insert_rows_json call


# ── Helpers (mirror bigquery_triggers.py) ────────────────────────────────────
def ts_to_iso(val):
    if val is None:
        return None
    try:
        if isinstance(val, str):
            return val
        if isinstance(val, datetime):
            return val.isoformat()
        if hasattr(val, 'to_datetime'):
            return val.to_datetime().isoformat()
        if hasattr(val, 'ToDatetime'):
            return val.ToDatetime().isoformat()
        if isinstance(val, dict):
            if '_methodName' in val and val.get('_methodName') == 'serverTimestamp':
                return datetime.now(timezone.utc).isoformat()
            if 'seconds' in val:
                from datetime import timezone as tz
                dt = datetime.fromtimestamp(float(val['seconds']) + float(val.get('nanos', 0)) / 1e9, tz=tz.utc)
                return dt.isoformat()
            if '_seconds' in val:
                from datetime import timezone as tz
                dt = datetime.fromtimestamp(float(val['_seconds']) + float(val.get('_nanoseconds', 0)) / 1e9, tz=tz.utc)
                return dt.isoformat()
        if isinstance(val, (int, float)):
            v = float(val)
            dt = datetime.fromtimestamp(v / 1000.0 if v > 1e12 else v, tz=timezone.utc)
            return dt.isoformat()
    except Exception:
        pass
    try:
        return str(val)
    except Exception:
        return None


def normalize_status_history(entries):
    if not isinstance(entries, list):
        return []
    out = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        out.append({
            "status": entry.get("status"),
            "changedAt": ts_to_iso(entry.get("changedAt")),
            "changedBy": entry.get("changedBy"),
        })
    return [{k: v for k, v in e.items() if v is not None} for e in out]


def normalize_string_list(values):
    if not isinstance(values, list):
        return []
    return [str(v) for v in values if v is not None]


def clean_payload(obj):
    if isinstance(obj, dict):
        return {k: clean_payload(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [clean_payload(v) for v in obj]
    return obj


def build_order_payload(order_id, d):
    ci = d.get("customerInfo") or {}
    pm = d.get("payments") or {}
    payload = {
        "orderId":                 order_id,
        "assignedCashierEmail":    d.get("assignedCashierEmail"),
        "assignedCashierId":       d.get("assignedCashierId"),
        "assignedCashierName":     d.get("assignedCashierName"),
        "atpOrOcn":                d.get("atpOrOcn"),
        "birPermitNo":             d.get("birPermitNo"),
        "cashSale":                bool(d.get("cashSale", False)),
        "chargeSale":              bool(d.get("chargeSale", False)),
        "companyAddress":          d.get("companyAddress"),
        "companyEmail":            d.get("companyEmail"),
        "companyId":               d.get("companyId"),
        "companyName":             d.get("companyName"),
        "companyPhone":            d.get("companyPhone"),
        "companyTaxId":            d.get("companyTaxId"),
        "createdAt":               ts_to_iso(d.get("createdAt")),
        "createdBy":               d.get("createdBy"),
        "customerInfo": {
            "address":    ci.get("address"),
            "customerId": ci.get("customerId"),
            "fullName":   ci.get("fullName"),
            "tin":        ci.get("tin"),
            "uid":        ci.get("uid"),
        } if d.get("customerInfo") else None,
        "date":                    ts_to_iso(d.get("date")),
        "discountAmount":          float(d.get("discountAmount", 0)) if d.get("discountAmount") is not None else None,
        "grossAmount":             float(d.get("grossAmount", 0)) if d.get("grossAmount") is not None else None,
        "inclusiveSerialNumber":   d.get("inclusiveSerialNumber"),
        "invoiceNumber":           d.get("invoiceNumber") or order_id,
        "message":                 d.get("message"),
        "netAmount":               float(d.get("netAmount", 0)) if d.get("netAmount") is not None else None,
        "payments": {
            "amountTendered":    float(pm.get("amountTendered", 0)) if pm.get("amountTendered") is not None else 0,
            "changeAmount":      float(pm.get("changeAmount", 0)) if pm.get("changeAmount") is not None else 0,
            "paymentDescription": pm.get("paymentDescription"),
            "paymentType":       pm.get("paymentType"),
        } if d.get("payments") else None,
        "status":                  d.get("status", "active"),
        "statusHistory":           normalize_status_history(d.get("statusHistory")),
        "statusTags":              normalize_string_list(d.get("statusTags")),
        "storeId":                 d.get("storeId"),
        "tableNumber":             d.get("tableNumber"),
        "totalAmount":             float(d.get("totalAmount", 0)) if d.get("totalAmount") is not None else None,
        "uid":                     d.get("uid"),
        "updatedAt":               ts_to_iso(d.get("updatedAt")),
        "updatedBy":               d.get("updatedBy"),
        "vatAmount":               float(d.get("vatAmount", 0)) if d.get("vatAmount") is not None else None,
        "vatExemptAmount":         float(d.get("vatExemptAmount", 0)) if d.get("vatExemptAmount") is not None else None,
        "vatableSales":            float(d.get("vatableSales", 0)) if d.get("vatableSales") is not None else None,
        "zeroRatedSales":          float(d.get("zeroRatedSales", 0)) if d.get("zeroRatedSales") is not None else None,
    }
    return clean_payload(payload)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",   default=None, help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--end",     default=None, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument("--store",   default=None, help="Filter to a single storeId")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually insert")
    args = parser.parse_args()

    # ── Init Firebase Admin ──────────────────────────────────────────────────
    cred = credentials.Certificate(SA_FILE)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    # ── Init BigQuery ────────────────────────────────────────────────────────
    sa_creds = service_account.Credentials.from_service_account_file(
        SA_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    bq = bigquery.Client(project=BQ_PROJECT, credentials=sa_creds)

    # ── Fetch existing orderIds from BQ to avoid duplicates ─────────────────
    print("🔍 Fetching existing orderIds from BigQuery...")
    existing_ids = set()
    try:
        rows = bq.query(f"SELECT orderId FROM `{ORDERS_TABLE}`").result()
        for row in rows:
            existing_ids.add(row.orderId)
        print(f"   Found {len(existing_ids)} existing orders in BigQuery")
    except Exception as e:
        print(f"⚠️  Could not fetch existing IDs (table may be empty): {e}")

    # ── Fetch orders from Firestore ──────────────────────────────────────────
    print(f"📥 Fetching orders from Firestore collection '{FIRESTORE_COLL}'...")
    coll = db.collection(FIRESTORE_COLL)
    query = coll

    if args.start:
        start_dt = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
        query = query.where("createdAt", ">=", start_dt)
    if args.end:
        end_dt = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
        # end of the day
        from datetime import timedelta
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
        query = query.where("createdAt", "<=", end_dt)

    docs = list(query.stream())
    print(f"   Found {len(docs)} documents in Firestore")

    # ── Build payloads ───────────────────────────────────────────────────────
    to_insert = []
    skipped = 0
    for doc in docs:
        order_id = doc.id
        if order_id in existing_ids:
            skipped += 1
            continue
        d = doc.to_dict()
        if args.store and d.get("storeId") != args.store:
            skipped += 1
            continue
        payload = build_order_payload(order_id, d)
        to_insert.append(payload)

    print(f"   {len(to_insert)} to insert, {skipped} skipped (already in BQ or wrong store)")

    if args.dry_run:
        print("🔵 Dry run — no data written.")
        return

    if not to_insert:
        print("✅ Nothing to insert.")
        return

    # ── Batch insert ─────────────────────────────────────────────────────────
    table = bq.get_table(ORDERS_TABLE)
    inserted = 0
    errors = []

    for i in range(0, len(to_insert), BATCH_SIZE):
        batch = to_insert[i:i + BATCH_SIZE]
        errs = bq.insert_rows_json(table, batch)
        if errs:
            for e in errs:
                errors.append(e)
                print(f"❌ Insert error: {e}")
        else:
            inserted += len(batch)
            print(f"   ✅ Inserted batch {i // BATCH_SIZE + 1}: {len(batch)} rows (total so far: {inserted})")

    print(f"\n{'='*50}")
    print(f"✅ Done. Inserted: {inserted} | Errors: {len(errors)}")
    if errors:
        print("❌ Errors:")
        for e in errors:
            print(f"   {e}")


if __name__ == "__main__":
    main()
