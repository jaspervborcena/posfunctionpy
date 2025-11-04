"""
Test script to verify that on_document_updated triggers update ALL fields in BigQuery.
This will create documents, then update them with different data to ensure complete field updates.
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

def test_order_complete_update():
    """Test that order updates replace ALL fields in BigQuery"""
    order_id = "test-complete-update-order"
    
    # Initial order data
    initial_data = {
        "companyId": "initial-company",
        "storeId": "initial-store",
        "totalAmount": 100.0,
        "status": "pending",
        "createdBy": "initial-user",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "uid": "initial-uid",
        "assignedCashierName": "Initial Cashier",
        "grossAmount": 100.0,
        "netAmount": 100.0
    }
    
    print(f"\n=== Testing Orders Complete Field Update ===")
    print(f"Creating initial order: {order_id}")
    db.collection("orders").document(order_id).set(initial_data)
    print("Initial order created - waiting 5 seconds...")
    time.sleep(5)
    
    # Updated order data with ALL fields changed
    updated_data = {
        "companyId": "UPDATED-company",
        "storeId": "UPDATED-store", 
        "totalAmount": 250.0,
        "status": "completed",
        "createdBy": "UPDATED-user",
        "createdAt": initial_data["createdAt"],  # Keep original creation time
        "updatedAt": datetime.utcnow(),
        "uid": "UPDATED-uid",
        "assignedCashierName": "UPDATED Cashier Name",
        "grossAmount": 250.0,
        "netAmount": 225.0,
        "discountAmount": 25.0,
        "vatAmount": 30.0,
        "assignedCashierEmail": "updated@test.com",
        "message": "This is an updated message",
        "invoiceNumber": "INV-UPDATED-001"
    }
    
    print(f"Updating order with ALL new field values: {order_id}")
    db.collection("orders").document(order_id).set(updated_data)
    print("✅ Order updated - should see ALL fields updated in BigQuery")

def test_orderdetails_complete_update():
    """Test that orderDetails updates replace ALL fields in BigQuery"""
    order_detail_id = "test-complete-update-orderdetails"
    
    # Initial orderDetails data
    initial_data = {
        "orderId": "initial-order-123",
        "companyId": "initial-company",
        "storeId": "initial-store",
        "batchNumber": 1,
        "createdBy": "initial-user",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "uid": "initial-uid",
        "items": [{
            "productId": "prod-initial",
            "productName": "Initial Product",
            "quantity": 1,
            "price": 50.0,
            "total": 50.0
        }]
    }
    
    print(f"\n=== Testing OrderDetails Complete Field Update ===")
    print(f"Creating initial orderDetails: {order_detail_id}")
    db.collection("orderDetails").document(order_detail_id).set(initial_data)
    print("Initial orderDetails created - waiting 5 seconds...")
    time.sleep(5)
    
    # Updated orderDetails data with ALL fields changed
    updated_data = {
        "orderId": "UPDATED-order-456",
        "companyId": "UPDATED-company",
        "storeId": "UPDATED-store",
        "batchNumber": 2,
        "createdBy": "UPDATED-user",
        "createdAt": initial_data["createdAt"],  # Keep original creation time
        "updatedAt": datetime.utcnow(),
        "uid": "UPDATED-uid",
        "updatedBy": "UPDATED-modifier",
        "items": [
            {
                "productId": "prod-updated-1",
                "productName": "UPDATED Product 1",
                "quantity": 3,
                "price": 75.0, 
                "total": 225.0,
                "discount": 5.0,
                "vat": 20.0
            },
            {
                "productId": "prod-updated-2", 
                "productName": "UPDATED Product 2",
                "quantity": 2,
                "price": 100.0,
                "total": 200.0,
                "discount": 0.0,
                "vat": 24.0
            }
        ]
    }
    
    print(f"Updating orderDetails with ALL new field values: {order_detail_id}")
    db.collection("orderDetails").document(order_detail_id).set(updated_data)
    print("✅ OrderDetails updated - should see ALL fields updated in BigQuery")

def test_product_complete_update():
    """Test that product updates replace ALL fields in BigQuery"""
    product_id = "test-complete-update-product"
    
    # Initial product data
    initial_data = {
        "productName": "Initial Product Name",
        "companyId": "initial-company",
        "storeId": "initial-store",
        "category": "Initial Category",
        "sellingPrice": 50.0,
        "totalStock": 100,
        "status": "active",
        "createdBy": "initial-user",
        "createdAt": datetime.utcnow(),
        "updatedAt": datetime.utcnow(),
        "uid": "initial-uid",
        "isVatApplicable": False,
        "description": "Initial description"
    }
    
    print(f"\n=== Testing Products Complete Field Update ===")
    print(f"Creating initial product: {product_id}")
    db.collection("products").document(product_id).set(initial_data)
    print("Initial product created - waiting 5 seconds...")
    time.sleep(5)
    
    # Updated product data with ALL fields changed
    updated_data = {
        "productName": "COMPLETELY UPDATED Product Name",
        "companyId": "UPDATED-company",
        "storeId": "UPDATED-store",
        "category": "UPDATED Category",
        "sellingPrice": 125.0,
        "totalStock": 250,
        "status": "featured",
        "createdBy": "UPDATED-user",
        "createdAt": initial_data["createdAt"],  # Keep original creation time
        "updatedAt": datetime.utcnow(),
        "updatedBy": "UPDATED-modifier",
        "uid": "UPDATED-uid",
        "isVatApplicable": True,
        "description": "COMPLETELY UPDATED description with new details",
        "productCode": "UPD-001",
        "barcodeId": "UPDATED-BARCODE-123",
        "skuId": "UPDATED-SKU-456",
        "unitType": "pieces",
        "hasDiscount": True,
        "discountType": "percentage",
        "discountValue": 10.0,
        "isFavorite": True,
        "imageUrl": "https://updated-image.com/product.jpg"
    }
    
    print(f"Updating product with ALL new field values: {product_id}")
    db.collection("products").document(product_id).set(updated_data)
    print("✅ Product updated - should see ALL fields updated in BigQuery")

def main():
    print("🔄 Testing Complete Field Updates in Firestore Triggers")
    print("This will create documents, then update them with completely new data")
    print("to verify that ALL fields are updated in BigQuery, not just changed ones.\n")
    
    test_order_complete_update()
    test_orderdetails_complete_update() 
    test_product_complete_update()
    
    print(f"\n✅ All complete field update tests completed!")
    print(f"\nCheck the Firebase Function logs to confirm ALL fields were updated:")
    print(f"gcloud functions logs read sync_order_to_bigquery_update --region=asia-east1 --limit=5")
    print(f"gcloud functions logs read sync_order_details_update --region=asia-east1 --limit=5")
    print(f"gcloud functions logs read sync_products_to_bigquery_update --region=asia-east1 --limit=5")
    print(f"\nAlso verify in BigQuery that ALL fields show the UPDATED values, not initial ones.")

if __name__ == '__main__':
    main()