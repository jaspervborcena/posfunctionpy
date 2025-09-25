from firebase_functions import https_fn, firestore_fn
from firebase_admin import initialize_app
import requests

# Initialize Firebase Admin SDK
initialize_app()

# Supabase configuration
SUPABASE_URL = "https://etwbbynzpgdsxdxuiasl.supabase.co"
# TODO: Replace with your anon/public key, not secret key
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV0d2JieW56cGdkc3hkeHVpYXNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTg1MTY4NTQsImV4cCI6MjA3NDA5Mjg1NH0.vNd1B_xxbOo5JnUkKfgflwikIA9tz2T7ym4mQWlCUJ0"  # Replace with actual anon key
SUPABASE_SECRET_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV0d2JieW56cGdkc3hkeHVpYXNsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODUxNjg1NCwiZXhwIjoyMDc0MDkyODU0fQ.b9ELJBIQReCvGiUCVPXC0kQgZ_nAaXuTqaVsVZT2LSQ"  # Keep for service role if needed

# Optional test endpoint
@https_fn.on_request()
def on_request_example(req: https_fn.Request) -> https_fn.Response:
    return https_fn.Response("Hello world!")

# Test Supabase connection endpoint
@https_fn.on_request()
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

# Firestore trigger for new user documents
@firestore_fn.on_document_created(document="users/{userId}")
def on_user_created(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print(f"New user created: {event.data.to_dict()}")

@firestore_fn.on_document_created(document="orders/{orderId}")
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