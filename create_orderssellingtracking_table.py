#!/usr/bin/env python3
"""
Create the ordersSellingTracking table in BigQuery with partitioning and clustering.
"""

import os
from google.cloud import bigquery

def create_ordersellingtracking_table():
    """Create the ordersSellingTracking table with partitioning and clustering."""
    # Set the service account credentials path
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'functions/service-account.json'
    
    # BigQuery configuration
    BIGQUERY_PROJECT_ID = "jasperpos-1dfd5"
    BIGQUERY_DATASET_ID = "tovrika_pos"
    BIGQUERY_LOCATION = "asia-east1"
    
    client = bigquery.Client(project=BIGQUERY_PROJECT_ID, location=BIGQUERY_LOCATION)
    
    table_id = f"{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET_ID}.ordersSellingTracking"
    
    # Define the schema - updated to match new Firestore collection structure
    schema = [
    bigquery.SchemaField("ordersSellingTrackingId", "STRING"),
        bigquery.SchemaField("batchNumber", "STRING"),
        bigquery.SchemaField("companyId", "STRING"),
        bigquery.SchemaField("createdAt", "TIMESTAMP"),
        bigquery.SchemaField("createdBy", "STRING"),
        bigquery.SchemaField("orderId", "STRING"),
        bigquery.SchemaField("status", "STRING"),
        bigquery.SchemaField("storeId", "STRING"),
        bigquery.SchemaField("uid", "STRING"),
        bigquery.SchemaField("updatedAt", "TIMESTAMP"),
        bigquery.SchemaField("updatedBy", "STRING"),
        bigquery.SchemaField("itemIndex", "INTEGER"),
        bigquery.SchemaField("productId", "STRING"),
        bigquery.SchemaField("productName", "STRING"),
        bigquery.SchemaField("price", "FLOAT64"),
        bigquery.SchemaField("quantity", "FLOAT64"),
        bigquery.SchemaField("discount", "FLOAT64"),
        bigquery.SchemaField("discountType", "STRING"),
        bigquery.SchemaField("vat", "FLOAT64"),
        bigquery.SchemaField("total", "FLOAT64"),
        bigquery.SchemaField("isVatExempt", "BOOLEAN"),
        bigquery.SchemaField("orderDetailsId", "STRING"),
    ]
    
    # Create the table with partitioning and clustering
    table = bigquery.Table(table_id, schema=schema)
    
    # Partition by date (daily) on updatedAt field
    table.time_partitioning = bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="updatedAt"
    )
    
    # Cluster by companyId and storeId for better query performance
    table.clustering_fields = ["companyId", "storeId"]
    
    try:
        # Check if table exists
        existing_table = client.get_table(table_id)
        print(f"✅ Table {table_id} already exists")
        return existing_table
    except Exception:
        # Table doesn't exist, create it
        try:
            table = client.create_table(table)
            print(f"✅ Created table {table_id} with:")
            print(f"   - Daily partitioning on 'updatedAt' field")
            print(f"   - Clustering on 'companyId' and 'storeId'")
            print(f"   - Schema: {len(schema)} fields")
            return table
        except Exception as e:
            print(f"❌ Error creating table: {e}")
            raise

if __name__ == "__main__":
    create_ordersellingtracking_table()