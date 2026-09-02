"""
Run dedupe queries to remove duplicate rows in BigQuery tables.

This script runs three DELETE ... JOIN queries that keep the most recent
row per id (productId, orderId, orderDetailsId) based on `updatedAt` (or
`createdAt` when updatedAt is null).

USE WITH CAUTION: This permanently deletes rows. Run in the BigQuery UI
or test on a copy of your table first.

Set environment variable GOOGLE_APPLICATION_CREDENTIALS to point to your
service account JSON (the same used by other functions).

Example:
    $env:GOOGLE_APPLICATION_CREDENTIALS = 'C:\MVP\POSFunctionPy\functions\service-account.json'
    python cleanup_bigquery_duplicates.py --project jasperpos-1dfd5 --dataset tovrika_pos

"""

import argparse
import os
from google.cloud import bigquery

SQL_DEDUPE_PRODUCTS = r"""
-- Keep the latest row per productId based on updatedAt (or createdAt fallback)
CREATE OR REPLACE TABLE `{project}.{dataset}.products_deduped` AS
SELECT * EXCEPT(rn) FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY productId ORDER BY COALESCE(updatedAt, createdAt) DESC) AS rn
  FROM `{project}.{dataset}.products`
)
WHERE rn = 1;

-- Replace original table (careful: this will drop/replace)
CREATE OR REPLACE TABLE `{project}.{dataset}.products` AS
SELECT * FROM `{project}.{dataset}.products_deduped`;

DROP TABLE `{project}.{dataset}.products_deduped`;
"""

SQL_DEDUPE_ORDERS = r"""
CREATE OR REPLACE TABLE `{project}.{dataset}.orders_deduped` AS
SELECT * EXCEPT(rn) FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY orderId ORDER BY COALESCE(updatedAt, createdAt) DESC) AS rn
  FROM `{project}.{dataset}.orders`
)
WHERE rn = 1;

CREATE OR REPLACE TABLE `{project}.{dataset}.orders` AS
SELECT * FROM `{project}.{dataset}.orders_deduped`;

DROP TABLE `{project}.{dataset}.orders_deduped`;
"""

SQL_DEDUPE_ORDERDETAILS = r"""
CREATE OR REPLACE TABLE `{project}.{dataset}.orderDetails_deduped` AS
SELECT * EXCEPT(rn) FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY orderDetailsId ORDER BY COALESCE(updatedAt, createdAt) DESC) AS rn
  FROM `{project}.{dataset}.orderDetails`
)
WHERE rn = 1;

CREATE OR REPLACE TABLE `{project}.{dataset}.orderDetails` AS
SELECT * FROM `{project}.{dataset}.orderDetails_deduped`;

DROP TABLE `{project}.{dataset}.orderDetails_deduped`;
"""


def run_query(client, sql):
    print("Running SQL:\n", sql[:500], "...\n")
    job = client.query(sql)
    job.result()
    print("Done")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="GCP project id")
    parser.add_argument("--dataset", required=True, help="BigQuery dataset name (e.g. tovrika_pos)")
    args = parser.parse_args()

    client = bigquery.Client(project=args.project)

    # products
    sql = SQL_DEDUPE_PRODUCTS.format(project=args.project, dataset=args.dataset)
    run_query(client, sql)

    # orders
    sql = SQL_DEDUPE_ORDERS.format(project=args.project, dataset=args.dataset)
    run_query(client, sql)

    # orderDetails
    sql = SQL_DEDUPE_ORDERDETAILS.format(project=args.project, dataset=args.dataset)
    run_query(client, sql)

    print("All dedupe operations completed.")


if __name__ == '__main__':
    main()
