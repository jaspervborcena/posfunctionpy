from firebase_functions import https_fn
import requests
import json
from datetime import datetime
import uuid

# Import configuration 
from config import SUPABASE_URL, get_supabase_headers, ORDERS_TABLE, ORDER_DETAILS_TABLE

# Test Supabase connection endpoint
@https_fn.on_request(region="asia-east1")
def test_supabase_connection(req: https_fn.Request) -> https_fn.Response:
    """Test endpoint to verify Supabase connection"""
    
    # Test payload
    test_payload = {
        "invoice_number": "TEST_001",
        "total_amount": 100.00,
        "status": "test",
        "sold_to": "Test Customer"
    }
    
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        response = requests.post(f"{SUPABASE_URL}/rest/v1/orders", json=test_payload, headers=headers)
        
        return https_fn.Response(
            f"Status: {response.status_code}\nResponse: {response.text}",
            status=200
        )
    except Exception as e:
        return https_fn.Response(f"Error: {str(e)}", status=500)

# Mock order creation API endpoint - simulates the Firestore trigger
@https_fn.on_request(region="asia-east1")
def mock_order_insert(req: https_fn.Request) -> https_fn.Response:
    """API endpoint that creates a mock order and inserts it into Supabase
    This simulates what the Firestore trigger does but with mock data"""
    
    # Generate unique invoice number for each test
    unique_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Generate mock data similar to your Firestore collection
    mock_order_data = {
        "assignedCashierId": "mock_cashier_xyz123",
        "atpOrOcn": f"OCN-2025-MOCK{unique_id}",
        "birPermitNo": f"BIR-PERMIT-2025-MOCK{unique_id}",
        "businessAddress": "123 Mock Street, Test City",
        "cashSale": True,
        "companyId": "mock_company_abc123",
        "createdAt": datetime.now(),
        "date": datetime.now(),
        "discountAmount": 50,
        "grossAmount": 650,
        "inclusiveSerialNumber": f"MOCK{unique_id[:3]}-MOCK{unique_id[3:6]}",
        "invoiceNumber": f"MOCK-INV-{timestamp}-{unique_id}",
        "logoUrl": "https://example.com/mock-logo.png",
        "message": "Mock order - Thank you for testing!",
        "netAmount": 600,
        "soldTo": "Mock Customer",
        "status": "paid",
        "storeId": "mock_store_def456",
        "tin": "MOCK-TIN-123456789",
        "totalAmount": 600,
        "vatAmount": 50,
        "vatExemptAmount": 200,
        "vatableSales": 400,
        "zeroRatedSales": 0
    }
    
    # Use same payload mapping as the Firestore trigger
    mock_order_id = f"mock_order_{unique_id}"
    payload = {
        "order_id": mock_order_id,
        "assigned_cashier_id": mock_order_data.get("assignedCashierId"),
        "atp_or_ocn": mock_order_data.get("atpOrOcn"),
        "bir_permit_no": mock_order_data.get("birPermitNo"),
        "business_address": mock_order_data.get("businessAddress"),
        "cash_sale": mock_order_data.get("cashSale", False),
        "company_id": mock_order_data.get("companyId"),
        "created_at": mock_order_data.get("createdAt").isoformat() if mock_order_data.get("createdAt") else None,
        "date": mock_order_data.get("date").isoformat() if mock_order_data.get("date") else None,
        "discount_amount": mock_order_data.get("discountAmount", 0),
        "gross_amount": mock_order_data.get("grossAmount", 0),
        "inclusive_serial_number": mock_order_data.get("inclusiveSerialNumber"),
        "invoice_number": mock_order_data.get("invoiceNumber"),
        "logo_url": mock_order_data.get("logoUrl"),
        "message": mock_order_data.get("message"),
        "net_amount": mock_order_data.get("netAmount", 0),
        "sold_to": mock_order_data.get("soldTo", "Walk-in Customer"),
        "status": mock_order_data.get("status", "active"),
        "store_id": mock_order_data.get("storeId"),
        "tin": mock_order_data.get("tin"),
        "total_amount": mock_order_data.get("totalAmount", 0),
        "vat_amount": mock_order_data.get("vatAmount", 0),
        "vat_exempt_amount": mock_order_data.get("vatExemptAmount", 0),
        "vatable_sales": mock_order_data.get("vatableSales", 0),
        "zero_rated_sales": mock_order_data.get("zeroRatedSales", 0)
    }
    
    # Remove null values to avoid Supabase issues
    payload = {k: v for k, v in payload.items() if v is not None}
    
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        print(f"🧪 Mock API: Inserting mock order to Supabase...")
        print(f"📦 Mock payload: {payload}")
        
        response = requests.post(f"{SUPABASE_URL}/rest/v1/orders", json=payload, headers=headers)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📄 Response body: {response.text}")
        
        response_data = {
            "success": response.status_code in [200, 201],
            "status_code": response.status_code,
            "mock_data_sent": payload,
            "supabase_response": response.text,
            "message": "✅ Mock order inserted successfully!" if response.status_code in [200, 201] else "❌ Failed to insert mock order"
        }
        
        if response.status_code in [200, 201]:
            response_data["inserted_data"] = response.json()
            
        return https_fn.Response(
            json.dumps(response_data, indent=2, default=str),
            status=200,
            headers={"Content-Type": "application/json"}
        )
        
    except requests.exceptions.RequestException as req_err:
        error_response = {
            "success": False,
            "error_type": "Request Error",
            "error_message": str(req_err),
            "mock_data_sent": payload
        }
        return https_fn.Response(
            json.dumps(error_response, indent=2),
            status=500,
            headers={"Content-Type": "application/json"}
        )
    except Exception as e:
        error_response = {
            "success": False,
            "error_type": "Unexpected Error",
            "error_message": str(e),
            "mock_data_sent": payload
        }
        return https_fn.Response(
            json.dumps(error_response, indent=2),
            status=500,
            headers={"Content-Type": "application/json"}
        )

