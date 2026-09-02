"""Backfill root-level Firestore orderDetails documents into production BigQuery."""
import argparse
import json

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud import bigquery
from google.oauth2 import service_account

from bq_helpers import build_orderdetails_payload

SA_FILE = "service-account.json"
PROJECT = "jasperpos-1dfd5"
TABLE = f"{PROJECT}.tovrika_pos.orderDetails"
BATCH_SIZE = 200


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    firebase_admin.initialize_app(credentials.Certificate(SA_FILE))
    db = firestore.client()
    bq = bigquery.Client(
        project=PROJECT,
        location="asia-east1",
        credentials=service_account.Credentials.from_service_account_file(
            SA_FILE, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        ),
    )

    docs = list(db.collection("orderDetails").stream())
    existing = {
        row.orderDetailsId
        for row in bq.query(f"SELECT orderDetailsId FROM `{TABLE}`", location="asia-east1").result()
    }
    payloads = [
        build_orderdetails_payload(doc.id, doc.to_dict())
        for doc in docs
        if doc.id not in existing
    ]
    print(f"Firestore documents: {len(docs)}")
    print(f"Already in BigQuery: {len(docs) - len(payloads)}")
    print(f"To insert: {len(payloads)}")
    if args.dry_run or not payloads:
        return

    table = bq.get_table(TABLE)
    inserted = 0
    errors = []
    for index in range(0, len(payloads), BATCH_SIZE):
        batch = payloads[index:index + BATCH_SIZE]
        batch_errors = bq.insert_rows_json(table, batch)
        if batch_errors:
            errors.extend(batch_errors)
        else:
            inserted += len(batch)
    print(f"Inserted: {inserted}")
    print(f"Errors: {json.dumps(errors)}")


if __name__ == "__main__":
    main()
