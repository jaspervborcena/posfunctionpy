from google.cloud import bigquery
import json
import sys

SERVICE_ACCOUNT = r"C:\MVP\POSFunctionPy\functions\service-account.json"
PROJECT = "jasperpos-1dfd5"
DATASET = "tovrika_pos"
TABLE = "orderDetails"

QUERY = f"SELECT * FROM `{PROJECT}.{DATASET}.{TABLE}` WHERE orderDetailsId LIKE 'test-orderdetails-robot-%' ORDER BY createdAt DESC LIMIT 5"


def main():
    try:
        client = bigquery.Client.from_service_account_json(SERVICE_ACCOUNT, project=PROJECT)
    except Exception as e:
        print(f"ERROR creating BigQuery client: {e}")
        sys.exit(2)

    try:
        job = client.query(QUERY)
        rows = list(job.result())
        print(f"Found {len(rows)} test orderDetails records in BigQuery")
        for i, row in enumerate(rows, 1):
            print(f"\n{i}. ID: {row.orderDetailsId}")
            print(f"   Order ID: {row.orderId}")
            print(f"   Company: {row.companyId}")
            print(f"   Store: {row.storeId}")
            print(f"   Created By: {row.createdBy}")
            print(f"   Created At: {row.createdAt}")
            try:
                items_count = len(row.items) if hasattr(row.items, '__len__') and row.items else 0
                print(f"   Items: {items_count} items")
            except:
                print(f"   Items: [complex structure]")
                print(f"   Items type: {type(row.items)}")
                print(f"   Items value: {row.items}")
        
        if len(rows) == 0:
            print("No test records found in BigQuery")
            
    except Exception as e:
        print(f"ERROR running query: {e}")
        sys.exit(3)


if __name__ == '__main__':
    main()