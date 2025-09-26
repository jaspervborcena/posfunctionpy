from firebase_functions import https_fn, firestore_fn
from firebase_admin import initialize_app
import requests

# Initialize Firebase Admin SDK
initialize_app()

# Supabase configuration
SUPABASE_URL = "https://etwbbynzpgdsxdxuiasl.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV0d2JieW56cGdkc3hkeHVpYXNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTg1MTY4NTQsImV4cCI6MjA3NDA5Mjg1NH0.vNd1B_xxbOo5JnUkKfgflwikIA9tz2T7ym4mQWlCUJ0"
SUPABASE_SECRET_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV0d2JieW56cGdkc3hkeHVpYXNsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODUxNjg1NCwiZXhwIjoyMDc0MDkyODU0fQ.b9ELJBIQReCvGiUCVPXC0kQgZ_nAaXuTqaVsVZT2LSQ"

# Optional test endpoint
@https_fn.on_request(region="asia-east1")
def on_request_example(req: https_fn.Request) -> https_fn.Response:
    return https_fn.Response("Hello world!")

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
    
    import json
    from datetime import datetime
    import uuid
    
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
    
    import json
    from datetime import datetime
    import uuid
    
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

# Firestore trigger for new order documents
@firestore_fn.on_document_created(document="orders/{orderId}", region="asia-east1")
def sync_order_to_supabase(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🔥 Firestore trigger activated for new order")

    order_id = event.params["orderId"]
    data = event.data.to_dict()

    print(f"📄 Document ID: {order_id}")
    print(f"📦 Document data: {data}")
    print(f"📋 Available fields: {list(data.keys()) if data else 'No fields'}")

    if not data:
        print("⚠️ Warning: Document data is empty!")
        return

    # Prepare payload for Supabase (mapping camelCase Firestore to snake_case Supabase)
    payload = {
        "order_id": order_id,  # Add the Firestore document ID as order_id
        "assigned_cashier_id": data.get("assignedCashierId"),
        "atp_or_ocn": data.get("atpOrOcn"),
        "bir_permit_no": data.get("birPermitNo"),
        "business_address": data.get("businessAddress"),
        "cash_sale": data.get("cashSale", False),
        "company_id": data.get("companyId"),
        "created_at": data.get("createdAt").isoformat() if data.get("createdAt") else None,
        "date": data.get("date").isoformat() if data.get("date") else None,
        "discount_amount": data.get("discountAmount", 0),
        "gross_amount": data.get("grossAmount", 0),
        "inclusive_serial_number": data.get("inclusiveSerialNumber"),
        "invoice_number": data.get("invoiceNumber", order_id),  # fallback to document ID
        "logo_url": data.get("logoUrl"),
        "message": data.get("message"),
        "net_amount": data.get("netAmount", 0),
        "sold_to": data.get("soldTo", "Walk-in Customer"),
        "status": data.get("status", "active"),
        "store_id": data.get("storeId"),
        "tin": data.get("tin"),
        "total_amount": data.get("totalAmount", 0),
        "vat_amount": data.get("vatAmount", 0),
        "vat_exempt_amount": data.get("vatExemptAmount", 0),
        "vatable_sales": data.get("vatableSales", 0),
        "zero_rated_sales": data.get("zeroRatedSales", 0)
    }
    
    # Remove null values to avoid Supabase issues
    payload = {k: v for k, v in payload.items() if v is not None}
    print(f"🧹 Cleaned payload (non-null values): {payload}")

    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    print(f"📤 Sending payload to Supabase: {payload}")

    try:
        response = requests.post(f"{SUPABASE_URL}/rest/v1/orders", json=payload, headers=headers)
        print(f"📊 Response status: {response.status_code}")
        print("📄 Response body:", response.text)

        if response.status_code in [200, 201]:
            print("✅ Supabase insert successful!")
            print(f"📋 Inserted data: {response.json()}")
        else:
            print(f"❌ Supabase insert failed with status {response.status_code}")
            print(f"📄 Response body: {response.text}")

        response.raise_for_status()

    except requests.exceptions.HTTPError as http_err:
        print("❌ HTTP error occurred:", http_err)
    except requests.exceptions.RequestException as req_err:
        print("❌ Request error occurred:", req_err)
    except Exception as e:
        print("❌ Unexpected error:", e)

# Firestore trigger for new order details documents  
@firestore_fn.on_document_created(document="orderDetails/{orderDetailId}", region="asia-east1")
def sync_order_details_to_supabase(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🔥🔥🔥 FIRESTORE TRIGGER ACTIVATED FOR ORDER DETAILS 🔥🔥🔥")
    print("🚨 TRIGGER IS WORKING! Document created in orderDetails collection!")
    print(f"🚨 Collection: orderDetails")
    print(f"🚨 Document ID: {event.params.get('orderDetailId')}")
    print(f"🚨 Timestamp: {event.data.create_time}")
    print("🚨 If you see this message, the trigger is working!")
    
    try:
        order_detail_id = event.params["orderDetailId"]
        data = event.data.to_dict()

        print(f"📄 Order Detail ID: {order_detail_id}")
        print(f"� Order Detail data: {data}")
        print(f"� Available fields: {list(data.keys()) if data else 'No fields'}")
        print(f"� orderId from data: '{data.get('orderId')}'")

        if not data:
            print("⚠️ Warning: Order detail data is empty!")
            return

        # Get common fields for all items
        company_id = data.get("companyId")
        order_id = data.get("orderId")
        store_id = data.get("storeId")
        items = data.get("items", [])
        
        print(f"� Found {len(items)} items to process")
        print(f"🏢 Company ID: {company_id}")
        print(f"📝 Order ID: {order_id}")
        print(f"🏪 Store ID: {store_id}")

        if not items:
            print("⚠️ Warning: No items found in the document!")
            return

        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        # Process each item in the items array
        successful_inserts = 0
        for i, item in enumerate(items):
            print(f"\n📦 Processing item {i+1}/{len(items)}: {item}")
            
            # Prepare flattened payload for each item
            payload = {
                "order_details_id": order_detail_id,  # Use orderDetails document ID
                "company_id": company_id,
                "order_id": order_id,
                "store_id": store_id,
                "product_id": item.get("productId"),
                "product_name": item.get("productName"),
                "quantity": item.get("quantity", 1),
                "price": item.get("price", 0),
                "discount": item.get("discount", 0),
                "vat": item.get("vat", 0),
                "is_vat_exempt": item.get("isVatExempt", False),
                "total": item.get("total", 0)
            }
            
            # Remove null values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            print(f"🧹 Item {i+1} payload: {payload}")
            print(f"🔍 Item {i+1} order_details_id: '{payload.get('order_details_id')}'")
            print(f"🔍 Item {i+1} product_id: '{payload.get('product_id')}'")
            print(f"🔍 Item {i+1} order_id: '{payload.get('order_id')}'")

            print(f"📤 Sending item {i+1} payload to Supabase...")

            try:
                response = requests.post(f"{SUPABASE_URL}/rest/v1/order_details", json=payload, headers=headers)
                print(f"📊 Item {i+1} response status: {response.status_code}")
                print(f"📄 Item {i+1} response body: {response.text}")

                if response.status_code in [200, 201]:
                    print(f"✅ Item {i+1} Supabase insert successful!")
                    print(f"📋 Item {i+1} inserted data: {response.json()}")
                    successful_inserts += 1
                else:
                    print(f"❌ Item {i+1} Supabase insert failed with status {response.status_code}")
                    print(f"📄 Response body: {response.text}")

                response.raise_for_status()

            except requests.exceptions.HTTPError as http_err:
                print(f"❌ Item {i+1} HTTP error occurred:", http_err)
            except requests.exceptions.RequestException as req_err:
                print(f"❌ Item {i+1} request error occurred:", req_err)
            except Exception as e:
                print(f"❌ Item {i+1} unexpected error:", e)
        
        print(f"\n🎉 SUMMARY: Successfully inserted {successful_inserts}/{len(items)} items to Supabase")
    
    except Exception as function_error:
        print("🚨 CRITICAL ERROR in order details trigger function:")
        print(f"🚨 Error type: {type(function_error)}")
        print(f"🚨 Error message: {str(function_error)}")
        print(f"🚨 Event data: {event}")
        import traceback
        print(f"🚨 Full traceback: {traceback.format_exc()}")