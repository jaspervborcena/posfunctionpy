"""Add missing columns to ordersSellingTracking BigQuery table."""
from google.cloud import bigquery
from google.oauth2 import service_account

SA_FILE    = "service-account.json"
PROJECT    = "jasperpos-1dfd5"
TABLE_ID   = f"{PROJECT}.tovrika_pos.ordersSellingTracking"

sa = service_account.Credentials.from_service_account_file(
    SA_FILE, scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
bq = bigquery.Client(project=PROJECT, credentials=sa)

table = bq.get_table(TABLE_ID)
existing = {f.name for f in table.schema}
print(f"Existing columns: {sorted(existing)}")

new_fields = [
    bigquery.SchemaField("category",      "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("invoiceNumber", "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("productCode",   "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("skuId",         "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("tagLabels",     "STRING",  mode="REPEATED"),
    bigquery.SchemaField("tags",          "STRING",  mode="REPEATED"),
]

to_add = [f for f in new_fields if f.name not in existing]
if not to_add:
    print("All columns already exist — nothing to do.")
else:
    table.schema = table.schema + to_add
    bq.update_table(table, ["schema"])
    print(f"✅ Added columns: {[f.name for f in to_add]}")
