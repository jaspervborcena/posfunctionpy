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

# Import configuration 
from config import get_bigquery_client, BIGQUERY_ORDERS_TABLE, BIGQUERY_ORDER_DETAILS_TABLE, BIGQUERY_PRODUCTS_TABLE, BIGQUERY_ORDER_SELLING_TRACKING_TABLE
from bq_helpers import build_product_payload

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
        
        # Check if orderId already exists in BigQuery
        check_query = f"SELECT COUNT(*) as count FROM `{BIGQUERY_ORDERS_TABLE}` WHERE orderId = @orderId"
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

        # Use MERGE to perform an idempotent upsert based on orderId
        try:
            merge_query = f"""
            MERGE `{BIGQUERY_ORDERS_TABLE}` T
            USING (SELECT @orderId AS orderId) S
            ON T.orderId = S.orderId
            WHEN MATCHED THEN
              UPDATE SET
                assignedCashierEmail = @assignedCashierEmail,
                assignedCashierId = @assignedCashierId,
                assignedCashierName = @assignedCashierName,
                atpOrOcn = @atpOrOcn,
                birPermitNo = @birPermitNo,
                cashSale = @cashSale,
                companyAddress = @companyAddress,
                companyEmail = @companyEmail,
                companyId = @companyId,
                companyName = @companyName,
                companyPhone = @companyPhone,
                companyTaxId = @companyTaxId,
                createdAt = SAFE_CAST(@createdAt AS TIMESTAMP),
                createdBy = @createdBy,
                customerInfo = STRUCT(@customer_address AS address, @customer_customerId AS customerId, @customer_fullName AS fullName, @customer_tin AS tin),
                date = SAFE_CAST(@date AS TIMESTAMP),
                discountAmount = @discountAmount,
                grossAmount = @grossAmount,
                inclusiveSerialNumber = @inclusiveSerialNumber,
                invoiceNumber = @invoiceNumber,
                message = @message,
                netAmount = @netAmount,
                payments = STRUCT(@payments_amountTendered AS amountTendered, @payments_changeAmount AS changeAmount, @payments_paymentDescription AS paymentDescription),
                status = @status,
                storeId = @storeId,
                totalAmount = @totalAmount,
                uid = @uid,
                updatedAt = SAFE_CAST(@updatedAt AS TIMESTAMP),
                updatedBy = @updatedBy,
                vatAmount = @vatAmount,
                vatExemptAmount = @vatExemptAmount,
                vatableSales = @vatableSales,
                zeroRatedSales = @zeroRatedSales
            WHEN NOT MATCHED THEN
              INSERT (orderId, assignedCashierEmail, assignedCashierId, assignedCashierName, atpOrOcn, birPermitNo, cashSale, companyAddress, companyEmail, companyId, companyName, companyPhone, companyTaxId, createdAt, createdBy, customerInfo, date, discountAmount, grossAmount, inclusiveSerialNumber, invoiceNumber, message, netAmount, payments, status, storeId, totalAmount, uid, updatedAt, updatedBy, vatAmount, vatExemptAmount, vatableSales, zeroRatedSales)
                            VALUES(@orderId, @assignedCashierEmail, @assignedCashierId, @assignedCashierName, @atpOrOcn, @birPermitNo, @cashSale, @companyAddress, @companyEmail, @companyId, @companyName, @companyPhone, @companyTaxId, SAFE_CAST(@createdAt AS TIMESTAMP), @createdBy, STRUCT(@customer_address AS address, @customer_customerId AS customerId, @customer_fullName AS fullName, @customer_tin AS tin), SAFE_CAST(@date AS TIMESTAMP), @discountAmount, @grossAmount, @inclusiveSerialNumber, @invoiceNumber, @message, @netAmount, STRUCT(@payments_amountTendered AS amountTendered, @payments_changeAmount AS changeAmount, @payments_paymentDescription AS paymentDescription), @status, @storeId, @totalAmount, @uid, SAFE_CAST(@updatedAt AS TIMESTAMP), @updatedBy, @vatAmount, @vatExemptAmount, @vatableSales, @zeroRatedSales)
            """

            params = [
                bigquery.ScalarQueryParameter("orderId", "STRING", order_id),
                bigquery.ScalarQueryParameter("assignedCashierEmail", "STRING", data.get("assignedCashierEmail")),
                bigquery.ScalarQueryParameter("assignedCashierId", "STRING", data.get("assignedCashierId")),
                bigquery.ScalarQueryParameter("assignedCashierName", "STRING", data.get("assignedCashierName")),
                bigquery.ScalarQueryParameter("atpOrOcn", "STRING", data.get("atpOrOcn")),
                bigquery.ScalarQueryParameter("birPermitNo", "STRING", data.get("birPermitNo")),
                bigquery.ScalarQueryParameter("cashSale", "BOOL", bool(data.get("cashSale", False))),
                bigquery.ScalarQueryParameter("companyAddress", "STRING", data.get("companyAddress")),
                bigquery.ScalarQueryParameter("companyEmail", "STRING", data.get("companyEmail")),
                bigquery.ScalarQueryParameter("companyId", "STRING", data.get("companyId")),
                bigquery.ScalarQueryParameter("companyName", "STRING", data.get("companyName")),
                bigquery.ScalarQueryParameter("companyPhone", "STRING", data.get("companyPhone")),
                bigquery.ScalarQueryParameter("companyTaxId", "STRING", data.get("companyTaxId")),
                bigquery.ScalarQueryParameter("createdAt", "TIMESTAMP", ts_to_iso(data.get('createdAt'))),
                bigquery.ScalarQueryParameter("createdBy", "STRING", data.get("createdBy")),
                bigquery.ScalarQueryParameter("customer_address", "STRING", data.get("customerInfo", {}).get("address") if data.get("customerInfo") else None),
                bigquery.ScalarQueryParameter("customer_customerId", "STRING", data.get("customerInfo", {}).get("customerId") if data.get("customerInfo") else None),
                bigquery.ScalarQueryParameter("customer_fullName", "STRING", data.get("customerInfo", {}).get("fullName") if data.get("customerInfo") else None),
                bigquery.ScalarQueryParameter("customer_tin", "STRING", data.get("customerInfo", {}).get("tin") if data.get("customerInfo") else None),
                bigquery.ScalarQueryParameter("date", "TIMESTAMP", ts_to_iso(data.get('date'))),
                bigquery.ScalarQueryParameter("discountAmount", "FLOAT64", float(data.get('discountAmount', 0)) if data.get('discountAmount') is not None else None),
                bigquery.ScalarQueryParameter("grossAmount", "FLOAT64", float(data.get('grossAmount', 0)) if data.get('grossAmount') is not None else None),
                bigquery.ScalarQueryParameter("inclusiveSerialNumber", "STRING", data.get('inclusiveSerialNumber')),
                bigquery.ScalarQueryParameter("invoiceNumber", "STRING", data.get('invoiceNumber', order_id)),
                bigquery.ScalarQueryParameter("message", "STRING", data.get('message')),
                bigquery.ScalarQueryParameter("netAmount", "FLOAT64", float(data.get('netAmount', 0)) if data.get('netAmount') is not None else None),
                # Pass payments fields as scalars to build a STRUCT in SQL (avoid assigning STRING -> STRUCT)
                bigquery.ScalarQueryParameter("payments_amountTendered", "FLOAT64", float(data.get('payments', {}).get('amountTendered')) if data.get('payments') and data.get('payments').get('amountTendered') is not None else None),
                bigquery.ScalarQueryParameter("payments_changeAmount", "FLOAT64", float(data.get('payments', {}).get('changeAmount')) if data.get('payments') and data.get('payments').get('changeAmount') is not None else None),
                bigquery.ScalarQueryParameter("payments_paymentDescription", "STRING", data.get('payments', {}).get('paymentDescription') if data.get('payments') else None),
                bigquery.ScalarQueryParameter("status", "STRING", data.get('status')),
                bigquery.ScalarQueryParameter("storeId", "STRING", data.get('storeId')),
                bigquery.ScalarQueryParameter("totalAmount", "FLOAT64", float(data.get('totalAmount', 0)) if data.get('totalAmount') is not None else None),
                bigquery.ScalarQueryParameter("uid", "STRING", data.get('uid')),
                bigquery.ScalarQueryParameter("updatedAt", "TIMESTAMP", ts_to_iso(data.get('updatedAt'))),
                bigquery.ScalarQueryParameter("updatedBy", "STRING", data.get('updatedBy')),
                bigquery.ScalarQueryParameter("vatAmount", "FLOAT64", float(data.get('vatAmount', 0)) if data.get('vatAmount') is not None else None),
                bigquery.ScalarQueryParameter("vatExemptAmount", "FLOAT64", float(data.get('vatExemptAmount', 0)) if data.get('vatExemptAmount') is not None else None),
                bigquery.ScalarQueryParameter("vatableSales", "FLOAT64", float(data.get('vatableSales', 0)) if data.get('vatableSales') is not None else None),
                bigquery.ScalarQueryParameter("zeroRatedSales", "FLOAT64", float(data.get('zeroRatedSales', 0)) if data.get('zeroRatedSales') is not None else None)
            ]

            job_config = bigquery.QueryJobConfig(query_parameters=params)
            query_job = client.query(merge_query, job_config=job_config)
            query_job.result()
            print(f"✅ MERGE upsert completed for order {order_id}")
        except Exception as me:
            print(f"❌ MERGE failed for order {order_id}: {me}")

    except Exception as e:
        print(f"❌ Unexpected error syncing to BigQuery: {e}")


