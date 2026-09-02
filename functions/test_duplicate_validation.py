"""
Test script to verify duplicate validation in Firestore triggers.
This will create duplicate documents to test that BigQuery inserts are skipped.
"""
from datetime import datetime
import time
import os

# Set up Firebase Admin SDK
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\MVP\POSFunctionPy\functions\service-account.json"

from firebase_admin import firestore, credentials, initialize_app

SERVICE_ACCOUNT = r"C:\MVP\POSFunctionPy\functions\service-account.json"

try:
    cred = credentials.Certificate(SERVICE_ACCOUNT)
    initialize_app(cred)
    print(f"Using service account from: {SERVICE_ACCOUNT}")
except ValueError:
    print("Firebase app already initialized")

db = firestore.client()

def test_duplicate_order():
    """Test duplicate order creation - should skip second insert"""
    order_id = "test-duplicate-order-validation"
    
    order_data = {
        "companyId": "test-company",
        "storeId": "test-store",
        "totalAmount": 150.0,
        "status": "active",
        "createdBy": "validation-test",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "uid": "test-user"
    }
    
    print(f"\n=== Testing Orders Duplicate Validation ===")
    print(f"Creating first order: {order_id}")
    db.collection("orders").document(order_id).set(order_data)
    print("✅ First order created")
    
    # Wait a moment for trigger to process
    time.sleep(3)
    
    print(f"Creating duplicate order: {order_id}")
    db.collection("orders").document(order_id).set(order_data)
    print("✅ Duplicate order created (should be skipped in BigQuery)")

def test_duplicate_orderdetails():
    """Test duplicate orderDetails creation - should skip second insert"""
    order_detail_id = "test-duplicate-orderdetails-validation"
    
    orderdetails_data = {
        "orderId": "test-order-123",
        "companyId": "test-company", 
        "storeId": "test-store",
        "batchNumber": 1,
        "createdBy": "validation-test",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "uid": "test-user",
        "items": [{
            "productId": "prod-1",
            "productName": "Test Product",
            "quantity": 2,
            "price": 50.0,
            "total": 100.0
        }]
    }
    
    print(f"\n=== Testing OrderDetails Duplicate Validation ===")
    print(f"Creating first orderDetails: {order_detail_id}")
    db.collection("orderDetails").document(order_detail_id).set(orderdetails_data)
    print("✅ First orderDetails created")
    
    # Wait a moment for trigger to process
    time.sleep(3)
    
    print(f"Creating duplicate orderDetails: {order_detail_id}")
    db.collection("orderDetails").document(order_detail_id).set(orderdetails_data)
    print("✅ Duplicate orderDetails created (should be skipped in BigQuery)")

def test_duplicate_product():
    """Test duplicate product creation - should skip second insert"""
    product_id = "test-duplicate-product-validation"
    
    product_data = {
        "productName": "Test Validation Product",
        "companyId": "test-company",
        "storeId": "test-store", 
        "category": "Test Category",
        "sellingPrice": 75.0,
        "totalStock": 100,
        "status": "active",
        "createdBy": "validation-test",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "uid": "test-user",
        "isVatApplicable": True
    }
    
    print(f"\n=== Testing Products Duplicate Validation ===")
    print(f"Creating first product: {product_id}")
    db.collection("products").document(product_id).set(product_data)
    print("✅ First product created")
    
    # Wait a moment for trigger to process
    time.sleep(3)
    
    print(f"Creating duplicate product: {product_id}")
    db.collection("products").document(product_id).set(product_data)
    print("✅ Duplicate product created (should be skipped in BigQuery)")

def main():
    print("🔬 Testing Duplicate Validation in Firestore Triggers")
    print("This will create documents twice to test BigQuery duplicate prevention")
    
    test_duplicate_order()
    test_duplicate_orderdetails()
    test_duplicate_product()
    
    print(f"\n✅ All duplicate validation tests completed!")
    print(f"Check the Firebase Function logs to confirm duplicates were skipped:")
    print(f"gcloud functions logs read sync_order_to_bigquery --region=asia-east1 --limit=10")
    print(f"gcloud functions logs read sync_order_details_to_bigquery --region=asia-east1 --limit=10")
    print(f"gcloud functions logs read sync_products_to_bigquery --region=asia-east1 --limit=10")

if __name__ == '__main__':
    main()