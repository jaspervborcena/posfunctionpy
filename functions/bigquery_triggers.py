from firebase_functions import firestore_fn
from datetime import datetime
import json

# Import configuration 
from config import get_bigquery_client, BIGQUERY_ORDERS_TABLE, BIGQUERY_ORDER_DETAILS_TABLE

try:
    from google.cloud import bigquery
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    print("WARNING: BigQuery library not available. BigQuery triggers will be disabled.")

# BigQuery trigger for new order documents
@firestore_fn.on_document_created(document="orders/{orderId}", region="asia-east1")
def sync_order_to_bigquery(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🔥 Firestore trigger activated for new order - BigQuery sync")

    order_id = event.params["orderId"]
    data = event.data.to_dict()

    print(f"📄 Document ID: {order_id}")
    print(f"📦 Document data: {data}")
    print(f"📋 Available fields: {list(data.keys()) if data else 'No fields'}")

    if not data:
        print("⚠️ Warning: Document data is empty!")
        return

    try:
        client = get_bigquery_client()
        
        # Prepare payload for BigQuery (matching your schema)
        payload = {
            "assignedCashierEmail": data.get("assignedCashierEmail"),
            "assignedCashierId": data.get("assignedCashierId"),
            "assignedCashierName": data.get("assignedCashierName"),
            "atpOrOcn": data.get("atpOrOcn"),
            "birPermitNo": data.get("birPermitNo"),
            "cashSale": data.get("cashSale", False),
            "companyAddress": data.get("companyAddress"),
            "companyEmail": data.get("companyEmail"),
            "companyId": data.get("companyId"),
            "companyName": data.get("companyName"),
            "companyPhone": data.get("companyPhone"),
            "companyTaxId": data.get("companyTaxId"),
            "createdAt": data.get("createdAt").isoformat() if data.get("createdAt") else None,
            "createdBy": data.get("createdBy"),
            "customerInfo": {
                "address": data.get("customerInfo", {}).get("address") if data.get("customerInfo") else None,
                "customerId": data.get("customerInfo", {}).get("customerId") if data.get("customerInfo") else None,
                "fullName": data.get("customerInfo", {}).get("fullName") if data.get("customerInfo") else None,
                "tin": data.get("customerInfo", {}).get("tin") if data.get("customerInfo") else None
            } if data.get("customerInfo") else None,
            "date": data.get("date").isoformat() if data.get("date") else None,
            "discountAmount": float(data.get("discountAmount", 0)),
            "grossAmount": float(data.get("grossAmount", 0)),
            "inclusiveSerialNumber": data.get("inclusiveSerialNumber"),
            "invoiceNumber": data.get("invoiceNumber", order_id),
            "message": data.get("message"),
            "netAmount": float(data.get("netAmount", 0)),
            "payments": {
                "amountTendered": float(data.get("payments", {}).get("amountTendered", 0)) if data.get("payments") else 0,
                "changeAmount": float(data.get("payments", {}).get("changeAmount", 0)) if data.get("payments") else 0,
                "paymentDescription": data.get("payments", {}).get("paymentDescription") if data.get("payments") else None
            } if data.get("payments") else None,
            "status": data.get("status", "active"),
            "storeId": data.get("storeId"),
            "totalAmount": float(data.get("totalAmount", 0)),
            "uid": data.get("uid"),
            "updatedAt": data.get("updatedAt").isoformat() if data.get("updatedAt") else None,
            "updatedBy": data.get("updatedBy"),
            "vatAmount": float(data.get("vatAmount", 0)),
            "vatExemptAmount": float(data.get("vatExemptAmount", 0)),
            "vatableSales": float(data.get("vatableSales", 0)),
            "zeroRatedSales": float(data.get("zeroRatedSales", 0))
        }
        
        # Remove null values to avoid BigQuery issues
        def clean_payload(obj):
            if isinstance(obj, dict):
                return {k: clean_payload(v) for k, v in obj.items() if v is not None}
            return obj
        
        payload = clean_payload(payload)
        
        # Add the Firestore document ID as a field
        payload["orderId"] = order_id
        
        print(f"🧹 Cleaned payload for BigQuery: {payload}")

        # Insert into BigQuery
        table = client.get_table(BIGQUERY_ORDERS_TABLE)
        errors = client.insert_rows_json(table, [payload])
        
        if errors:
            print(f"❌ BigQuery insert failed with errors: {errors}")
        else:
            print("✅ BigQuery insert successful!")
            print(f"📋 Inserted order: {order_id}")

    except Exception as e:
        print(f"❌ Unexpected error syncing to BigQuery: {e}")


# BigQuery trigger for new order details documents  
@firestore_fn.on_document_created(document="orderDetails/{orderDetailId}", region="asia-east1")
def sync_order_details_to_bigquery(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🔥🔥🔥 FIRESTORE TRIGGER ACTIVATED FOR ORDER DETAILS - BigQuery sync 🔥🔥🔥")
    
    try:
        order_detail_id = event.params["orderDetailId"]
        data = event.data.to_dict()

        print(f"📄 Order Detail ID: {order_detail_id}")
        print(f"📋 Order Detail data: {data}")
        print(f"📋 Available fields: {list(data.keys()) if data else 'No fields'}")

        if not data:
            print("⚠️ Warning: Order detail data is empty!")
            return

        # Get fields from Firestore document
        company_id = data.get("companyId")
        order_id = data.get("orderId")
        store_id = data.get("storeId")
        items = data.get("items", [])
        created_at = data.get("createdAt")
        created_by = data.get("createdBy")
        uid = data.get("uid")
        updated_at = data.get("updatedAt")
        updated_by = data.get("updatedBy")
        batch_number = data.get("batchNumber")
        
        print(f"📋 Found {len(items)} items to process")
        print(f"🏢 Company ID: {company_id}")
        print(f"📝 Order ID: {order_id}")
        print(f"🏪 Store ID: {store_id}")

        if not items:
            print("⚠️ Warning: No items found in the document!")
            return

        client = get_bigquery_client()
        
        # Prepare payload matching your BigQuery schema (with nested items array)
        payload = {
            "batchNumber": int(batch_number) if batch_number else None,
            "companyId": company_id,
            "createdAt": created_at.isoformat() if created_at else None,
            "createdBy": created_by,
            "orderId": order_id,
            "storeId": store_id,
            "uid": uid,
            "updatedAt": updated_at.isoformat() if updated_at else None,
            "updatedBy": updated_by,
            "items": []
        }
        
        # Process items array (keep as nested structure)
        for i, item in enumerate(items):
            print(f"\n📦 Processing item {i+1}/{len(items)}: {item}")
            
            item_payload = {
                "productId": item.get("productId"),
                "productName": item.get("productName"),
                "quantity": int(item.get("quantity", 1)),
                "price": float(item.get("price", 0)),
                "discount": float(item.get("discount", 0)),
                "vat": float(item.get("vat", 0)),
                "isVatExempt": bool(item.get("isVatExempt", False)),
                "total": float(item.get("total", 0))
            }
            
            # Remove null values from item
            item_payload = {k: v for k, v in item_payload.items() if v is not None}
            payload["items"].append(item_payload)
        
        # Remove null values from main payload
        payload = {k: v for k, v in payload.items() if v is not None}
        
        # Add the Firestore document ID as a field
        payload["orderDetailsId"] = order_detail_id
        
        print(f"🧹 Final payload for BigQuery: {payload}")

        # Insert into BigQuery
        table = client.get_table(BIGQUERY_ORDER_DETAILS_TABLE)
        errors = client.insert_rows_json(table, [payload])
        
        if errors:
            print(f"❌ BigQuery insert failed with errors: {errors}")
        else:
            print(f"✅ BigQuery insert successful! Order details with {len(items)} items")
            print(f"📋 Order Details ID: {order_detail_id}")

    except Exception as e:
        print(f"❌ Unexpected error syncing order details to BigQuery: {e}")