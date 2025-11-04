#!/usr/bin/env python3
"""
Test the orderDetails BigQuery insertion logic directly.
This tests the core logic without Firebase Functions dependencies.
"""

import os
import sys
import time
import json
from datetime import datetime, timezone

# Set up environment for BigQuery
SERVICE_ACCOUNT = r'C:\MVP\POSFunctionPy\functions\service-account.json'
PROJECT = "jasperpos-1dfd5"
DATASET = "tovrika_pos"
TABLE = "orderDetails"

try:
    from google.cloud import bigquery
    print("✅ BigQuery client available")
except ImportError:
    print("❌ BigQuery client not available")
    sys.exit(1)

# Import the helper function
try:
    from bq_helpers import build_orderdetails_payload
    print("✅ Successfully imported build_orderdetails_payload helper")
except Exception as e:
    print(f"❌ Failed to import helper function: {e}")
    sys.exit(1)


def test_orderdetails_payload_and_insert():
    """Test the orderDetails payload building and BigQuery insertion."""
    
    print("🧪 Testing orderDetails payload building and BigQuery insertion...")
    print("=" * 60)
    
    # Create test data similar to what would come from Firestore
    doc_id = f"test-orderdetails-direct-{int(time.time())}"
    
    test_data = {
        "batchNumber": 1,
        "companyId": "company_test",
        "createdAt": datetime.now(timezone.utc),
        "createdBy": "robot@test",
        "orderId": "order_test_direct_123",
        "storeId": "store_1",
        "uid": "robot_user",
        "updatedAt": datetime.now(timezone.utc),
        "updatedBy": "robot@test",
        "items": [
            {
                "productId": "prod_1",
                "productName": "Widget A Direct Test",
                "quantity": 4,
                "price": 200.0,
                "discount": 10.0,
                "vat": 24.0,
                "isVatExempt": False,
                "total": 814.0
            },
            {
                "productId": "prod_2", 
                "productName": "Widget B Direct Test",
                "quantity": 1,
                "price": 50.0,
                "discount": 0.0,
                "vat": 6.0,
                "isVatExempt": False,
                "total": 56.0
            }
        ]
    }
    
    print(f"📄 Test Document ID: {doc_id}")
    print(f"📦 Test Data: {json.dumps(test_data, default=str, indent=2)}")
    print()
    
    try:
        # Step 1: Test payload building
        print("🔧 Step 1: Building payload...")
        payload = build_orderdetails_payload(doc_id, test_data)
        print(f"✅ Payload built successfully:")
        print(json.dumps(payload, default=str, indent=2))
        print()
        
        # Step 2: Test BigQuery insertion
        print("🔧 Step 2: Inserting into BigQuery...")
        client = bigquery.Client.from_service_account_json(SERVICE_ACCOUNT, project=PROJECT)
        
        table_ref = f"{PROJECT}.{DATASET}.{TABLE}"
        table = client.get_table(table_ref)
        
        print(f"📤 Inserting into {table_ref}...")
        errors = client.insert_rows_json(table, [payload])
        
        if errors:
            print(f"❌ BigQuery insert failed with errors: {errors}")
            return 1
        else:
            print(f"✅ BigQuery insert successful!")
            print(f"📋 Document ID: {doc_id}")
            print(f"📋 Check BigQuery table for the new record")
            return 0
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        return 1


def main():
    return test_orderdetails_payload_and_insert()


if __name__ == '__main__':
    sys.exit(main())