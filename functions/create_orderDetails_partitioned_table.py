from google.cloud import bigquery
import sys

SERVICE_ACCOUNT = r"C:\MVP\POSFunctionPy\functions\service-account.json"
PROJECT = "jasperpos-1dfd5"
DATASET_ID = "tovrika_pos"
TABLE_ID = "orderDetails"  # camelCase as requested

client = bigquery.Client.from_service_account_json(SERVICE_ACCOUNT, project=PROJECT)

def ensure_dataset():
    dataset_ref = bigquery.DatasetReference(PROJECT, DATASET_ID)
    try:
        client.get_dataset(dataset_ref)
        print(f"Dataset {PROJECT}.{DATASET_ID} already exists")
    except Exception:
        print(f"Creating dataset {PROJECT}.{DATASET_ID}")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "asia-east1"
        client.create_dataset(dataset)
        print("Dataset created")


def create_partitioned_table():
    dataset_ref = bigquery.DatasetReference(PROJECT, DATASET_ID)
    table_ref = dataset_ref.table(TABLE_ID)
    try:
        client.get_table(table_ref)
        print(f"Table {PROJECT}.{DATASET_ID}.{TABLE_ID} already exists")
        return
    except Exception:
        print(f"Creating partitioned table {PROJECT}.{DATASET_ID}.{TABLE_ID}")

    schema = [
        bigquery.SchemaField("batchNumber", "INT64"),
        bigquery.SchemaField("companyId", "STRING"),
        bigquery.SchemaField("createdAt", "TIMESTAMP"),
        bigquery.SchemaField("createdBy", "STRING"),
        bigquery.SchemaField("orderId", "STRING"),
        bigquery.SchemaField("storeId", "STRING"),
        bigquery.SchemaField("uid", "STRING"),
        bigquery.SchemaField("updatedAt", "TIMESTAMP"),
        bigquery.SchemaField("updatedBy", "STRING"),
        bigquery.SchemaField(
            "items",
            "RECORD",
            mode="REPEATED",
            fields=[
                bigquery.SchemaField("productId", "STRING"),
                bigquery.SchemaField("productName", "STRING"),
                bigquery.SchemaField("quantity", "INT64"),
                bigquery.SchemaField("price", "FLOAT64"),
                bigquery.SchemaField("discount", "FLOAT64"),
                bigquery.SchemaField("vat", "FLOAT64"),
                bigquery.SchemaField("isVatExempt", "BOOL"),
                bigquery.SchemaField("total", "FLOAT64"),
            ],
        ),
        bigquery.SchemaField("orderDetailsId", "STRING"),
    ]

    table = bigquery.Table(table_ref, schema=schema)
    # Partition by DATE(updatedAt)
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="updatedAt",
        require_partition_filter=False
    )

    table = client.create_table(table)
    print(f"Created partitioned table: {table.project}.{table.dataset_id}.{table.table_id} (partitioned by DATE(updatedAt))")


if __name__ == '__main__':
    try:
        ensure_dataset()
        create_partitioned_table()
    except Exception as e:
        print(f"Error creating dataset/table: {e}")
        sys.exit(1)
    print("Done")
