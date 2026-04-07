from firebase_functions import firestore_fn
from datetime import datetime
import json
from datetime import timezone, timedelta
from decimal import Decimal, InvalidOperation


# Helper: normalize various timestamp shapes to ISO-8601 string or None
def ts_to_iso(val):
    """Convert a variety of timestamp representations into an ISO-8601 string.

    Handles:
    - datetime.datetime
    - numeric milliseconds or seconds (int/float)
    - dicts from some JSON payloads with 'seconds'/'nanos' or '_seconds'/'_nanoseconds'
    - objects that expose to_datetime()/ToDatetime() (Firestore Timestamp-like)
    - strings (returned as-is)
    Returns None when conversion isn't possible.
    """
    if val is None:
        return None
    try:
        # already a string
        if isinstance(val, str):
            return val
        # python datetime
        if isinstance(val, datetime):
            return val.isoformat()
        # Firestore Timestamp-like: try common method names
        if hasattr(val, 'to_datetime'):
            try:
                return val.to_datetime().isoformat()
            except Exception:
                pass
        if hasattr(val, 'ToDatetime'):
            try:
                return val.ToDatetime().isoformat()
            except Exception:
                pass

        # Dict shapes from some clients or protobuf JSON
        if isinstance(val, dict):
            # Handle Firestore serverTimestamp placeholder
            if '_methodName' in val and val.get('_methodName') == 'serverTimestamp':
                # Return current timestamp as server timestamps are placeholders
                return datetime.now(timezone.utc).isoformat()
            if 'seconds' in val:
                secs = float(val.get('seconds', 0))
                nanos = float(val.get('nanos', 0))
                dt = datetime.fromtimestamp(secs + nanos / 1e9, tz=timezone.utc)
                return dt.isoformat()
            if '_seconds' in val:
                secs = float(val.get('_seconds', 0))
                nanos = float(val.get('_nanoseconds', 0))
                dt = datetime.fromtimestamp(secs + nanos / 1e9, tz=timezone.utc)
                return dt.isoformat()

        # Numeric — guess milliseconds vs seconds
        if isinstance(val, (int, float)):
            # heuristics: values > 1e12 are ms since epoch
            v = float(val)
            if v > 1e12:
                dt = datetime.fromtimestamp(v / 1000.0, tz=timezone.utc)
            else:
                dt = datetime.fromtimestamp(v, tz=timezone.utc)
            return dt.isoformat()
    except Exception:
        pass

    # last resort: stringify
    try:
        return str(val)
    except Exception:
        return None


def normalize_status_history(entries):
    """Normalize status history entries to a BigQuery-friendly array of structs."""
    if not isinstance(entries, list):
        return []

    normalized = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        normalized.append({
            "status": entry.get("status"),
            "changedAt": ts_to_iso(entry.get("changedAt")),
            "changedBy": entry.get("changedBy")
        })
    return normalized


def normalize_string_list(values):
    """Return a list of strings for array parameters."""
    if not isinstance(values, list):
        return []
    return [str(v) for v in values if v is not None]

# Import configuration 
from bq_helpers import build_product_payload

try:
    from google.cloud import bigquery
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    print("WARNING: BigQuery library not available. BigQuery triggers will be disabled.")

from config import get_bigquery_client, get_bigquery_table_name

