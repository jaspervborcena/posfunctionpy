"""
Local backfill script: Firestore ordersSellingTracking -> BigQuery (prod)

Run from the functions/ directory:
    python backfill_ost.py

Optional args:
    --start 2025-01-01   Start date (inclusive, filters on createdAt). Default: all history.
    --end   2026-04-06   End date   (inclusive). Default: today.
    --dry-run            Print counts but don't insert.
"""
import sys
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import bigquery
from google.oauth2 import service_account

# ── Config ──────────────────────────────────────────────────────────────────
SA_FILE      = "service-account.json"
BQ_PROJECT   = "jasperpos-1dfd5"
BQ_DATASET   = "tovrika_pos"
OST_TABLE    = f"{BQ_PROJECT}.{BQ_DATASET}.ordersSellingTracking"
FIRESTORE_COLL = "ordersSellingTracking"
BATCH_SIZE   = 200


# ── Helpers ──────────────────────────────────────────────────────────────────
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
            if 'seconds' in val:
                dt = datetime.fromtimestamp(float(val['seconds']) + float(val.get('nanos', 0)) / 1e9, tz=timezone.utc)
                return dt.isoformat()
            if '_seconds' in val:
                dt = datetime.fromtimestamp(float(val['_seconds']) + float(val.get('_nanoseconds', 0)) / 1e9, tz=timezone.utc)
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


def to_int(v):
    try:
        return int(v) if v is not None else None
    except Exception:
        return None


def to_numeric(v):
    try:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return str(v)
        return str(Decimal(str(v)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def clean_payload(obj):
    if isinstance(obj, dict):
        return {k: clean_payload(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [clean_payload(v) for v in obj]
    if isinstance(obj, Decimal):
        return str(obj)
    return obj


def build_ost_payload(ost_id, d):
    payload = {
        "ordersSellingTrackingId":  ost_id,
        "batchNumber":              to_int(d.get("batchNumber")),
        "cashierEmail":             d.get("cashierEmail"),
        "cashierId":                d.get("cashierId"),
        "cashierName":              d.get("cashierName"),
        "category":                 d.get("category"),
        "companyId":                d.get("companyId"),
        "cost":                     to_numeric(d.get("cost")),
        "createdAt":                ts_to_iso(d.get("createdAt")),
        "createdBy":                d.get("createdBy"),
        "discount":                 to_numeric(d.get("discount")),
        "discountType":             d.get("discountType"),
        "invoiceNumber":            d.get("invoiceNumber"),
        "isStockTracked":           bool(d.get("isStockTracked", False)),
        "isVatExempt":              bool(d.get("isVatExempt", False)),
        "itemIndex":                to_int(d.get("itemIndex")),
        "orderId":                  d.get("orderId"),
        "orderDetailsId":           d.get("orderDetailsId"),
        "price":                    to_numeric(d.get("price")),
        "productCode":              d.get("productCode"),
        "productId":                d.get("productId"),
        "itemCode":                 d.get("itemCode"),
        "productName":              d.get("productName"),
        "quantity":                 to_int(d.get("quantity")),
        "runningBalanceTotalStock": to_int(d.get("runningBalanceTotalStock")),
        "skuId":                    d.get("skuId"),
        "status":                   d.get("status"),
        "storeId":                  d.get("storeId"),
        "tagLabels":                d.get("tagLabels") if isinstance(d.get("tagLabels"), list) else [],
        "tags":                     d.get("tags") if isinstance(d.get("tags"), list) else [],
        "total":                    to_numeric(d.get("total")),
        "uid":                      d.get("uid"),
        "updatedAt":                ts_to_iso(d.get("updatedAt")),
        "updatedBy":                d.get("updatedBy"),
        "vat":                      to_numeric(d.get("vat")),
    }
    return clean_payload(payload)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",   default=None, help="Start date YYYY-MM-DD (inclusive)")
    parser.add_argument("--end",     default=None, help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument("--dry-run", action="store_true", help="Count only, don't insert")
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

    # ── Fetch existing IDs + invoice/itemCode combos from BQ to avoid duplicates ───
    print("🔍 Fetching existing ordersSellingTrackingIds and invoice/itemCode combos from BigQuery...")
    existing_ids = set()
    existing_invoice_item_combos = set()
    try:
        rows = bq.query(f"SELECT ordersSellingTrackingId, invoiceNumber, itemCode FROM `{OST_TABLE}`").result()
        for row in rows:
            existing_ids.add(row.ordersSellingTrackingId)
            # Create a tuple of (invoiceNumber, itemCode) to identify duplicates
            if row.invoiceNumber and row.itemCode:
                existing_invoice_item_combos.add((row.invoiceNumber, row.itemCode))
        print(f"   Found {len(existing_ids)} existing rows in BigQuery")
        print(f"   Found {len(existing_invoice_item_combos)} unique invoice/itemCode combinations")
    except Exception as e:
        print(f"⚠️  Could not fetch existing records (table may be empty): {e}")

    # ── Fetch from Firestore ─────────────────────────────────────────────────
    print(f"📥 Fetching from Firestore '{FIRESTORE_COLL}'...")
    query = db.collection(FIRESTORE_COLL)

    if args.start:
        start_dt = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
        query = query.where("createdAt", ">=", start_dt)
    if args.end:
        from datetime import timedelta
        end_dt = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc).replace(hour=23, minute=59, second=59)
        query = query.where("createdAt", "<=", end_dt)

    docs = list(query.stream())
    print(f"   Found {len(docs)} documents in Firestore")

    # ── Build payloads ───────────────────────────────────────────────────────
    to_insert = []
    skipped = 0
    for doc in docs:
        ost_id = doc.id
        d = doc.to_dict()
        
        # Skip if the ordersSellingTrackingId already exists
        if ost_id in existing_ids:
            skipped += 1
            print(f"   ⏭️ Skipping {ost_id}: document ID already exists in BQ")
            continue
        
        # Skip if the same invoiceNumber + itemCode combination already exists
        invoice_number = d.get("invoiceNumber")
        item_code = d.get("itemCode")
        if invoice_number and item_code and (invoice_number, item_code) in existing_invoice_item_combos:
            skipped += 1
            print(f"   ⏭️ Skipping {ost_id}: duplicate detected (invoiceNumber={invoice_number}, itemCode={item_code}) already exists in BQ")
            continue
        
        payload = build_ost_payload(ost_id, d)
        to_insert.append(payload)

    print(f"   {len(to_insert)} to insert, {skipped} skipped (already in BQ)")

    if args.dry_run:
        print("🔵 Dry run — no data written.")
        return

    if not to_insert:
        print("✅ Nothing to insert.")
        return

    # ── Batch insert ─────────────────────────────────────────────────────────
    table = bq.get_table(OST_TABLE)
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