# Mock order details creation API endpoint
@https_fn.on_request(region="asia-east1")
def mock_order_details_insert(req: https_fn.Request) -> https_fn.Response:
    """API endpoint that creates mock order details and inserts them into Supabase"""
    
    # Generate unique IDs for each test
    unique_id = str(uuid.uuid4())[:8]
    order_id = f"mock_order_{unique_id}"
    
    # Generate mock order details data (typically multiple items per order)
    mock_order_details = [
        {
            "orderId": order_id,
            "productId": "prod_001",
            "productName": "Sample Product 1",
            "quantity": 2,
            "unitPrice": 150.00,
            "totalPrice": 300.00,
            "category": "Electronics",
            "sku": f"SKU-{unique_id}-001",
            "discount": 0,
            "createdAt": datetime.now()
        },
        {
            "orderId": order_id,
            "productId": "prod_002", 
            "productName": "Sample Product 2",
            "quantity": 1,
            "unitPrice": 300.00,
            "totalPrice": 300.00,
            "category": "Accessories",
            "sku": f"SKU-{unique_id}-002",
            "discount": 50,
            "createdAt": datetime.now()
        }
    ]
    
    # Prepare payloads for Supabase (matching your exact table structure)
    payloads = []
    for i, detail in enumerate(mock_order_details):
        mock_order_detail_id = f"mock_order_detail_{unique_id}_{i+1}"
        payload = {
            "order_details_id": mock_order_detail_id,
            "company_id": "mock_company_abc123",
            "order_id": detail.get("orderId"),
            "store_id": "mock_store_def456",
            "product_id": detail.get("productId"),
            "product_name": detail.get("productName"),
            "quantity": detail.get("quantity", 1),
            "price": detail.get("unitPrice", 0),
            "discount": detail.get("discount", 0),
            "vat": 0,
            "is_vat_exempt": False,
            "total": detail.get("totalPrice", 0)
        }
        # Remove null values
        payload = {k: v for k, v in payload.items() if v is not None}
        payloads.append(payload)
    
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    results = []
    
    try:
        print(f"🧪 Mock API: Inserting {len(payloads)} order details to Supabase...")
        
        for i, payload in enumerate(payloads):
            print(f"📦 Inserting detail {i+1}: {payload}")
            
            response = requests.post(f"{SUPABASE_URL}/rest/v1/order_details", json=payload, headers=headers)
            
            print(f"📊 Response {i+1} status: {response.status_code}")
            print(f"📄 Response {i+1} body: {response.text}")
            
            result = {
                "item_number": i + 1,
                "success": response.status_code in [200, 201],
                "status_code": response.status_code,
                "payload_sent": payload,
                "response": response.text
            }
            
            if response.status_code in [200, 201]:
                result["inserted_data"] = response.json()
            
            results.append(result)
        
        # Summary response
        successful_inserts = sum(1 for r in results if r["success"])
        
        response_data = {
            "success": successful_inserts == len(payloads),
            "total_items": len(payloads),
            "successful_inserts": successful_inserts,
            "failed_inserts": len(payloads) - successful_inserts,
            "message": f"✅ {successful_inserts}/{len(payloads)} order details inserted successfully!" if successful_inserts > 0 else "❌ All order details failed to insert",
            "results": results
        }
        
        return https_fn.Response(
            json.dumps(response_data, indent=2, default=str),
            status=200,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        error_response = {
            "success": False,
            "error_type": "Unexpected Error",
            "error_message": str(e),
            "payloads_attempted": payloads
        }
        return https_fn.Response(
            json.dumps(error_response, indent=2),
            status=500,
            headers={"Content-Type": "application/json"}
        )