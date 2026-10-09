"""Add missing columns to ordersSellingTracking BigQuery table."""
import os

from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT    = os.environ.get("TARGET_PROJECT", "jasperpos-1dfd5")
DATASET   = os.environ.get(
    "TARGET_DATASET",
    "tovrika_pos_dev" if PROJECT == "jasperpos-dev" else "tovrika_pos"
)
SA_FILE    = "service-account-dev.json" if PROJECT == "jasperpos-dev" else "service-account.json"
TABLE_ID   = f"{PROJECT}.{DATASET}.ordersSellingTracking"

sa = service_account.Credentials.from_service_account_file(
    SA_FILE, scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
bq = bigquery.Client(project=PROJECT, credentials=sa)

table = bq.get_table(TABLE_ID)
existing = {f.name for f in table.schema}
print(f"Existing columns: {sorted(existing)}")

new_fields = [
    bigquery.SchemaField("cost",          "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("category",      "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("invoiceNumber", "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("itemCode",      "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("productCode",   "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("skuId",         "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("isStockTracked", "BOOL",   mode="NULLABLE"),
    bigquery.SchemaField("runningBalanceTotalStock", "INT64", mode="NULLABLE"),
    bigquery.SchemaField("tagLabels",     "STRING",  mode="REPEATED"),
    bigquery.SchemaField("tags",          "STRING",  mode="REPEATED"),
    bigquery.SchemaField("orderDetailsId", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("uid",           "STRING",  mode="NULLABLE"),
]

to_add = [f for f in new_fields if f.name not in existing]
if not to_add:
    print("All columns already exist — nothing to do.")
else:
    table.schema = table.schema + to_add
    bq.update_table(table, ["schema"])
    print(f"✅ Added columns: {[f.name for f in to_add]}")
