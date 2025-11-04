"""
Cleanup script for BigQuery tables.

This script truncates (removes all rows from) a target table using the service account JSON
provided in the repo. It is safer and cheaper than dropping/recreating tables and preserves
schema and partitioning.

Usage (PowerShell):
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\MVP\POSFunctionPy\functions\service-account.json"
python .\functions\cleanup_bigquery.py --table orderDetails

Options:
  --project  (default: jasperpos-1dfd5)
  --dataset  (default: tovrika_pos)
  --table    (required) table name (e.g. orderDetails)
  --dry-run  (flag) print the SQL that would run without executing it

CAUTION: This permanently deletes data. Run with --dry-run first.
"""
from google.cloud import bigquery
import argparse
import sys

DEFAULT_PROJECT = "jasperpos-1dfd5"
DEFAULT_DATASET = "tovrika_pos"


def parse_args():
    p = argparse.ArgumentParser(description="Truncate BigQuery table (permanent)")
    p.add_argument("--project", default=DEFAULT_PROJECT)
    p.add_argument("--dataset", default=DEFAULT_DATASET)
    p.add_argument("--table", required=True)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()

    table_fq = f"{args.project}.{args.dataset}.{args.table}"
    sql = f"TRUNCATE TABLE `{table_fq}`"

    print(f"Target table: {table_fq}")
    print(f"SQL: {sql}")

    if args.dry_run:
        print("Dry run mode - not executing")
        return

    try:
        client = bigquery.Client()
    except Exception as e:
        print(f"ERROR creating BigQuery client: {e}")
        sys.exit(2)

    try:
        job = client.query(sql)
        job.result()
        print(f"SUCCESS: Table truncated: {table_fq}")
    except Exception as e:
        print(f"ERROR truncating table: {e}")
        sys.exit(3)


if __name__ == '__main__':
    main()
