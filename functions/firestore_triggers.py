from firebase_functions import firestore_fn
import requests
from datetime import datetime

# Import configuration 
from config import SUPABASE_URL, get_supabase_headers, ORDERS_TABLE, ORDER_DETAILS_TABLE

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
        print(f"📋 Order Detail data: {data}")
        print(f"📋 Available fields: {list(data.keys()) if data else 'No fields'}")
        print(f"📋 orderId from data: '{data.get('orderId')}'")

        if not data:
            print("⚠️ Warning: Order detail data is empty!")
            return

        # Get common fields for all items
        company_id = data.get("companyId")
        order_id = data.get("orderId")
        store_id = data.get("storeId")
        items = data.get("items", [])
        
        print(f"📋 Found {len(items)} items to process")
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