# Orders update handler: COMPLETE field update using MERGE (updates ALL fields from Firestore)
@firestore_fn.on_document_updated(document="orders/{orderId}", region="asia-east1")
def sync_order_to_bigquery_update(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🔁 Firestore trigger activated for updated order - BigQuery sync")
    try:
        order_id = event.params.get("orderId")
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
        check_query = f"SELECT COUNT(*) as count FROM `{BIGQUERY_ORDERS_TABLE}` WHERE orderId = @orderId"
        check_params = [bigquery.ScalarQueryParameter("orderId", "STRING", order_id)]
        check_job_config = bigquery.QueryJobConfig(query_parameters=check_params)
        check_job = client.query(check_query, job_config=check_job_config)
        result = list(check_job.result())
        
        if result[0].count == 0:
            print(f"⚠️ Order {order_id} does not exist in BigQuery - creating new record instead of update")
        else:
            print(f"✅ Order {order_id} exists in BigQuery - proceeding with complete field update")

        # Use MERGE to upsert the updated order (idempotent)
        try:
            merge_query = f"""
            MERGE `{BIGQUERY_ORDERS_TABLE}` T
            USING (SELECT @orderId AS orderId) S
            ON T.orderId = S.orderId
            WHEN MATCHED THEN
              UPDATE SET
                assignedCashierEmail = @assignedCashierEmail,
                assignedCashierId = @assignedCashierId,
                assignedCashierName = @assignedCashierName,
                atpOrOcn = @atpOrOcn,
                birPermitNo = @birPermitNo,
                cashSale = @cashSale,
                companyAddress = @companyAddress,
                companyEmail = @companyEmail,
                companyId = @companyId,
                companyName = @companyName,
                companyPhone = @companyPhone,
                companyTaxId = @companyTaxId,
                createdAt = SAFE_CAST(@createdAt AS TIMESTAMP),
                createdBy = @createdBy,
                customerInfo = STRUCT(@customer_address AS address, @customer_customerId AS customerId, @customer_fullName AS fullName, @customer_tin AS tin),
                date = SAFE_CAST(@date AS TIMESTAMP),
                discountAmount = @discountAmount,
                grossAmount = @grossAmount,
                inclusiveSerialNumber = @inclusiveSerialNumber,
                invoiceNumber = @invoiceNumber,
                message = @message,
                netAmount = @netAmount,
                payments = STRUCT(@payments_amountTendered AS amountTendered, @payments_changeAmount AS changeAmount, @payments_paymentDescription AS paymentDescription),
                status = @status,
                storeId = @storeId,
                totalAmount = @totalAmount,
                uid = @uid,
                updatedAt = SAFE_CAST(@updatedAt AS TIMESTAMP),
                updatedBy = @updatedBy,
                vatAmount = @vatAmount,
                vatExemptAmount = @vatExemptAmount,
                vatableSales = @vatableSales,
                zeroRatedSales = @zeroRatedSales
            WHEN NOT MATCHED THEN
              INSERT (orderId, assignedCashierEmail, assignedCashierId, assignedCashierName, atpOrOcn, birPermitNo, cashSale, companyAddress, companyEmail, companyId, companyName, companyPhone, companyTaxId, createdAt, createdBy, customerInfo, date, discountAmount, grossAmount, inclusiveSerialNumber, invoiceNumber, message, netAmount, payments, status, storeId, totalAmount, uid, updatedAt, updatedBy, vatAmount, vatExemptAmount, vatableSales, zeroRatedSales)
                            VALUES(@orderId, @assignedCashierEmail, @assignedCashierId, @assignedCashierName, @atpOrOcn, @birPermitNo, @cashSale, @companyAddress, @companyEmail, @companyId, @companyName, @companyPhone, @companyTaxId, SAFE_CAST(@createdAt AS TIMESTAMP), @createdBy, STRUCT(@customer_address AS address, @customer_customerId AS customerId, @customer_fullName AS fullName, @customer_tin AS tin), SAFE_CAST(@date AS TIMESTAMP), @discountAmount, @grossAmount, @inclusiveSerialNumber, @invoiceNumber, @message, @netAmount, STRUCT(@payments_amountTendered AS amountTendered, @payments_changeAmount AS changeAmount, @payments_paymentDescription AS paymentDescription), @status, @storeId, @totalAmount, @uid, SAFE_CAST(@updatedAt AS TIMESTAMP), @updatedBy, @vatAmount, @vatExemptAmount, @vatableSales, @zeroRatedSales)
            """

            params = [
                bigquery.ScalarQueryParameter("orderId", "STRING", order_id),
                bigquery.ScalarQueryParameter("assignedCashierEmail", "STRING", after.get("assignedCashierEmail")),
                bigquery.ScalarQueryParameter("assignedCashierId", "STRING", after.get("assignedCashierId")),
                bigquery.ScalarQueryParameter("assignedCashierName", "STRING", after.get("assignedCashierName")),
                bigquery.ScalarQueryParameter("atpOrOcn", "STRING", after.get("atpOrOcn")),
                bigquery.ScalarQueryParameter("birPermitNo", "STRING", after.get("birPermitNo")),
                bigquery.ScalarQueryParameter("cashSale", "BOOL", bool(after.get("cashSale", False))),
                bigquery.ScalarQueryParameter("companyAddress", "STRING", after.get("companyAddress")),
                bigquery.ScalarQueryParameter("companyEmail", "STRING", after.get("companyEmail")),
                bigquery.ScalarQueryParameter("companyId", "STRING", after.get("companyId")),
                bigquery.ScalarQueryParameter("companyName", "STRING", after.get("companyName")),
                bigquery.ScalarQueryParameter("companyPhone", "STRING", after.get("companyPhone")),
                bigquery.ScalarQueryParameter("companyTaxId", "STRING", after.get("companyTaxId")),
                bigquery.ScalarQueryParameter("createdAt", "TIMESTAMP", ts_to_iso(after.get('createdAt'))),
                bigquery.ScalarQueryParameter("createdBy", "STRING", after.get("createdBy")),
                bigquery.ScalarQueryParameter("customer_address", "STRING", after.get("customerInfo", {}).get("address") if after.get("customerInfo") else None),
                bigquery.ScalarQueryParameter("customer_customerId", "STRING", after.get("customerInfo", {}).get("customerId") if after.get("customerInfo") else None),
                bigquery.ScalarQueryParameter("customer_fullName", "STRING", after.get("customerInfo", {}).get("fullName") if after.get("customerInfo") else None),
                bigquery.ScalarQueryParameter("customer_tin", "STRING", after.get("customerInfo", {}).get("tin") if after.get("customerInfo") else None),
                bigquery.ScalarQueryParameter("date", "TIMESTAMP", ts_to_iso(after.get('date'))),
                bigquery.ScalarQueryParameter("discountAmount", "FLOAT64", float(after.get('discountAmount', 0)) if after.get('discountAmount') is not None else None),
                bigquery.ScalarQueryParameter("grossAmount", "FLOAT64", float(after.get('grossAmount', 0)) if after.get('grossAmount') is not None else None),
                bigquery.ScalarQueryParameter("inclusiveSerialNumber", "STRING", after.get("inclusiveSerialNumber")),
                bigquery.ScalarQueryParameter("invoiceNumber", "STRING", after.get('invoiceNumber', order_id)),
                bigquery.ScalarQueryParameter("message", "STRING", after.get('message')),
                bigquery.ScalarQueryParameter("netAmount", "FLOAT64", float(after.get('netAmount', 0)) if after.get('netAmount') is not None else None),
                # Pass payments fields as scalars to build a STRUCT in SQL (avoid assigning STRING -> STRUCT)
                bigquery.ScalarQueryParameter("payments_amountTendered", "FLOAT64", float(after.get('payments', {}).get('amountTendered')) if after.get('payments') and after.get('payments').get('amountTendered') is not None else None),
                bigquery.ScalarQueryParameter("payments_changeAmount", "FLOAT64", float(after.get('payments', {}).get('changeAmount')) if after.get('payments') and after.get('payments').get('changeAmount') is not None else None),
                bigquery.ScalarQueryParameter("payments_paymentDescription", "STRING", after.get('payments', {}).get('paymentDescription') if after.get('payments') else None),
                bigquery.ScalarQueryParameter("status", "STRING", after.get('status')),
                bigquery.ScalarQueryParameter("storeId", "STRING", after.get('storeId')),
                bigquery.ScalarQueryParameter("totalAmount", "FLOAT64", float(after.get('totalAmount', 0)) if after.get('totalAmount') is not None else None),
                bigquery.ScalarQueryParameter("uid", "STRING", after.get('uid')),
                bigquery.ScalarQueryParameter("updatedAt", "TIMESTAMP", ts_to_iso(after.get('updatedAt'))),
                bigquery.ScalarQueryParameter("updatedBy", "STRING", after.get('updatedBy')),
                bigquery.ScalarQueryParameter("vatAmount", "FLOAT64", float(after.get('vatAmount', 0)) if after.get('vatAmount') is not None else None),
                bigquery.ScalarQueryParameter("vatExemptAmount", "FLOAT64", float(after.get('vatExemptAmount', 0)) if after.get('vatExemptAmount') is not None else None),
                bigquery.ScalarQueryParameter("vatableSales", "FLOAT64", float(after.get('vatableSales', 0)) if after.get('vatableSales') is not None else None),
                bigquery.ScalarQueryParameter("zeroRatedSales", "FLOAT64", float(after.get('zeroRatedSales', 0)) if after.get('zeroRatedSales') is not None else None)
            ]

            job_config = bigquery.QueryJobConfig(query_parameters=params)
            query_job = client.query(merge_query, job_config=job_config)
            query_job.result()
            print(f"✅ MERGE upsert completed for updated order {order_id}")
        except Exception as me:
            print(f"❌ MERGE (update) failed for order {order_id}: {me}")

    except Exception as e:
        print(f"❌ Unexpected error syncing updated order to BigQuery: {e}")


# Orders delete handler
@firestore_fn.on_document_deleted(document="orders/{orderId}", region="asia-east1")
def sync_order_to_bigquery_delete(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🗑️ Firestore trigger activated for deleted order - BigQuery sync")
    try:
        order_id = event.params.get("orderId")
        client = get_bigquery_client()
        delete_query = f"DELETE FROM `{BIGQUERY_ORDERS_TABLE}` WHERE orderId = @orderId"
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

        # Check if orderDetailsId already exists in BigQuery
        check_query = f"SELECT COUNT(*) as count FROM `{BIGQUERY_ORDER_DETAILS_TABLE}` WHERE orderDetailsId = @orderDetailsId"
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
            table = client.get_table(BIGQUERY_ORDER_DETAILS_TABLE)
            print(f"📤 Inserting payload into {BIGQUERY_ORDER_DETAILS_TABLE}")
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
        
        # Verify the orderDetails exists before updating
        check_query = f"SELECT COUNT(*) as count FROM `{BIGQUERY_ORDER_DETAILS_TABLE}` WHERE orderDetailsId = @orderDetailsId"
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
            delete_query = f"DELETE FROM `{BIGQUERY_ORDER_DETAILS_TABLE}` WHERE orderDetailsId = @orderDetailsId"
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
            table = client.get_table(BIGQUERY_ORDER_DETAILS_TABLE)
            print(f"📤 Inserting (update) payload into {BIGQUERY_ORDER_DETAILS_TABLE}: {json.dumps(payload)}")
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
        delete_query = f"DELETE FROM `{BIGQUERY_ORDER_DETAILS_TABLE}` WHERE orderDetailsId = @orderDetailsId"
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
        
        # Check if productId already exists in BigQuery
        check_query = f"SELECT COUNT(*) as count FROM `{BIGQUERY_PRODUCTS_TABLE}` WHERE productId = @productId"
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
            "createdAt": ts_to_iso(data.get("createdAt")),
            "createdBy": data.get("createdBy"),
            "description": data.get("description"),
            "discountType": data.get("discountType"),
            "discountValue": float(data.get("discountValue", 0)) if data.get("discountValue") is not None else None,
            "hasDiscount": bool(data.get("hasDiscount", False)),
            "imageUrl": data.get("imageUrl"),
            "isFavorite": bool(data.get("isFavorite", False)),
            "isVatApplicable": bool(data.get("isVatApplicable", False)),
            "productCode": data.get("productCode"),
            "productName": data.get("productName"),
            "sellingPrice": float(data.get("sellingPrice", 0)) if data.get("sellingPrice") is not None else None,
            "skuId": data.get("skuId"),
            "status": data.get("status"),
            "storeId": data.get("storeId"),
            "totalStock": int(data.get("totalStock", 0)) if data.get("totalStock") is not None else None,
            "uid": data.get("uid"),
            "unitType": data.get("unitType"),
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
            MERGE `{BIGQUERY_PRODUCTS_TABLE}` T
            USING (SELECT @productId AS productId) S
            ON T.productId = S.productId
            WHEN MATCHED THEN
              UPDATE SET
                barcodeId = @barcodeId,
                category = @category,
                companyId = @companyId,
                createdAt = SAFE_CAST(@createdAt AS TIMESTAMP),
                createdBy = @createdBy,
                description = @description,
                discountType = @discountType,
                discountValue = @discountValue,
                hasDiscount = @hasDiscount,
                imageUrl = @imageUrl,
                isFavorite = @isFavorite,
                isVatApplicable = @isVatApplicable,
                productCode = @productCode,
                productName = @productName,
                sellingPrice = @sellingPrice,
                skuId = @skuId,
                status = @status,
                storeId = @storeId,
                totalStock = @totalStock,
                uid = @uid,
                unitType = @unitType,
                updatedAt = SAFE_CAST(@updatedAt AS TIMESTAMP),
                updatedBy = @updatedBy
            WHEN NOT MATCHED THEN
              INSERT (productId, barcodeId, category, companyId, createdAt, createdBy, description, discountType, discountValue, hasDiscount, imageUrl, isFavorite, isVatApplicable, productCode, productName, sellingPrice, skuId, status, storeId, totalStock, uid, unitType, updatedAt, updatedBy)
              VALUES(@productId, @barcodeId, @category, @companyId, SAFE_CAST(@createdAt AS TIMESTAMP), @createdBy, @description, @discountType, @discountValue, @hasDiscount, @imageUrl, @isFavorite, @isVatApplicable, @productCode, @productName, @sellingPrice, @skuId, @status, @storeId, @totalStock, @uid, @unitType, SAFE_CAST(@updatedAt AS TIMESTAMP), @updatedBy)
            """

            params = [
                bigquery.ScalarQueryParameter("productId", "STRING", product_id),
                bigquery.ScalarQueryParameter("barcodeId", "STRING", data.get("barcodeId")),
                bigquery.ScalarQueryParameter("category", "STRING", data.get("category")),
                bigquery.ScalarQueryParameter("companyId", "STRING", data.get("companyId")),
                bigquery.ScalarQueryParameter("createdAt", "TIMESTAMP", ts_to_iso(data.get('createdAt'))),
                bigquery.ScalarQueryParameter("createdBy", "STRING", data.get("createdBy")),
                bigquery.ScalarQueryParameter("description", "STRING", data.get("description")),
                bigquery.ScalarQueryParameter("discountType", "STRING", data.get("discountType")),
                bigquery.ScalarQueryParameter("discountValue", "FLOAT64", float(data.get('discountValue', 0)) if data.get('discountValue') is not None else None),
                bigquery.ScalarQueryParameter("hasDiscount", "BOOL", bool(data.get('hasDiscount', False))),
                bigquery.ScalarQueryParameter("imageUrl", "STRING", data.get('imageUrl')),
                bigquery.ScalarQueryParameter("isFavorite", "BOOL", bool(data.get('isFavorite', False))),
                bigquery.ScalarQueryParameter("isVatApplicable", "BOOL", bool(data.get('isVatApplicable', False))),
                bigquery.ScalarQueryParameter("productCode", "STRING", data.get('productCode')),
                bigquery.ScalarQueryParameter("productName", "STRING", data.get('productName')),
                bigquery.ScalarQueryParameter("sellingPrice", "FLOAT64", float(data.get('sellingPrice', 0)) if data.get('sellingPrice') is not None else None),
                bigquery.ScalarQueryParameter("skuId", "STRING", data.get('skuId')),
                bigquery.ScalarQueryParameter("status", "STRING", data.get('status')),
                bigquery.ScalarQueryParameter("storeId", "STRING", data.get('storeId')),
                bigquery.ScalarQueryParameter("totalStock", "INT64", int(data.get('totalStock', 0)) if data.get('totalStock') is not None else None),
                bigquery.ScalarQueryParameter("uid", "STRING", data.get('uid')),
                bigquery.ScalarQueryParameter("unitType", "STRING", data.get('unitType')),
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
                createdAt = SAFE_CAST(@createdAt AS TIMESTAMP),
                createdBy = @createdBy,
                description = @description,
                discountType = @discountType,
                discountValue = @discountValue,
                hasDiscount = @hasDiscount,
                imageUrl = @imageUrl,
                isFavorite = @isFavorite,
                isVatApplicable = @isVatApplicable,
                productCode = @productCode,
                productName = @productName,
                sellingPrice = @sellingPrice,
                skuId = @skuId,
                status = @status,
                storeId = @storeId,
                totalStock = @totalStock,
                uid = @uid,
                unitType = @unitType,
                updatedAt = SAFE_CAST(@updatedAt AS TIMESTAMP),
                updatedBy = @updatedBy
            WHEN NOT MATCHED THEN
              INSERT (productId, barcodeId, category, companyId, createdAt, createdBy, description, discountType, discountValue, hasDiscount, imageUrl, isFavorite, isVatApplicable, productCode, productName, sellingPrice, skuId, status, storeId, totalStock, uid, unitType, updatedAt, updatedBy)
              VALUES(@productId, @barcodeId, @category, @companyId, SAFE_CAST(@createdAt AS TIMESTAMP), @createdBy, @description, @discountType, @discountValue, @hasDiscount, @imageUrl, @isFavorite, @isVatApplicable, @productCode, @productName, @sellingPrice, @skuId, @status, @storeId, @totalStock, @uid, @unitType, SAFE_CAST(@updatedAt AS TIMESTAMP), @updatedBy)
            """

            params = [
                bigquery.ScalarQueryParameter("productId", "STRING", product_id),
                bigquery.ScalarQueryParameter("barcodeId", "STRING", after.get("barcodeId")),
                bigquery.ScalarQueryParameter("category", "STRING", after.get("category")),
                bigquery.ScalarQueryParameter("companyId", "STRING", after.get("companyId")),
                bigquery.ScalarQueryParameter("createdAt", "TIMESTAMP", ts_to_iso(after.get('createdAt'))),
                bigquery.ScalarQueryParameter("createdBy", "STRING", after.get("createdBy")),
                bigquery.ScalarQueryParameter("description", "STRING", after.get("description")),
                bigquery.ScalarQueryParameter("discountType", "STRING", after.get("discountType")),
                bigquery.ScalarQueryParameter("discountValue", "FLOAT64", float(after.get('discountValue', 0)) if after.get('discountValue') is not None else None),
                bigquery.ScalarQueryParameter("hasDiscount", "BOOL", bool(after.get('hasDiscount', False))),
                bigquery.ScalarQueryParameter("imageUrl", "STRING", after.get('imageUrl')),
                bigquery.ScalarQueryParameter("isFavorite", "BOOL", bool(after.get('isFavorite', False))),
                bigquery.ScalarQueryParameter("isVatApplicable", "BOOL", bool(after.get('isVatApplicable', False))),
                bigquery.ScalarQueryParameter("productCode", "STRING", after.get('productCode')),
                bigquery.ScalarQueryParameter("productName", "STRING", after.get('productName')),
                bigquery.ScalarQueryParameter("sellingPrice", "FLOAT64", float(after.get('sellingPrice', 0)) if after.get('sellingPrice') is not None else None),
                bigquery.ScalarQueryParameter("skuId", "STRING", after.get('skuId')),
                bigquery.ScalarQueryParameter("status", "STRING", after.get('status')),
                bigquery.ScalarQueryParameter("storeId", "STRING", after.get('storeId')),
                bigquery.ScalarQueryParameter("totalStock", "INT64", int(after.get('totalStock', 0)) if after.get('totalStock') is not None else None),
                bigquery.ScalarQueryParameter("uid", "STRING", after.get('uid')),
                bigquery.ScalarQueryParameter("unitType", "STRING", after.get('unitType')),
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

    print(f"📄 orderSellingTracking Document ID: {ost_id}")
    print(f"📦 Document data: {data}")
    print(f"📋 Available fields: {list(data.keys()) if data else 'No fields'}")

    if not data:
        print("⚠️ Warning: orderSellingTracking document data is empty!")
        return

    try:
        client = get_bigquery_client()
        
        # Check if ordersSellingTracking already exists in BigQuery to avoid duplicate inserts
        check_query = f"SELECT COUNT(*) as count FROM `{BIGQUERY_ORDER_SELLING_TRACKING_TABLE}` WHERE ordersSellingTrackingId = @ostId"
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
            "companyId": data.get("companyId"),
            "createdAt": ts_to_iso(data.get("createdAt")),
            "createdBy": data.get("createdBy"),
            "orderId": data.get("orderId"),
            "orderDetailsId": data.get("orderDetailsId"),
            "status": data.get("status"),
            "storeId": data.get("storeId"),
            "uid": data.get("uid"),
            "updatedAt": ts_to_iso(data.get("updatedAt")),
            "updatedBy": data.get("updatedBy"),
            "itemIndex": to_int(data.get("itemIndex")),
            "productId": data.get("productId"),
            "productName": data.get("productName"),
            "price": to_numeric(data.get("price")),
            "quantity": to_int(data.get("quantity")),
            "discount": to_numeric(data.get("discount")),
            "discountType": data.get("discountType"),
            "vat": to_numeric(data.get("vat")),
            "total": to_numeric(data.get("total")),
            "isVatExempt": bool(data.get("isVatExempt", False)),
        }

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
            table = client.get_table(BIGQUERY_ORDER_SELLING_TRACKING_TABLE)
            print(f"📤 Inserting payload into {BIGQUERY_ORDER_SELLING_TRACKING_TABLE}")
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

        print(f"📄 orderSellingTracking ID (updated): {ost_id}")
        print(f"📦 New data: {after}")

        if not after:
            print("⚠️ Warning: updated document empty — skipping")
            return

        client = get_bigquery_client()

        # Delete existing row (if any) and re-insert full payload (mirrors orderDetails update flow)
        try:
            delete_query = f"DELETE FROM `{BIGQUERY_ORDER_SELLING_TRACKING_TABLE}` WHERE ordersSellingTrackingId = @orderSellingTrackingId"
            params = [bigquery.ScalarQueryParameter("orderSellingTrackingId", "STRING", ost_id)]
            job_config = bigquery.QueryJobConfig(query_parameters=params)
            delete_job = client.query(delete_query, job_config=job_config)
            delete_job.result()
            print(f"🗑️ Removed existing orderSellingTracking {ost_id} (if any)")
        except Exception as de:
            print(f"⚠️ Warning deleting existing orderSellingTracking row: {de}")

        # Recreate payload from the updated document with new schema
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

        payload = {
            "ordersSellingTrackingId": ost_id,
            "batchNumber": to_int(after.get("batchNumber")),
            "companyId": after.get("companyId"),
            "createdAt": ts_to_iso(after.get("createdAt")),
            "createdBy": after.get("createdBy"),
            "orderId": after.get("orderId"),
            "orderDetailsId": after.get("orderDetailsId"),
            "status": after.get("status"),
            "storeId": after.get("storeId"),
            "uid": after.get("uid"),
            "updatedAt": ts_to_iso(after.get("updatedAt")),
            "updatedBy": after.get("updatedBy"),
            "itemIndex": to_int(after.get("itemIndex")),
            "productId": after.get("productId"),
            "productName": after.get("productName"),
            "price": to_numeric(after.get("price")),
            "quantity": to_int(after.get("quantity")),
            "discount": to_numeric(after.get("discount")),
            "discountType": after.get("discountType"),
            "vat": to_numeric(after.get("vat")),
            "total": to_numeric(after.get("total")),
            "isVatExempt": bool(after.get("isVatExempt", False)),
        }

        # Clean payload and convert Decimal to JSON-friendly types
        def clean_payload(obj):
            if isinstance(obj, dict):
                return {k: clean_payload(v) for k, v in obj.items() if v is not None}
            if isinstance(obj, list):
                return [clean_payload(v) for v in obj]
            if isinstance(obj, Decimal):
                return str(obj)
            return obj

        payload = clean_payload(payload)

        try:
            table = client.get_table(BIGQUERY_ORDER_SELLING_TRACKING_TABLE)
            print(f"📤 Inserting (update) payload into {BIGQUERY_ORDER_SELLING_TRACKING_TABLE}: {payload}")
            errors = client.insert_rows_json(table, [payload])
            if errors:
                print(f"❌ Failed to insert updated orderSellingTracking: {errors}")
                print(f"❗ Failed payload: {payload}")
            else:
                print(f"✅ Re-inserted updated orderSellingTracking {ost_id}")
        except Exception as ie:
            print(f"❌ Exception while inserting updated orderSellingTracking to BigQuery: {ie}")

    except Exception as e:
        print(f"❌ Unexpected error syncing updated orderSellingTracking to BigQuery: {e}")


# OrderSellingTracking delete handler
@firestore_fn.on_document_deleted(document="orderSellingTracking/{orderSellingTrackingId}", region="asia-east1")
def sync_order_selling_tracking_delete(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🗑️ Firestore trigger activated for deleted orderSellingTracking - BigQuery sync")
    try:
        ost_id = event.params.get("orderSellingTrackingId")
        client = get_bigquery_client()
        delete_query = f"DELETE FROM `{BIGQUERY_ORDER_SELLING_TRACKING_TABLE}` WHERE ordersSellingTrackingId = @orderSellingTrackingId"
        params = [bigquery.ScalarQueryParameter("orderSellingTrackingId", "STRING", ost_id)]
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        job = client.query(delete_query, job_config=job_config)
        job.result()
        print(f"✅ Deleted orderSellingTracking {ost_id} from BigQuery (if existed)")
    except Exception as e:
        print(f"❌ Unexpected error deleting orderSellingTracking from BigQuery: {e}")