# BigQuery trigger for new order documents
@firestore_fn.on_document_created(document="orders/{orderId}", region="asia-east1")
def sync_order_to_bigquery(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🔥 Firestore trigger activated for new order - BigQuery sync")

    order_id = event.params["orderId"]
    # Defensive normalization and logging
    table_name = get_bigquery_table_name('orders')
    print(f"ℹ️ Using BigQuery table for orders: {table_name}")
    order_id = str(order_id)
    data = event.data.to_dict()

    print(f"📄 Document ID: {order_id}")
    print(f"📦 Document data: {data}")
    print(f"📋 Available fields: {list(data.keys()) if data else 'No fields'}")

    if not data:
        print("⚠️ Warning: Document data is empty!")
        return

    try:
        client = get_bigquery_client()
        
        # Check if orderId already exists in BigQuery
        check_query = f"SELECT COUNT(*) as count FROM `{table_name}` WHERE orderId = @orderId"
        check_params = [bigquery.ScalarQueryParameter("orderId", "STRING", order_id)]
        check_job_config = bigquery.QueryJobConfig(query_parameters=check_params)
        check_job = client.query(check_query, job_config=check_job_config)
        result = list(check_job.result())
        
        if result[0].count > 0:
            print(f"⏭️ Order {order_id} already exists in BigQuery - skipping duplicate insert")
            return
        
        # Prepare payload for BigQuery (matching your schema)
        payload = {
            "assignedCashierEmail": data.get("assignedCashierEmail"),
            "assignedCashierId": data.get("assignedCashierId"),
            "assignedCashierName": data.get("assignedCashierName"),
            "atpOrOcn": data.get("atpOrOcn"),
            "birPermitNo": data.get("birPermitNo"),
            "cashSale": data.get("cashSale", False),
            "chargeSale": data.get("chargeSale", False),
            "companyAddress": data.get("companyAddress"),
            "companyEmail": data.get("companyEmail"),
            "companyId": data.get("companyId"),
            "companyName": data.get("companyName"),
            "companyPhone": data.get("companyPhone"),
            "companyTaxId": data.get("companyTaxId"),
            "createdAt": ts_to_iso(data.get("createdAt")),
            "createdBy": data.get("createdBy"),
            "customerInfo": {
                "address": data.get("customerInfo", {}).get("address") if data.get("customerInfo") else None,
                "customerId": data.get("customerInfo", {}).get("customerId") if data.get("customerInfo") else None,
                "fullName": data.get("customerInfo", {}).get("fullName") if data.get("customerInfo") else None,
                "tin": data.get("customerInfo", {}).get("tin") if data.get("customerInfo") else None
            } if data.get("customerInfo") else None,
            "date": ts_to_iso(data.get("date")),
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
            "statusHistory": normalize_status_history(data.get("statusHistory")),
            "statusTags": normalize_string_list(data.get("statusTags")),
            "storeId": data.get("storeId"),
            "tableNumber": data.get("tableNumber"),
            "totalAmount": float(data.get("totalAmount", 0)),
            "uid": data.get("uid"),
            "updatedAt": ts_to_iso(data.get("updatedAt")),
            "updatedBy": data.get("updatedBy"),
            "vatAmount": float(data.get("vatAmount", 0)),
            "vatExemptAmount": float(data.get("vatExemptAmount", 0)),
            "vatableSales": float(data.get("vatableSales", 0)),
            "zeroRatedSales": float(data.get("zeroRatedSales", 0))
        }
        
        # Remove null values and convert Decimal to JSON-friendly types
        def clean_payload(obj):
            if isinstance(obj, dict):
                return {k: clean_payload(v) for k, v in obj.items() if v is not None}
            if isinstance(obj, list):
                return [clean_payload(v) for v in obj]
            if isinstance(obj, Decimal):
                return str(obj)
            return obj
        
        payload = clean_payload(payload)
        
        # Add the Firestore document ID as a field
        payload["orderId"] = order_id
        
        print(f"🧹 Cleaned payload for BigQuery: {payload}")

        # Stream insert the order (same proven pattern as orderDetails)
        try:
            table = client.get_table(table_name)
            print(f"📤 Inserting order payload into {table_name}")
            errors = client.insert_rows_json(table, [payload])
            if errors:
                print(f"❌ BigQuery insert failed with errors: {errors}")
            else:
                print(f"✅ BigQuery insert successful for order {order_id}")
        except Exception as ie:
            print(f"❌ Exception while inserting order to BigQuery: {ie}")

    except Exception as e:
        print(f"❌ Unexpected error syncing to BigQuery: {e}")


# Orders update handler: COMPLETE field update using MERGE (updates ALL fields from Firestore)
@firestore_fn.on_document_updated(document="orders/{orderId}", region="asia-east1")
def sync_order_to_bigquery_update(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🔁 Firestore trigger activated for updated order - BigQuery sync")
    try:
        order_id = event.params.get("orderId")
        # Defensive normalization and logging
        print(f"ℹ️ Using BigQuery table for orders: {get_bigquery_table_name('orders')}")
        order_id = str(order_id) if order_id is not None else order_id
        after = event.data.after.to_dict()

        print(f"📄 Order ID (updated): {order_id}")
        print(f"📦 New order data (ALL FIELDS): {after}")
        print(f"📋 Updating ALL fields for orderId: {order_id}")

        if not after:
            print("⚠️ Warning: Updated order document empty — skipping")
            return
        
        if not order_id:
            print("⚠️ Warning: Order ID is missing — skipping")
            return

        client = get_bigquery_client()
        
        # Verify the order exists in BigQuery before updating
        table_name = get_bigquery_table_name('orders')
        check_query = f"SELECT COUNT(*) as count FROM `{table_name}` WHERE orderId = @orderId"
        check_params = [bigquery.ScalarQueryParameter("orderId", "STRING", order_id)]
        check_job_config = bigquery.QueryJobConfig(query_parameters=check_params)
        check_job = client.query(check_query, job_config=check_job_config)
        result = list(check_job.result())
        
        if result[0].count == 0:
            print(f"⚠️ Order {order_id} does not exist in BigQuery - creating new record instead of update")
        else:
            print(f"✅ Order {order_id} exists in BigQuery - proceeding with complete field update")

        # Delete existing row then re-insert updated data (same proven pattern as orderDetails)
        try:
            delete_query = f"DELETE FROM `{table_name}` WHERE orderId = @orderId"
            del_params = [bigquery.ScalarQueryParameter("orderId", "STRING", order_id)]
            del_config = bigquery.QueryJobConfig(query_parameters=del_params)
            del_job = client.query(delete_query, job_config=del_config)
            del_job.result()
            print(f"🗑️ Removed existing order {order_id} (if any)")
        except Exception as de:
            print(f"⚠️ Warning deleting existing order row: {de}")

        upd_payload = {
            "orderId": order_id,
            "assignedCashierEmail": after.get("assignedCashierEmail"),
            "assignedCashierId": after.get("assignedCashierId"),
            "assignedCashierName": after.get("assignedCashierName"),
            "atpOrOcn": after.get("atpOrOcn"),
            "birPermitNo": after.get("birPermitNo"),
            "cashSale": bool(after.get("cashSale", False)),
            "chargeSale": bool(after.get("chargeSale", False)),
            "companyAddress": after.get("companyAddress"),
            "companyEmail": after.get("companyEmail"),
            "companyId": after.get("companyId"),
            "companyName": after.get("companyName"),
            "companyPhone": after.get("companyPhone"),
            "companyTaxId": after.get("companyTaxId"),
            "createdAt": ts_to_iso(after.get("createdAt")),
            "createdBy": after.get("createdBy"),
            "customerInfo": {
                "address": after.get("customerInfo", {}).get("address") if after.get("customerInfo") else None,
                "customerId": after.get("customerInfo", {}).get("customerId") if after.get("customerInfo") else None,
                "fullName": after.get("customerInfo", {}).get("fullName") if after.get("customerInfo") else None,
                "tin": after.get("customerInfo", {}).get("tin") if after.get("customerInfo") else None
            } if after.get("customerInfo") else None,
            "date": ts_to_iso(after.get("date")),
            "discountAmount": float(after.get("discountAmount", 0)) if after.get("discountAmount") is not None else None,
            "grossAmount": float(after.get("grossAmount", 0)) if after.get("grossAmount") is not None else None,
            "inclusiveSerialNumber": after.get("inclusiveSerialNumber"),
            "invoiceNumber": after.get("invoiceNumber", order_id),
            "message": after.get("message"),
            "netAmount": float(after.get("netAmount", 0)) if after.get("netAmount") is not None else None,
            "payments": {
                "amountTendered": float(after.get("payments", {}).get("amountTendered", 0)) if after.get("payments") else 0,
                "changeAmount": float(after.get("payments", {}).get("changeAmount", 0)) if after.get("payments") else 0,
                "paymentDescription": after.get("payments", {}).get("paymentDescription") if after.get("payments") else None
            } if after.get("payments") else None,
            "status": after.get("status", "active"),
            "statusHistory": normalize_status_history(after.get("statusHistory")),
            "statusTags": normalize_string_list(after.get("statusTags")),
            "storeId": after.get("storeId"),
            "tableNumber": after.get("tableNumber"),
            "totalAmount": float(after.get("totalAmount", 0)) if after.get("totalAmount") is not None else None,
            "uid": after.get("uid"),
            "updatedAt": ts_to_iso(after.get("updatedAt")),
            "updatedBy": after.get("updatedBy"),
            "vatAmount": float(after.get("vatAmount", 0)) if after.get("vatAmount") is not None else None,
            "vatExemptAmount": float(after.get("vatExemptAmount", 0)) if after.get("vatExemptAmount") is not None else None,
            "vatableSales": float(after.get("vatableSales", 0)) if after.get("vatableSales") is not None else None,
            "zeroRatedSales": float(after.get("zeroRatedSales", 0)) if after.get("zeroRatedSales") is not None else None
        }

        def _clean(obj):
            if isinstance(obj, dict):
                return {k: _clean(v) for k, v in obj.items() if v is not None}
            if isinstance(obj, list):
                return [_clean(v) for v in obj]
            return obj

        upd_payload = _clean(upd_payload)
        print(f"🧹 Updated order payload: {upd_payload}")

        try:
            table = client.get_table(table_name)
            print(f"📤 Inserting updated order payload into {table_name}")
            errors = client.insert_rows_json(table, [upd_payload])
            if errors:
                print(f"❌ BigQuery update insert failed with errors: {errors}")
                print(f"❗ Failed payload: {upd_payload}")
            else:
                print(f"✅ BigQuery update (re-insert) successful for order {order_id}")
        except Exception as ie:
            print(f"❌ Exception while inserting updated order to BigQuery: {ie}")

    except Exception as e:
        print(f"❌ Unexpected error syncing updated order to BigQuery: {e}")


# Orders delete handler
@firestore_fn.on_document_deleted(document="orders/{orderId}", region="asia-east1")
def sync_order_to_bigquery_delete(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🗑️ Firestore trigger activated for deleted order - BigQuery sync")
    try:
        order_id = event.params.get("orderId")
        client = get_bigquery_client()
        table_name = get_bigquery_table_name('orders')
        delete_query = f"DELETE FROM `{table_name}` WHERE orderId = @orderId"
        params = [bigquery.ScalarQueryParameter("orderId", "STRING", order_id)]
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        job = client.query(delete_query, job_config=job_config)
        job.result()
        print(f"✅ Deleted order {order_id} from BigQuery (if existed)")
    except Exception as e:
        print(f"❌ Unexpected error deleting order from BigQuery: {e}")


# BigQuery trigger for new orderDetails documents  
@firestore_fn.on_document_created(document="orderDetails/{orderDetailsId}", region="asia-east1")
def sync_order_details_to_bigquery(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    """Sync newly created Firestore orderDetails documents into BigQuery orderDetails table."""
    print("🔥 Firestore trigger activated for new orderDetails - BigQuery sync")

    order_detail_id = event.params["orderDetailsId"]
    data = event.data.to_dict()

    print(f"📄 Order Detail ID: {order_detail_id}")
    print(f"📦 Order Detail data: {data}")
    print(f"📋 Available fields: {list(data.keys()) if data else 'No fields'}")

    if not data:
        print("⚠️ Warning: Order detail data is empty!")
        return

    try:
        client = get_bigquery_client()

        table_name = get_bigquery_table_name('orderDetails')
        # Check if orderDetailsId already exists in BigQuery
        check_query = f"SELECT COUNT(*) as count FROM `{table_name}` WHERE orderDetailsId = @orderDetailsId"
        check_params = [bigquery.ScalarQueryParameter("orderDetailsId", "STRING", order_detail_id)]
        check_job_config = bigquery.QueryJobConfig(query_parameters=check_params)
        check_job = client.query(check_query, job_config=check_job_config)
        result = list(check_job.result())
        
        if result[0].count > 0:
            print(f"⏭️ OrderDetails {order_detail_id} already exists in BigQuery - skipping duplicate insert")
            return

        # Build payload using centralized helper to standardize column names
        from bq_helpers import build_orderdetails_payload
        payload = build_orderdetails_payload(order_detail_id, data)

        print(f"🧹 Final payload for BigQuery (orderDetails): {payload}")

        # Use streaming insert for orderDetails (keeps nested items intact)
        try:
            table = client.get_table(table_name)
            print(f"📤 Inserting payload into {table_name}")
            errors = client.insert_rows_json(table, [payload])
            if errors:
                print(f"❌ BigQuery insert failed with errors: {errors}")
            else:
                print(f"✅ BigQuery insert successful for orderDetails {order_detail_id}")
        except Exception as ie:
            print(f"❌ Exception while inserting orderDetails to BigQuery: {ie}")

    except Exception as e:
        print(f"❌ Unexpected error syncing orderDetails to BigQuery: {e}")


# OrderDetails update handler: DELETE + INSERT complete payload (updates ALL fields from Firestore)
@firestore_fn.on_document_updated(document="orderDetails/{orderDetailsId}", region="asia-east1")
def sync_order_details_update(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🔁 Firestore trigger activated for updated orderDetails - BigQuery sync")
    try:
        order_detail_id = event.params.get("orderDetailsId")
        after = event.data.after.to_dict()

        print(f"📄 Order Detail ID (updated): {order_detail_id}")
        print(f"📦 New order detail data (ALL FIELDS): {after}")
        print(f"📋 Updating ALL fields for orderDetailsId: {order_detail_id}")

        if not after:
            print("⚠️ Warning: Updated orderDetails document empty — skipping")
            return
            
        if not order_detail_id:
            print("⚠️ Warning: OrderDetails ID is missing — skipping")
            return

        client = get_bigquery_client()
        
        table_name = get_bigquery_table_name('orderDetails')
        # Verify the orderDetails exists before updating
        check_query = f"SELECT COUNT(*) as count FROM `{table_name}` WHERE orderDetailsId = @orderDetailsId"
        check_params = [bigquery.ScalarQueryParameter("orderDetailsId", "STRING", order_detail_id)]
        check_job_config = bigquery.QueryJobConfig(query_parameters=check_params)
        check_job = client.query(check_query, job_config=check_job_config)
        result = list(check_job.result())
        
        if result[0].count == 0:
            print(f"⚠️ OrderDetails {order_detail_id} does not exist in BigQuery - will create new record")
        else:
            print(f"✅ OrderDetails {order_detail_id} exists in BigQuery - proceeding with complete replacement")

        # Delete existing row if present
        try:
            delete_query = f"DELETE FROM `{table_name}` WHERE orderDetailsId = @orderDetailsId"
            params = [bigquery.ScalarQueryParameter("orderDetailsId", "STRING", order_detail_id)]
            job_config = bigquery.QueryJobConfig(query_parameters=params)
            delete_job = client.query(delete_query, job_config=job_config)
            delete_job.result()
            print(f"🗑️ Removed existing orderDetails {order_detail_id} (if any)")
        except Exception as de:
            print(f"⚠️ Warning deleting existing orderDetails row: {de}")

        # Recreate payload using centralized helper to standardize column names
        from bq_helpers import build_orderdetails_payload
        payload = build_orderdetails_payload(order_detail_id, after)

        # Insert new payload with richer logging (streaming insert)
        try:
            table = client.get_table(table_name)
            print(f"📤 Inserting (update) payload into {table_name}: {json.dumps(payload)}")
            errors = client.insert_rows_json(table, [payload])
            if errors:
                print(f"❌ Failed to insert updated orderDetails: {errors}")
                print(f"❗ Failed payload: {json.dumps(payload)}")
            else:
                print(f"✅ Re-inserted updated orderDetails {order_detail_id}")
        except Exception as ie:
            print(f"❌ Exception while inserting updated orderDetails to BigQuery: {ie}")
            try:
                print(f"❗ Payload at exception time: {json.dumps(payload)}")
            except Exception:
                pass

    except Exception as e:
        print(f"❌ Unexpected error syncing updated orderDetails to BigQuery: {e}")


# OrderDetails delete handler
@firestore_fn.on_document_deleted(document="orderDetails/{orderDetailsId}", region="asia-east1")
def sync_order_details_delete(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🗑️ Firestore trigger activated for deleted orderDetails - BigQuery sync")
    try:
        order_detail_id = event.params.get("orderDetailsId")
        client = get_bigquery_client()
        table_name = get_bigquery_table_name('orderDetails')
        delete_query = f"DELETE FROM `{table_name}` WHERE orderDetailsId = @orderDetailsId"
        params = [bigquery.ScalarQueryParameter("orderDetailsId", "STRING", order_detail_id)]
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        job = client.query(delete_query, job_config=job_config)
        job.result()
        print(f"✅ Deleted orderDetails {order_detail_id} from BigQuery (if existed)")
    except Exception as e:
        print(f"❌ Unexpected error deleting orderDetails from BigQuery: {e}")



# BigQuery trigger for new products documents
@firestore_fn.on_document_created(document="products/{productId}", region="asia-east1")
def sync_products_to_bigquery(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    """Sync newly created Firestore product documents into BigQuery products table."""
    print("🔥 Firestore trigger activated for new product - BigQuery sync")

    product_id = event.params["productId"]
    data = event.data.to_dict()

    print(f"📄 Document ID: {product_id}")
    print(f"📦 Document data: {data}")
    print(f"📋 Available fields: {list(data.keys()) if data else 'No fields'}")

    if not data:
        print("⚠️ Warning: Document data is empty!")
        return

    try:
        client = get_bigquery_client()
        
        table_name = get_bigquery_table_name('products')
        # Check if productId already exists in BigQuery
        check_query = f"SELECT COUNT(*) as count FROM `{table_name}` WHERE productId = @productId"
        check_params = [bigquery.ScalarQueryParameter("productId", "STRING", product_id)]
        check_job_config = bigquery.QueryJobConfig(query_parameters=check_params)
        check_job = client.query(check_query, job_config=check_job_config)
        result = list(check_job.result())
        
        if result[0].count > 0:
            print(f"⏭️ Product {product_id} already exists in BigQuery - skipping duplicate insert")
            return
        
        # Prepare payload for BigQuery (matching your schema)
        payload = {
            "barcodeId": data.get("barcodeId"),
            "category": data.get("category"),
            "companyId": data.get("companyId"),
            "costPrice": float(data.get("costPrice", 0)) if data.get("costPrice") is not None else None,
            "createdAt": ts_to_iso(data.get("createdAt")),
            "createdBy": data.get("createdBy"),
            "description": data.get("description"),
            "discountType": data.get("discountType"),
            "discountValue": float(data.get("discountValue", 0)) if data.get("discountValue") is not None else None,
            "hasDiscount": bool(data.get("hasDiscount", False)),
            "imageUrl": data.get("imageUrl"),
            "isFavorite": bool(data.get("isFavorite", False)),
            "isStockTracked": bool(data.get("isStockTracked", False)),
            "isVatApplicable": bool(data.get("isVatApplicable", False)),
            "lastUpdated": ts_to_iso(data.get("lastUpdated")),
            "originalPrice": float(data.get("originalPrice", 0)) if data.get("originalPrice") is not None else None,
            "productCode": data.get("productCode"),
            "productName": data.get("productName"),
            "sellingPrice": float(data.get("sellingPrice", 0)) if data.get("sellingPrice") is not None else None,
            "skuId": data.get("skuId"),
            "status": data.get("status"),
            "storeId": data.get("storeId"),
            "tagLabels": data.get("tagLabels") if isinstance(data.get("tagLabels"), list) else None,
            "tags": data.get("tags") if isinstance(data.get("tags"), list) else None,
            "totalStock": int(data.get("totalStock", 0)) if data.get("totalStock") is not None else None,
            "uid": data.get("uid"),
            "unitType": data.get("unitType"),
            "vatRate": float(data.get("vatRate", 0)) if data.get("vatRate") is not None else None,
            "updatedAt": ts_to_iso(data.get("updatedAt")),
            "updatedBy": data.get("updatedBy")
        }
        
        # Remove null values and convert Decimal to JSON-friendly types
        def clean_payload(obj):
            if isinstance(obj, dict):
                return {k: clean_payload(v) for k, v in obj.items() if v is not None}
            if isinstance(obj, list):
                return [clean_payload(v) for v in obj]
            if isinstance(obj, Decimal):
                return str(obj)
            return obj
        
        payload = clean_payload(payload)
        
        # Add the Firestore document ID as a field
        payload["productId"] = product_id
        
        print(f"🧹 Cleaned payload for BigQuery: {payload}")

        # Use MERGE to perform an idempotent upsert based on productId
        try:
            merge_query = f"""
            MERGE `{table_name}` T
            USING (SELECT @productId AS productId) S
            ON T.productId = S.productId
            WHEN MATCHED THEN
              UPDATE SET
                barcodeId = @barcodeId,
                category = @category,
                companyId = @companyId,
                                costPrice = @costPrice,
                createdAt = SAFE_CAST(@createdAt AS TIMESTAMP),
                createdBy = @createdBy,
                description = @description,
                discountType = @discountType,
                discountValue = @discountValue,
                hasDiscount = @hasDiscount,
                imageUrl = @imageUrl,
                isFavorite = @isFavorite,
                                isStockTracked = @isStockTracked,
                isVatApplicable = @isVatApplicable,
                                lastUpdated = SAFE_CAST(@lastUpdated AS TIMESTAMP),
                                originalPrice = @originalPrice,
                productCode = @productCode,
                productName = @productName,
                sellingPrice = @sellingPrice,
                skuId = @skuId,
                status = @status,
                storeId = @storeId,
                                tagLabels = @tagLabels,
                                tags = @tags,
                totalStock = @totalStock,
                uid = @uid,
                unitType = @unitType,
                                vatRate = @vatRate,
                updatedAt = SAFE_CAST(@updatedAt AS TIMESTAMP),
                updatedBy = @updatedBy
            WHEN NOT MATCHED THEN
                            INSERT (productId, barcodeId, category, companyId, costPrice, createdAt, createdBy, description, discountType, discountValue, hasDiscount, imageUrl, isFavorite, isStockTracked, isVatApplicable, lastUpdated, originalPrice, productCode, productName, sellingPrice, skuId, status, storeId, tagLabels, tags, totalStock, uid, unitType, vatRate, updatedAt, updatedBy)
                            VALUES(@productId, @barcodeId, @category, @companyId, @costPrice, SAFE_CAST(@createdAt AS TIMESTAMP), @createdBy, @description, @discountType, @discountValue, @hasDiscount, @imageUrl, @isFavorite, @isStockTracked, @isVatApplicable, SAFE_CAST(@lastUpdated AS TIMESTAMP), @originalPrice, @productCode, @productName, @sellingPrice, @skuId, @status, @storeId, @tagLabels, @tags, @totalStock, @uid, @unitType, @vatRate, SAFE_CAST(@updatedAt AS TIMESTAMP), @updatedBy)
            """

            params = [
                bigquery.ScalarQueryParameter("productId", "STRING", product_id),
                bigquery.ScalarQueryParameter("barcodeId", "STRING", data.get("barcodeId")),
                bigquery.ScalarQueryParameter("category", "STRING", data.get("category")),
                bigquery.ScalarQueryParameter("companyId", "STRING", data.get("companyId")),
                bigquery.ScalarQueryParameter("costPrice", "FLOAT64", float(data.get('costPrice', 0)) if data.get('costPrice') is not None else None),
                bigquery.ScalarQueryParameter("createdAt", "TIMESTAMP", ts_to_iso(data.get('createdAt'))),
                bigquery.ScalarQueryParameter("createdBy", "STRING", data.get("createdBy")),
                bigquery.ScalarQueryParameter("description", "STRING", data.get("description")),
                bigquery.ScalarQueryParameter("discountType", "STRING", data.get("discountType")),
                bigquery.ScalarQueryParameter("discountValue", "FLOAT64", float(data.get('discountValue', 0)) if data.get('discountValue') is not None else None),
                bigquery.ScalarQueryParameter("hasDiscount", "BOOL", bool(data.get('hasDiscount', False))),
                bigquery.ScalarQueryParameter("imageUrl", "STRING", data.get('imageUrl')),
                bigquery.ScalarQueryParameter("isFavorite", "BOOL", bool(data.get('isFavorite', False))),
                bigquery.ScalarQueryParameter("isStockTracked", "BOOL", bool(data.get('isStockTracked', False))),
                bigquery.ScalarQueryParameter("isVatApplicable", "BOOL", bool(data.get('isVatApplicable', False))),
                bigquery.ScalarQueryParameter("lastUpdated", "TIMESTAMP", ts_to_iso(data.get('lastUpdated'))),
                bigquery.ScalarQueryParameter("originalPrice", "FLOAT64", float(data.get('originalPrice', 0)) if data.get('originalPrice') is not None else None),
                bigquery.ScalarQueryParameter("productCode", "STRING", data.get('productCode')),
                bigquery.ScalarQueryParameter("productName", "STRING", data.get('productName')),
                bigquery.ScalarQueryParameter("sellingPrice", "FLOAT64", float(data.get('sellingPrice', 0)) if data.get('sellingPrice') is not None else None),
                bigquery.ScalarQueryParameter("skuId", "STRING", data.get('skuId')),
                bigquery.ScalarQueryParameter("status", "STRING", data.get('status')),
                bigquery.ScalarQueryParameter("storeId", "STRING", data.get('storeId')),
                bigquery.ArrayQueryParameter("tagLabels", "STRING", data.get('tagLabels') if isinstance(data.get('tagLabels'), list) else []),
                bigquery.ArrayQueryParameter("tags", "STRING", data.get('tags') if isinstance(data.get('tags'), list) else []),
                bigquery.ScalarQueryParameter("totalStock", "INT64", int(data.get('totalStock', 0)) if data.get('totalStock') is not None else None),
                bigquery.ScalarQueryParameter("uid", "STRING", data.get('uid')),
                bigquery.ScalarQueryParameter("unitType", "STRING", data.get('unitType')),
                bigquery.ScalarQueryParameter("vatRate", "FLOAT64", float(data.get('vatRate', 0)) if data.get('vatRate') is not None else None),
                bigquery.ScalarQueryParameter("updatedAt", "TIMESTAMP", ts_to_iso(data.get('updatedAt'))),
                bigquery.ScalarQueryParameter("updatedBy", "STRING", data.get('updatedBy'))
            ]

            job_config = bigquery.QueryJobConfig(query_parameters=params)
            query_job = client.query(merge_query, job_config=job_config)
            query_job.result()
            print(f"✅ MERGE upsert completed for product {product_id}")
        except Exception as me:
            print(f"❌ MERGE failed for product {product_id}: {me}")

    except Exception as e:
        print(f"❌ Unexpected error syncing to BigQuery: {e}")


# Products update handler: COMPLETE field update using MERGE (updates ALL fields from Firestore)
@firestore_fn.on_document_updated(document="products/{productId}", region="asia-east1")
def sync_products_to_bigquery_update(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🔁 Firestore trigger activated for updated product - BigQuery sync")
    try:
        product_id = event.params.get("productId")
        after = event.data.after.to_dict()

        print(f"📄 Product ID (updated): {product_id}")
        print(f"📦 New product data (ALL FIELDS): {after}")
        print(f"📋 Updating ALL fields for productId: {product_id}")

        if not after:
            print("⚠️ Warning: Updated product document empty — skipping")
            return
        
        if not product_id:
            print("⚠️ Warning: Product ID is missing — skipping")
            return

        client = get_bigquery_client()
        
        # Verify the product exists in BigQuery before updating
        check_query = f"SELECT COUNT(*) as count FROM `{BIGQUERY_PRODUCTS_TABLE}` WHERE productId = @productId"
        check_params = [bigquery.ScalarQueryParameter("productId", "STRING", product_id)]
        check_job_config = bigquery.QueryJobConfig(query_parameters=check_params)
        check_job = client.query(check_query, job_config=check_job_config)
        result = list(check_job.result())
        
        if result[0].count == 0:
            print(f"⚠️ Product {product_id} does not exist in BigQuery - creating new record instead of update")
        else:
            print(f"✅ Product {product_id} exists in BigQuery - proceeding with complete field update")

        # Use MERGE to upsert the updated product (idempotent)
        try:
            merge_query = f"""
            MERGE `{BIGQUERY_PRODUCTS_TABLE}` T
            USING (SELECT @productId AS productId) S
            ON T.productId = S.productId
            WHEN MATCHED THEN
              UPDATE SET
                barcodeId = @barcodeId,
                category = @category,
                companyId = @companyId,
                                costPrice = @costPrice,
                createdAt = SAFE_CAST(@createdAt AS TIMESTAMP),
                createdBy = @createdBy,
                description = @description,
                discountType = @discountType,
                discountValue = @discountValue,
                hasDiscount = @hasDiscount,
                imageUrl = @imageUrl,
                isFavorite = @isFavorite,
                                isStockTracked = @isStockTracked,
                isVatApplicable = @isVatApplicable,
                                lastUpdated = SAFE_CAST(@lastUpdated AS TIMESTAMP),
                                originalPrice = @originalPrice,
                productCode = @productCode,
                productName = @productName,
                sellingPrice = @sellingPrice,
                skuId = @skuId,
                status = @status,
                storeId = @storeId,
                                tagLabels = @tagLabels,
                                tags = @tags,
                totalStock = @totalStock,
                uid = @uid,
                unitType = @unitType,
                                vatRate = @vatRate,
                updatedAt = SAFE_CAST(@updatedAt AS TIMESTAMP),
                updatedBy = @updatedBy
            WHEN NOT MATCHED THEN
                            INSERT (productId, barcodeId, category, companyId, costPrice, createdAt, createdBy, description, discountType, discountValue, hasDiscount, imageUrl, isFavorite, isStockTracked, isVatApplicable, lastUpdated, originalPrice, productCode, productName, sellingPrice, skuId, status, storeId, tagLabels, tags, totalStock, uid, unitType, vatRate, updatedAt, updatedBy)
                            VALUES(@productId, @barcodeId, @category, @companyId, @costPrice, SAFE_CAST(@createdAt AS TIMESTAMP), @createdBy, @description, @discountType, @discountValue, @hasDiscount, @imageUrl, @isFavorite, @isStockTracked, @isVatApplicable, SAFE_CAST(@lastUpdated AS TIMESTAMP), @originalPrice, @productCode, @productName, @sellingPrice, @skuId, @status, @storeId, @tagLabels, @tags, @totalStock, @uid, @unitType, @vatRate, SAFE_CAST(@updatedAt AS TIMESTAMP), @updatedBy)
            """

            params = [
                bigquery.ScalarQueryParameter("productId", "STRING", product_id),
                bigquery.ScalarQueryParameter("barcodeId", "STRING", after.get("barcodeId")),
                bigquery.ScalarQueryParameter("category", "STRING", after.get("category")),
                bigquery.ScalarQueryParameter("companyId", "STRING", after.get("companyId")),
                bigquery.ScalarQueryParameter("costPrice", "FLOAT64", float(after.get('costPrice', 0)) if after.get('costPrice') is not None else None),
                bigquery.ScalarQueryParameter("createdAt", "TIMESTAMP", ts_to_iso(after.get('createdAt'))),
                bigquery.ScalarQueryParameter("createdBy", "STRING", after.get("createdBy")),
                bigquery.ScalarQueryParameter("description", "STRING", after.get("description")),
                bigquery.ScalarQueryParameter("discountType", "STRING", after.get("discountType")),
                bigquery.ScalarQueryParameter("discountValue", "FLOAT64", float(after.get('discountValue', 0)) if after.get('discountValue') is not None else None),
                bigquery.ScalarQueryParameter("hasDiscount", "BOOL", bool(after.get('hasDiscount', False))),
                bigquery.ScalarQueryParameter("imageUrl", "STRING", after.get('imageUrl')),
                bigquery.ScalarQueryParameter("isFavorite", "BOOL", bool(after.get('isFavorite', False))),
                bigquery.ScalarQueryParameter("isStockTracked", "BOOL", bool(after.get('isStockTracked', False))),
                bigquery.ScalarQueryParameter("isVatApplicable", "BOOL", bool(after.get('isVatApplicable', False))),
                bigquery.ScalarQueryParameter("lastUpdated", "TIMESTAMP", ts_to_iso(after.get('lastUpdated'))),
                bigquery.ScalarQueryParameter("originalPrice", "FLOAT64", float(after.get('originalPrice', 0)) if after.get('originalPrice') is not None else None),
                bigquery.ScalarQueryParameter("productCode", "STRING", after.get('productCode')),
                bigquery.ScalarQueryParameter("productName", "STRING", after.get('productName')),
                bigquery.ScalarQueryParameter("sellingPrice", "FLOAT64", float(after.get('sellingPrice', 0)) if after.get('sellingPrice') is not None else None),
                bigquery.ScalarQueryParameter("skuId", "STRING", after.get('skuId')),
                bigquery.ScalarQueryParameter("status", "STRING", after.get('status')),
                bigquery.ScalarQueryParameter("storeId", "STRING", after.get('storeId')),
                bigquery.ArrayQueryParameter("tagLabels", "STRING", after.get('tagLabels') if isinstance(after.get('tagLabels'), list) else []),
                bigquery.ArrayQueryParameter("tags", "STRING", after.get('tags') if isinstance(after.get('tags'), list) else []),
                bigquery.ScalarQueryParameter("totalStock", "INT64", int(after.get('totalStock', 0)) if after.get('totalStock') is not None else None),
                bigquery.ScalarQueryParameter("uid", "STRING", after.get('uid')),
                bigquery.ScalarQueryParameter("unitType", "STRING", after.get('unitType')),
                bigquery.ScalarQueryParameter("vatRate", "FLOAT64", float(after.get('vatRate', 0)) if after.get('vatRate') is not None else None),
                bigquery.ScalarQueryParameter("updatedAt", "TIMESTAMP", ts_to_iso(after.get('updatedAt'))),
                bigquery.ScalarQueryParameter("updatedBy", "STRING", after.get('updatedBy'))
            ]

            job_config = bigquery.QueryJobConfig(query_parameters=params)
            query_job = client.query(merge_query, job_config=job_config)
            query_job.result()
            print(f"✅ MERGE upsert completed for updated product {product_id}")
        except Exception as me:
            print(f"❌ MERGE (update) failed for product {product_id}: {me}")

    except Exception as e:
        print(f"❌ Unexpected error syncing updated product to BigQuery: {e}")


# Products delete handler
@firestore_fn.on_document_deleted(document="products/{productId}", region="asia-east1")
def sync_products_to_bigquery_delete(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🗑️ Firestore trigger activated for deleted product - BigQuery sync")
    try:
        product_id = event.params.get("productId")
        client = get_bigquery_client()
        delete_query = f"DELETE FROM `{BIGQUERY_PRODUCTS_TABLE}` WHERE productId = @productId"
        params = [bigquery.ScalarQueryParameter("productId", "STRING", product_id)]
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        job = client.query(delete_query, job_config=job_config)
        job.result()
        print(f"✅ Deleted product {product_id} from BigQuery (if existed)")
    except Exception as e:
        print(f"❌ Unexpected error deleting product from BigQuery: {e}")


# OrderSellingTracking: create handler
@firestore_fn.on_document_created(document="ordersSellingTracking/{orderSellingTrackingId}", region="asia-east1")
def sync_order_selling_tracking_to_bigquery(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🔥 Firestore trigger activated for new orderSellingTracking - BigQuery sync")

    ost_id = event.params["orderSellingTrackingId"]
    data = event.data.to_dict()
    table_name = get_bigquery_table_name('ordersSellingTracking')

    print(f"📄 orderSellingTracking Document ID: {ost_id}")
    print(f"📦 Document data: {data}")
    print(f"📋 Available fields: {list(data.keys()) if data else 'No fields'}")

    if not data:
        print("⚠️ Warning: orderSellingTracking document data is empty!")
        return

    try:
        client = get_bigquery_client()
        
        # Check if ordersSellingTracking already exists in BigQuery to avoid duplicate inserts
        check_query = f"SELECT COUNT(*) as count FROM `{table_name}` WHERE ordersSellingTrackingId = @ostId"
        check_params = [bigquery.ScalarQueryParameter("ostId", "STRING", ost_id)]
        check_job_config = bigquery.QueryJobConfig(query_parameters=check_params)
        check_job = client.query(check_query, job_config=check_job_config)
        result = list(check_job.result())
        
        if result[0].count > 0:
            print(f"⏭️ orderSellingTracking {ost_id} already exists in BigQuery - skipping duplicate insert")
            return

        # Build payload with updated field schema to match new Firestore structure
        # Match BigQuery types: INT64 for batchNumber/quantity/itemIndex; NUMERIC for price/discount/vat/total
        def to_int(v):
            try:
                return int(v) if v is not None else None
            except Exception:
                return None

        def to_numeric(v):
            try:
                if v is None:
                    return None
                # Accept Decimal, int, float, or numeric string
                if isinstance(v, Decimal):
                    return v
                return Decimal(str(v))
            except (InvalidOperation, ValueError, TypeError):
                return None

        payload = {
            "ordersSellingTrackingId": ost_id,
            "batchNumber": to_int(data.get("batchNumber")),
            "cashierEmail": data.get("cashierEmail"),
            "cashierId": data.get("cashierId"),
            "cashierName": data.get("cashierName"),
            "category": data.get("category"),
            "companyId": data.get("companyId"),
            "cost": to_numeric(data.get("cost")),
            "createdAt": ts_to_iso(data.get("createdAt")),
            "createdBy": data.get("createdBy"),
            "discount": to_numeric(data.get("discount")),
            "discountType": data.get("discountType"),
            "invoiceNumber": data.get("invoiceNumber"),
            "isStockTracked": bool(data.get("isStockTracked", False)),
            "isVatExempt": bool(data.get("isVatExempt", False)),
            "itemIndex": to_int(data.get("itemIndex")),
            "orderId": data.get("orderId"),
            "orderDetailsId": data.get("orderDetailsId"),
            "price": to_numeric(data.get("price")),
            "productCode": data.get("productCode"),
            "productId": data.get("productId"),
            "productName": data.get("productName"),
            "quantity": to_int(data.get("quantity")),
            "runningBalanceTotalStock": to_int(data.get("runningBalanceTotalStock")),
            "skuId": data.get("skuId"),
            "status": data.get("status"),
            "storeId": data.get("storeId"),
            "tagLabels": data.get("tagLabels") if isinstance(data.get("tagLabels"), list) else [],
            "tags": data.get("tags") if isinstance(data.get("tags"), list) else [],
            "total": to_numeric(data.get("total")),
            "uid": data.get("uid"),
            "updatedAt": ts_to_iso(data.get("updatedAt")),
            "updatedBy": data.get("updatedBy"),
            "vat": to_numeric(data.get("vat")),
        }

        print(f"🔍 All Firestore data keys: {list(data.keys())}")

        # Clean None values and convert Decimal to JSON-friendly types
        def clean_payload(obj):
            if isinstance(obj, dict):
                return {k: clean_payload(v) for k, v in obj.items() if v is not None}
            if isinstance(obj, list):
                return [clean_payload(v) for v in obj]
            if isinstance(obj, Decimal):
                return str(obj)
            return obj

        payload = clean_payload(payload)

        print(f"🧹 Final payload for BigQuery (orderSellingTracking): {payload}")

        # Use streaming insert for orderSellingTracking (keeps nested items intact)
        try:
            table = client.get_table(table_name)
            print(f"📤 Inserting payload into {table_name}")
            errors = client.insert_rows_json(table, [payload])
            if errors:
                print(f"❌ BigQuery insert failed with errors: {errors}")
            else:
                print(f"✅ BigQuery insert successful for orderSellingTracking {ost_id}")
        except Exception as ie:
            print(f"❌ Exception while inserting orderSellingTracking to BigQuery: {ie}")

    except Exception as e:
        print(f"❌ Unexpected error syncing orderSellingTracking to BigQuery: {e}")


# OrderSellingTracking update handler: Re-added for new schema
@firestore_fn.on_document_updated(document="ordersSellingTracking/{orderSellingTrackingId}", region="asia-east1")
def sync_order_selling_tracking_update(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🔁 Firestore trigger activated for updated orderSellingTracking - BigQuery sync")
    try:
        ost_id = event.params.get("orderSellingTrackingId")
        after = event.data.after.to_dict()
        table_name = get_bigquery_table_name('ordersSellingTracking')

        print(f"📄 orderSellingTracking ID (updated): {ost_id}")
        print(f"📦 New data: {after}")

        if not after:
            print("⚠️ Warning: updated document empty — skipping")
            return

        client = get_bigquery_client()

        # Use MERGE for proper upsert instead of DELETE+INSERT to avoid data loss
        # This ensures atomicity and handles both insert and update cases safely

        # Recreate payload from the updated document with new schema
        def to_int(v):
            try:
                return int(v) if v is not None else None
            except Exception:
                return None

        def to_numeric(v):
            try:
                if v is None:
                    return None
                if isinstance(v, Decimal):
                    return v
                return Decimal(str(v))
            except (InvalidOperation, ValueError, TypeError):
                return None
                
        # Debug status field specifically
        print(f"🔍 UPDATE Status field debugging - Raw Firestore value: '{after.get('status')}' (type: {type(after.get('status'))})")
        print(f"🔍 UPDATE All Firestore data keys: {list(after.keys())}")

        upd_payload = {
            "ordersSellingTrackingId": ost_id,
            "batchNumber": to_int(after.get("batchNumber")),
            "cashierEmail": after.get("cashierEmail"),
            "cashierId": after.get("cashierId"),
            "cashierName": after.get("cashierName"),
            "category": after.get("category"),
            "companyId": after.get("companyId"),
            "cost": to_numeric(after.get("cost")),
            "createdAt": ts_to_iso(after.get("createdAt")),
            "createdBy": after.get("createdBy"),
            "discount": to_numeric(after.get("discount")),
            "discountType": after.get("discountType"),
            "invoiceNumber": after.get("invoiceNumber"),
            "isStockTracked": bool(after.get("isStockTracked", False)),
            "isVatExempt": bool(after.get("isVatExempt", False)),
            "itemIndex": to_int(after.get("itemIndex")),
            "orderId": after.get("orderId"),
            "orderDetailsId": after.get("orderDetailsId"),
            "price": to_numeric(after.get("price")),
            "productCode": after.get("productCode"),
            "productId": after.get("productId"),
            "productName": after.get("productName"),
            "quantity": to_int(after.get("quantity")),
            "runningBalanceTotalStock": to_int(after.get("runningBalanceTotalStock")),
            "skuId": after.get("skuId"),
            "status": after.get("status"),
            "storeId": after.get("storeId"),
            "tagLabels": after.get("tagLabels") if isinstance(after.get("tagLabels"), list) else [],
            "tags": after.get("tags") if isinstance(after.get("tags"), list) else [],
            "total": to_numeric(after.get("total")),
            "uid": after.get("uid"),
            "updatedAt": ts_to_iso(after.get("updatedAt")),
            "updatedBy": after.get("updatedBy"),
            "vat": to_numeric(after.get("vat")),
        }

        def clean_payload(obj):
            if isinstance(obj, dict):
                return {k: clean_payload(v) for k, v in obj.items() if v is not None}
            if isinstance(obj, list):
                return [clean_payload(v) for v in obj]
            if isinstance(obj, Decimal):
                return str(obj)
            return obj

        upd_payload = clean_payload(upd_payload)

        # Delete existing row then re-insert (same proven pattern as orders/orderDetails)
        try:
            del_query = f"DELETE FROM `{table_name}` WHERE ordersSellingTrackingId = @ostId"
            del_params = [bigquery.ScalarQueryParameter("ostId", "STRING", ost_id)]
            del_job = client.query(del_query, job_config=bigquery.QueryJobConfig(query_parameters=del_params))
            del_job.result()
            print(f"🗑️ Removed existing OST row {ost_id} (if any)")
        except Exception as de:
            print(f"⚠️ Warning deleting existing OST row: {de}")

        try:
            table = client.get_table(table_name)
            print(f"📤 Inserting updated OST payload into {table_name}")
            errors = client.insert_rows_json(table, [upd_payload])
            if errors:
                print(f"❌ BigQuery update insert failed: {errors}")
            else:
                print(f"✅ BigQuery update successful for orderSellingTracking {ost_id}")
        except Exception as ie:
            print(f"❌ Exception inserting updated OST to BigQuery: {ie}")

    except Exception as e:
        print(f"❌ Unexpected error syncing updated orderSellingTracking to BigQuery: {e}")


# OrderSellingTracking delete handler
@firestore_fn.on_document_deleted(document="ordersSellingTracking/{orderSellingTrackingId}", region="asia-east1")
def sync_order_selling_tracking_delete(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🗑️ Firestore trigger activated for deleted orderSellingTracking - BigQuery sync")
    try:
        ost_id = event.params.get("orderSellingTrackingId")
        client = get_bigquery_client()
        table_name = get_bigquery_table_name('ordersSellingTracking')
        delete_query = f"DELETE FROM `{table_name}` WHERE ordersSellingTrackingId = @orderSellingTrackingId"
        params = [bigquery.ScalarQueryParameter("orderSellingTrackingId", "STRING", ost_id)]
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        job = client.query(delete_query, job_config=job_config)
        job.result()
        print(f"✅ Deleted orderSellingTracking {ost_id} from BigQuery (if existed)")
    except Exception as e:
        print(f"❌ Unexpected error deleting orderSellingTracking from BigQuery: {e}")