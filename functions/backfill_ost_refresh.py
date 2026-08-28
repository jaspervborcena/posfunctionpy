"""
Full refresh backfill for ordersSellingTracking — wipes BQ table and re-inserts
all Firestore docs with the updated payload (now including category, invoiceNumber,
productCode, skuId, tagLabels, tags).

Run from functions/ directory:
    python backfill_ost_refresh.py

Optional:
    --dry-run   Count only, no writes.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import bigquery
from google.oauth2 import service_account

SA_FILE    = "service-account.json"
BQ_PROJECT = "jasperpos-1dfd5"
OST_TABLE  = f"{BQ_PROJECT}.tovrika_pos.ordersSellingTracking"
FIRESTORE_COLL = "ordersSellingTracking"
BATCH_SIZE = 200


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cred = credentials.Certificate(SA_FILE)
    firebase_admin.initialize_app(cred)
    db = firestore.client()

    sa_creds = service_account.Credentials.from_service_account_file(
        SA_FILE, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    bq = bigquery.Client(project=BQ_PROJECT, credentials=sa_creds)

    # Fetch all Firestore docs
    print(f"📥 Fetching all docs from Firestore '{FIRESTORE_COLL}'...")
    docs = list(db.collection(FIRESTORE_COLL).stream())
    print(f"   Found {len(docs)} documents")

    # Build payloads
    payloads = [build_ost_payload(doc.id, doc.to_dict()) for doc in docs]

    if args.dry_run:
        print(f"🔵 Dry run — would delete all BQ rows and re-insert {len(payloads)} rows.")
        print(f"   Sample fields in first payload: {list(payloads[0].keys()) if payloads else []}")
        return

    # Truncate BQ table
    print(f"🗑️  Truncating {OST_TABLE}...")
    bq.query(f"TRUNCATE TABLE `{OST_TABLE}`").result()
    print("   Done.")

    # Batch insert
    table = bq.get_table(OST_TABLE)
    inserted = 0
    errors = []

    for i in range(0, len(payloads), BATCH_SIZE):
        batch = payloads[i:i + BATCH_SIZE]
        errs = bq.insert_rows_json(table, batch)
        if errs:
            errors.extend(errs)
            print(f"❌ Errors in batch {i // BATCH_SIZE + 1}: {errs}")
        else:
            inserted += len(batch)
            print(f"   ✅ Batch {i // BATCH_SIZE + 1}: {len(batch)} rows (total: {inserted})")

    print(f"\n{'='*50}")
    print(f"✅ Done. Inserted: {inserted} | Errors: {len(errors)}")
    if errors:
        for e in errors:
            print(f"   {e}")


if __name__ == "__main__":
    main()
