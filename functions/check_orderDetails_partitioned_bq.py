from google.cloud import bigquery
import json
import sys

SERVICE_ACCOUNT = r"C:\MVP\POSFunctionPy\functions\service-account.json"
PROJECT = "jasperpos-1dfd5"
DATASET = "tovrika_pos"
TABLE = "orderDetails"

QUERY = f"SELECT * FROM `{PROJECT}.{DATASET}.{TABLE}` WHERE orderDetailsId = 'test-orderdetails-partitioned-001' LIMIT 10"


def main():
    try:
        client = bigquery.Client.from_service_account_json(SERVICE_ACCOUNT, project=PROJECT)
    except Exception as e:
        print(f"ERROR creating BigQuery client: {e}")
        sys.exit(2)

    try:
        job = client.query(QUERY)
        rows = list(job.result())
        print(f"Found {len(rows)} rows for test-orderdetails-partitioned-001")
        out = []
        for r in rows:
            d = dict((k, (v.isoformat() if hasattr(v, 'isoformat') else v)) for k, v in dict(r).items())
            out.append(d)
        print(json.dumps(out, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"ERROR running query: {e}")
        sys.exit(3)


if __name__ == '__main__':
    main()
