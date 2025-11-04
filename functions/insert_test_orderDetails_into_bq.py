from google.cloud import bigquery
import json
import sys
from datetime import datetime, timezone

SERVICE_ACCOUNT = r"C:\MVP\POSFunctionPy\functions\service-account.json"
PROJECT = "jasperpos-1dfd5"
DATASET = "tovrika_pos"
TABLE = "orderDetails"

payload = {
    "orderDetailsId": "test-orderdetails-partitioned-001",
    "batchNumber": 1,
    "companyId": "company_test",
    "createdAt": datetime.now(timezone.utc).isoformat(),
    "createdBy": "robot@test",
    "orderId": "order_test_part_001",
    "storeId": "store_1",
    "uid": "robot_user",
    "updatedAt": datetime.now(timezone.utc).isoformat(),
    "updatedBy": "robot@test",
    "items": [
        {
            "productId": "prod_1",
            "productName": "Widget A",
            "quantity": 2,
            "price": 100.0,
            "discount": 0.0,
            "vat": 12.0,
            "isVatExempt": False,
            "total": 224.0
        }
    ]
}


def main():
    try:
        client = bigquery.Client.from_service_account_json(SERVICE_ACCOUNT, project=PROJECT)
    except Exception as e:
        print(f"ERROR creating BigQuery client: {e}")
        sys.exit(2)

    table_ref = f"{PROJECT}.{DATASET}.{TABLE}"
    try:
        table = client.get_table(table_ref)
    except Exception as e:
        print(f"ERROR: target table not found: {e}")
        sys.exit(3)

    try:
        errors = client.insert_rows_json(table, [payload])
        if errors:
            print(f"Insert returned errors: {errors}")
            sys.exit(4)
        else:
            print("Insert succeeded into partitioned table")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"ERROR inserting rows: {e}")
        sys.exit(5)


if __name__ == '__main__':
    main()
