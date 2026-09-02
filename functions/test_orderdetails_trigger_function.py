#!/usr/bin/env python3
"""
Test the orderDetails trigger function directly by simulating a Firestore event.
This bypasses Firestore and directly calls the BigQuery sync function.
"""

import os
import sys
import time
import json
from datetime import datetime, timezone
from unittest.mock import Mock

# Add the current directory to the path so we can import the trigger function
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up environment for BigQuery
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\MVP\POSFunctionPy\functions\service-account.json'

try:
    # Import the trigger function we want to test
    from bigquery_triggers import sync_order_details_to_bigquery
    print("✅ Successfully imported sync_order_details_to_bigquery function")
except Exception as e:
    print(f"❌ Failed to import trigger function: {e}")
    sys.exit(1)


def create_mock_firestore_event():
    """Create a mock Firestore event that simulates a document creation."""
    
    # Create test data similar to what would be in Firestore
    doc_id = f"test-orderdetails-trigger-{int(time.time())}"
    
    test_data = {
        "batchNumber": 1,
        "companyId": "company_test",
        "createdAt": datetime.now(timezone.utc),
        "createdBy": "robot@test",
        "orderId": "order_test_trigger_123",
        "storeId": "store_1",
        "uid": "robot_user",
        "updatedAt": datetime.now(timezone.utc),
        "updatedBy": "robot@test",
        "items": [
            {
                "productId": "prod_1",
                "productName": "Widget A Trigger Test",
                "quantity": 3,
                "price": 150.0,
                "discount": 5.0,
                "vat": 18.0,
                "isVatExempt": False,
                "total": 463.0
            }
        ]
    }
    
    # Mock the Firestore event structure
    mock_event = Mock()
    mock_event.params = {"orderDetailsId": doc_id}
    
    # Mock the document snapshot
    mock_data = Mock()
    mock_data.to_dict.return_value = test_data
    mock_event.data = mock_data
    
    return mock_event, doc_id, test_data


def main():
    print("🧪 Testing orderDetails trigger function directly...")
    print("=" * 50)
    
    try:
        # Create a mock Firestore event
        mock_event, doc_id, test_data = create_mock_firestore_event()
        
        print(f"📄 Test Document ID: {doc_id}")
        print(f"📦 Test Data: {json.dumps(test_data, default=str, indent=2)}")
        print()
        print("🚀 Calling sync_order_details_to_bigquery function...")
        print("-" * 50)
        
        # Call the trigger function directly
        sync_order_details_to_bigquery(mock_event)
        
        print("-" * 50)
        print("✅ Trigger function call completed!")
        print(f"📋 Check BigQuery table 'jasperpos-1dfd5.tovrika_pos.orderDetails' for document: {doc_id}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error testing trigger function: {e}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        return 1


if __name__ == '__main__':
    sys.exit(main())