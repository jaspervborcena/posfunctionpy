"""
Clean up duplicate ordersSellingTracking records in BigQuery.
Keeps only the latest record (by updatedAt) for each invoiceNumber + itemCode combination.

Run from the functions/ directory:
    python cleanup_ost_duplicates.py --project jasperpos-1dfd5 --dataset tovrika_pos
    python cleanup_ost_duplicates.py --project jasperpos-dev --dataset tovrika_pos_dev
"""
import sys
import argparse
from datetime import datetime
from google.cloud import bigquery
from google.oauth2 import service_account

SA_FILE = "service-account.json"

def cleanup_duplicates(project_id, dataset_id):
    """Remove duplicate ordersSellingTracking records, keeping only the latest."""
    
    # Initialize BigQuery client
    sa_creds = service_account.Credentials.from_service_account_file(
        SA_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    client = bigquery.Client(project=project_id, credentials=sa_creds)
    
    table_name = f"{project_id}.{dataset_id}.ordersSellingTracking"
    
    print(f"🔍 Analyzing duplicates in {table_name}...")
    
    # Find duplicates: invoiceNumber + itemCode combinations with more than 1 record
    find_duplicates_query = f"""
        SELECT 
            invoiceNumber,
            itemCode,
            COUNT(*) as count,
            ARRAY_AGG(
                STRUCT(
                    ordersSellingTrackingId,
                    status,
                    updatedAt
                ) 
                ORDER BY updatedAt DESC
            ) as records
        FROM `{table_name}`
        WHERE invoiceNumber IS NOT NULL AND itemCode IS NOT NULL
        GROUP BY invoiceNumber, itemCode
        HAVING count > 1
    """
    
    results = list(client.query(find_duplicates_query).result())
    
    if not results:
        print("✅ No duplicates found!")
        return
    
    print(f"📊 Found {len(results)} duplicate groups:")
    
    # Collect all IDs to delete (keeping the first/latest one)
    ids_to_delete = []
    
    for row in results:
        invoice = row['invoiceNumber']
        item_code = row['itemCode']
        count = row['count']
        records = row['records']
        
        print(f"\n   Invoice: {invoice}, ItemCode: {item_code}")
        print(f"   Count: {count}")
        print(f"   Records (ordered by latest first):")
        
        # Keep the first (latest) record, delete the rest
        for i, rec in enumerate(records):
            status = "KEEP ✅" if i == 0 else "DELETE ❌"
            print(f"      {status} | ID: {rec['ordersSellingTrackingId']} | Status: {rec['status']} | Updated: {rec['updatedAt']}")
            if i > 0:  # Skip the first one (keep it)
                ids_to_delete.append(rec['ordersSellingTrackingId'])
    
    if not ids_to_delete:
        print("\n✅ No records to delete (all groups have exactly 1 record)")
        return
    
    print(f"\n🗑️  About to delete {len(ids_to_delete)} duplicate records...")
    print("⏳ Using table replacement method (streaming buffer safe)...")
    
    # Extract table info
    table_parts = table_name.split(".")
    dataset_id_str = table_parts[1]
    table_id_str = table_parts[2]
    temp_table_id = f"{table_id_str}_temp"
    
    dataset = client.get_dataset(dataset_id_str)
    
    # Keep one row per invoice+itemCode; completed is preferred over open.
    dedup_query = f"""
        SELECT * EXCEPT(row_num)
        FROM (
            SELECT 
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY invoiceNumber, itemCode 
                    ORDER BY
                        CASE WHEN status = 'completed' THEN 0 ELSE 1 END,
                        updatedAt DESC NULLS LAST,
                        createdAt DESC NULLS LAST,
                        ordersSellingTrackingId DESC
                ) as row_num
            FROM `{table_name}`
            WHERE invoiceNumber IS NOT NULL AND itemCode IS NOT NULL
        )
        WHERE row_num = 1
    """
    
    print(f"   Creating temporary table with deduplicated records...")
    temp_table_ref = dataset.table(temp_table_id)
    job_config = bigquery.QueryJobConfig(
        destination=temp_table_ref,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
    )
    job = client.query(dedup_query, job_config=job_config)
    job.result()
    print(f"   ✅ Temporary table created")
    
    # Create backup with timestamp
    backup_table_id = f"{table_id_str}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_table_ref = dataset.table(backup_table_id)
    
    print(f"   Creating backup of original table...")
    copy_job_config = bigquery.CopyJobConfig()
    copy_job = client.copy_table(
        dataset.table(table_id_str),
        backup_table_ref,
        job_config=copy_job_config
    )
    copy_job.result()
    print(f"   ✅ Backup created: {backup_table_id}")
    
    # Delete original table
    print(f"   Deleting original table...")
    client.delete_table(dataset.table(table_id_str))
    print(f"   ✅ Original table deleted")
    
    # Rename temp to original
    print(f"   Renaming temp table to original name...")
    temp_table = client.get_table(temp_table_ref)
    original_table = bigquery.Table(dataset.table(table_id_str), schema=temp_table.schema)
    original_table.time_partitioning = temp_table.time_partitioning
    
    # Copy temp to original location
    copy_final = client.copy_table(temp_table_ref, dataset.table(table_id_str))
    copy_final.result()
    print(f"   ✅ Restored original table name")
    
    # Delete temp table
    client.delete_table(temp_table_ref)
    print(f"   ✅ Cleanup complete")
    
    print(f"\n✅ Successfully deduplicated table!")
    print(f"   - Removed {len(ids_to_delete)} duplicate records")
    print(f"   - Backup saved as: {backup_table_id}")
    
    # Verify cleanup
    verify_query = f"""
        SELECT 
            invoiceNumber,
            itemCode,
            COUNT(*) as count
        FROM `{table_name}`
        WHERE invoiceNumber IS NOT NULL AND itemCode IS NOT NULL
        GROUP BY invoiceNumber, itemCode
        HAVING count > 1
    """
    
    remaining = list(client.query(verify_query).result())
    if remaining:
        print(f"\n⚠️  Warning: {len(remaining)} duplicate groups still remain:")
        for row in remaining:
            print(f"   Invoice: {row['invoiceNumber']}, ItemCode: {row['itemCode']}, Count: {row['count']}")
    else:
        print(f"✅ Verification: All duplicates removed!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="GCP Project ID (jasperpos-1dfd5 or jasperpos-dev)")
    parser.add_argument("--dataset", required=True, help="BigQuery Dataset ID (tovrika_pos or tovrika_pos_dev)")
    args = parser.parse_args()
    
    try:
        cleanup_duplicates(args.project, args.dataset)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
