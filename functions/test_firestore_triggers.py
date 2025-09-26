from firebase_functions import https_fn
from firebase_admin import firestore
import json
from datetime import datetime
import uuid

# Test endpoint that creates actual Firestore documents to trigger sync
@https_fn.on_request(region="asia-east1")
def test_firestore_trigger_order(req: https_fn.Request) -> https_fn.Response:
    """Create a real Firestore order document to test if triggers work"""
    
    try:
        db = firestore.client()
        
        # Generate unique test data
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now()
        
        # Create test order document - this should trigger sync_order_to_supabase
        order_data = {
            "assignedCashierId": "test_cashier_123",
            "atpOrOcn": "12345",
            "birPermitNo": "TEST-PERMIT-001",
            "businessAddress": "Test Business Address",
            "cashSale": True,
            "companyId": "fuREf6Lixrhhi2qiAa5N",
            "createdAt": timestamp,
            "date": timestamp,
            "discountAmount": 0,
            "grossAmount": 250.0,
            "inclusiveSerialNumber": f"ISN-{unique_id}",
            "invoiceNumber": f"TEST-INV-{unique_id}",
            "logoUrl": "https://example.com/logo.png",
            "message": "Test order created for trigger testing",
            "netAmount": 250.0,
            "soldTo": "Test Customer",
            "status": "active",
            "storeId": "5sWqCApkZo6Q094sngb7",
            "tin": "123-456-789-000",
            "totalAmount": 250.0,
            "vatAmount": 0,
            "vatExemptAmount": 250.0,
            "vatableSales": 0,
            "zeroRatedSales": 0
        }
        
        # Add document to orders collection - THIS SHOULD TRIGGER THE SYNC
        doc_ref = db.collection('orders').add(order_data)
        order_id = doc_ref[1].id
        
        print(f"🔥 Created Firestore order document: {order_id}")
        print(f"📄 Order data: {order_data}")
        
        return https_fn.Response(
            json.dumps({
                "success": True,
                "message": "Firestore order document created successfully!",
                "order_id": order_id,
                "trigger_expected": "sync_order_to_supabase should have been triggered",
                "check_logs": "Check Firebase Functions logs for trigger execution",
                "order_data": order_data,
                "timestamp": timestamp.isoformat()
            }),
            status=200,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        print(f"❌ Error creating Firestore document: {str(e)}")
        return https_fn.Response(
            json.dumps({
                "success": False,
                "error": str(e),
                "message": "Failed to create Firestore order document"
            }),
            status=500,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )

@https_fn.on_request(region="asia-east1")
def test_firestore_trigger_order_details(req: https_fn.Request) -> https_fn.Response:
    """Create a real Firestore orderDetails document to test if triggers work"""
    
    try:
        db = firestore.client()
        
        # Generate unique test data
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now()
        
        # Create test order details document - this should trigger sync_order_details_to_supabase
        order_details_data = {
            "companyId": "fuREf6Lixrhhi2qiAa5N",
            "orderId": f"TEST-ORDER-{unique_id}",
            "storeId": "5sWqCApkZo6Q094sngb7",
            "createdAt": timestamp,
            "items": [
                {
                    "productId": "PROD001",
                    "productName": "Test Product 1",
                    "quantity": 2,
                    "price": 50.0,
                    "discount": 0,
                    "vat": 0,
                    "isVatExempt": True,
                    "total": 100.0
                },
                {
                    "productId": "PROD002", 
                    "productName": "Test Product 2",
                    "quantity": 1,
                    "price": 150.0,
                    "discount": 10.0,
                    "vat": 0,
                    "isVatExempt": True,
                    "total": 140.0
                }
            ]
        }
        
        # Add document to orderDetails collection - THIS SHOULD TRIGGER THE SYNC
        doc_ref = db.collection('orderDetails').add(order_details_data)
        order_details_id = doc_ref[1].id
        
        print(f"🔥 Created Firestore orderDetails document: {order_details_id}")
        print(f"📄 OrderDetails data: {order_details_data}")
        
        return https_fn.Response(
            json.dumps({
                "success": True,
                "message": "Firestore orderDetails document created successfully!",
                "order_details_id": order_details_id,
                "trigger_expected": "sync_order_details_to_supabase should have been triggered",
                "check_logs": "Check Firebase Functions logs for trigger execution",
                "items_count": len(order_details_data["items"]),
                "expected_supabase_rows": len(order_details_data["items"]),
                "order_details_data": order_details_data,
                "timestamp": timestamp.isoformat()
            }),
            status=200,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        print(f"❌ Error creating Firestore orderDetails document: {str(e)}")
        return https_fn.Response(
            json.dumps({
                "success": False,
                "error": str(e),
                "message": "Failed to create Firestore orderDetails document"
            }),
            status=500,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )