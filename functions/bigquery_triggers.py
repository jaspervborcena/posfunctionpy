from firebase_functions import firestore_fn
from datetime import datetime
import json
from datetime import timezone, timedelta

# Import configuration 
from config import get_bigquery_client, BIGQUERY_ORDERS_TABLE, BIGQUERY_ORDER_DETAILS_TABLE, BIGQUERY_PRODUCTS_TABLE
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


# Orders update handler: delete existing row then re-insert updated payload
@firestore_fn.on_document_updated(document="orders/{orderId}", region="asia-east1")
def sync_order_to_bigquery_update(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🔁 Firestore trigger activated for updated order - BigQuery sync")
    try:
        order_id = event.params.get("orderId")
        after = event.data.to_dict()

        print(f"📄 Order ID (updated): {order_id}")
        print(f"📦 New order data: {after}")

        if not after:
            print("⚠️ Warning: Updated order document empty — skipping")
            return

        client = get_bigquery_client()

        # Delete existing order row if present
        try:
            delete_query = f"DELETE FROM `{BIGQUERY_ORDERS_TABLE}` WHERE orderId = @orderId"
            params = [bigquery.ScalarQueryParameter("orderId", "STRING", order_id)]
            job_config = bigquery.QueryJobConfig(query_parameters=params)
            delete_job = client.query(delete_query, job_config=job_config)
            delete_job.result()
            print(f"🗑️ Removed existing order {order_id} (if any)")
        except Exception as de:
            print(f"⚠️ Warning deleting existing order row: {de}")

        # Recreate payload similar to create handler
        payload = {
            "assignedCashierEmail": after.get("assignedCashierEmail"),
            "assignedCashierId": after.get("assignedCashierId"),
            "assignedCashierName": after.get("assignedCashierName"),
            "atpOrOcn": after.get("atpOrOcn"),
            "birPermitNo": after.get("birPermitNo"),
            "cashSale": after.get("cashSale", False),
            "companyAddress": after.get("companyAddress"),
            "companyEmail": after.get("companyEmail"),
            "companyId": after.get("companyId"),
            "companyName": after.get("companyName"),
            "companyPhone": after.get("companyPhone"),
            "companyTaxId": after.get("companyTaxId"),
            "createdAt": after.get("createdAt").isoformat() if after.get("createdAt") else None,
            "createdBy": after.get("createdBy"),
            "customerInfo": {
                "address": after.get("customerInfo", {}).get("address") if after.get("customerInfo") else None,
                "customerId": after.get("customerInfo", {}).get("customerId") if after.get("customerInfo") else None,
                "fullName": after.get("customerInfo", {}).get("fullName") if after.get("customerInfo") else None,
                "tin": after.get("customerInfo", {}).get("tin") if after.get("customerInfo") else None
            } if after.get("customerInfo") else None,
            "date": after.get("date").isoformat() if after.get("date") else None,
            "discountAmount": float(after.get("discountAmount", 0)),
            "grossAmount": float(after.get("grossAmount", 0)),
            "inclusiveSerialNumber": after.get("inclusiveSerialNumber"),
            "invoiceNumber": after.get("invoiceNumber", order_id),
            "message": after.get("message"),
            "netAmount": float(after.get("netAmount", 0)),
            "payments": {
                "amountTendered": float(after.get("payments", {}).get("amountTendered", 0)) if after.get("payments") else 0,
                "changeAmount": float(after.get("payments", {}).get("changeAmount", 0)) if after.get("payments") else 0,
                "paymentDescription": after.get("payments", {}).get("paymentDescription") if after.get("payments") else None
            } if after.get("payments") else None,
            "status": after.get("status", "active"),
            "storeId": after.get("storeId"),
            "totalAmount": float(after.get("totalAmount", 0)),
            "uid": after.get("uid"),
            "updatedAt": after.get("updatedAt").isoformat() if after.get("updatedAt") else None,
            "updatedBy": after.get("updatedBy"),
            "vatAmount": float(after.get("vatAmount", 0)),
            "vatExemptAmount": float(after.get("vatExemptAmount", 0)),
            "vatableSales": float(after.get("vatableSales", 0)),
            "zeroRatedSales": float(after.get("zeroRatedSales", 0))
        }

        # Clean payload
        def clean_payload(obj):
            if isinstance(obj, dict):
                return {k: clean_payload(v) for k, v in obj.items() if v is not None}
            return obj

        payload = clean_payload(payload)
        payload["orderId"] = order_id

        # Insert updated row
        table = client.get_table(BIGQUERY_ORDERS_TABLE)
        errors = client.insert_rows_json(table, [payload])
        if errors:
            print(f"❌ Failed to insert updated order: {errors}")
        else:
            print(f"✅ Re-inserted updated order {order_id}")

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


# OrderDetails update handler: delete existing row (if any) then re-insert the full payload
@firestore_fn.on_document_updated(document="orderDetails/{orderDetailId}", region="asia-east1")
def sync_order_details_to_bigquery_update(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🔁 Firestore trigger activated for updated orderDetails - BigQuery sync")
    try:
        order_detail_id = event.params.get("orderDetailId")
        after = event.data.to_dict()

        print(f"📄 Order Detail ID (updated): {order_detail_id}")
        print(f"📦 New order detail data: {after}")

        if not after:
            print("⚠️ Warning: Updated orderDetails document empty — skipping")
            return

        client = get_bigquery_client()

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

        # Recreate payload similar to create handler
        payload = {
            "batchNumber": int(after.get("batchNumber")) if after.get("batchNumber") else None,
            "companyId": after.get("companyId"),
            "createdAt": after.get("createdAt").isoformat() if after.get("createdAt") else None,
            "createdBy": after.get("createdBy"),
            "orderId": after.get("orderId"),
            "storeId": after.get("storeId"),
            "uid": after.get("uid"),
            "updatedAt": after.get("updatedAt").isoformat() if after.get("updatedAt") else None,
            "updatedBy": after.get("updatedBy"),
            "items": []
        }

        for item in after.get("items", []):
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
            item_payload = {k: v for k, v in item_payload.items() if v is not None}
            payload["items"].append(item_payload)

        payload = {k: v for k, v in payload.items() if v is not None}
        payload["orderDetailsId"] = order_detail_id

        # Insert new payload
        table = client.get_table(BIGQUERY_ORDER_DETAILS_TABLE)
        errors = client.insert_rows_json(table, [payload])
        if errors:
            print(f"❌ Failed to insert updated orderDetails: {errors}")
        else:
            print(f"✅ Re-inserted updated orderDetails {order_detail_id}")

    except Exception as e:
        print(f"❌ Unexpected error syncing updated orderDetails to BigQuery: {e}")


# OrderDetails delete handler
@firestore_fn.on_document_deleted(document="orderDetails/{orderDetailId}", region="asia-east1")
def sync_order_details_to_bigquery_delete(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    print("🗑️ Firestore trigger activated for deleted orderDetails - BigQuery sync")
    try:
        order_detail_id = event.params.get("orderDetailId")
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

    try:
        product_id = event.params.get("productId")
        data = event.data.to_dict()

        print(f"📄 Product Document ID: {product_id}")
        print(f"📦 Product data: {data}")

        if not data:
            print("⚠️ Warning: Product document data is empty!")
            return
        # Only sync products created within the last 14 days
        try:
            created_at = data.get("createdAt")
            if created_at:
                # Normalize to UTC naive for comparison
                if getattr(created_at, 'tzinfo', None):
                    created_at_dt = created_at.astimezone(timezone.utc).replace(tzinfo=None)
                else:
                    created_at_dt = created_at

                cutoff = datetime.utcnow() - timedelta(days=14)
                if created_at_dt < cutoff:
                    print(f"⏭️ Product {product_id} created at {created_at_dt} is older than 14 days — skipping sync")
                    return
        except Exception as e:
            print(f"⚠️ Warning checking createdAt for recency: {e} — continuing with sync")

        client = get_bigquery_client()

        # Build payload using centralized helper to standardize column names
        payload = build_product_payload(product_id, data)

        print("🔀 Using MERGE to insert if not exists (idempotent)")
        try:
            # Build MERGE statement that inserts when productId does not exist
            merge_query = f"""
            MERGE `{BIGQUERY_PRODUCTS_TABLE}` T
            USING (SELECT @productId AS productId) S
            ON T.productId = S.productId
            WHEN NOT MATCHED THEN
              INSERT (productId, barcodeId, category, companyId, createdAt, createdBy, description, discountType, discountValue, hasDiscount, imageUrl, isFavorite, isVatApplicable, productCode, productName, sellingPrice, skuId, status, storeId, totalStock, uid, unitType, updatedAt, updatedBy)
              VALUES(@productId, @barcodeId, @category, @companyId, SAFE_CAST(@createdAt AS TIMESTAMP), @createdBy, @description, @discountType, @discountValue, @hasDiscount, @imageUrl, @isFavorite, @isVatApplicable, @productCode, @productName, @sellingPrice, @skuId, @status, @storeId, @totalStock, @uid, @unitType, SAFE_CAST(@updatedAt AS TIMESTAMP), @updatedBy)
            """

            # Prepare query parameters (use appropriate types and None where missing)
            params = [
                bigquery.ScalarQueryParameter("productId", "STRING", product_id),
                bigquery.ScalarQueryParameter("barcodeId", "STRING", data.get("barcodeId")),
                bigquery.ScalarQueryParameter("category", "STRING", data.get("category")),
                bigquery.ScalarQueryParameter("companyId", "STRING", data.get("companyId")),
                bigquery.ScalarQueryParameter("createdAt", "TIMESTAMP", data.get("createdAt").isoformat() if data.get("createdAt") else None),
                bigquery.ScalarQueryParameter("createdBy", "STRING", data.get("createdBy")),
                bigquery.ScalarQueryParameter("description", "STRING", data.get("description")),
                bigquery.ScalarQueryParameter("discountType", "STRING", data.get("discountType")),
                bigquery.ScalarQueryParameter("discountValue", "FLOAT64", float(data.get("discountValue")) if data.get("discountValue") is not None else None),
                bigquery.ScalarQueryParameter("hasDiscount", "BOOL", bool(data.get("hasDiscount", False))),
                bigquery.ScalarQueryParameter("imageUrl", "STRING", data.get("imageUrl")),
                bigquery.ScalarQueryParameter("isFavorite", "BOOL", bool(data.get("isFavorite", False))),
                bigquery.ScalarQueryParameter("isVatApplicable", "BOOL", bool(data.get("isVatApplicable", False))),
                bigquery.ScalarQueryParameter("productCode", "STRING", data.get("productCode")),
                bigquery.ScalarQueryParameter("productName", "STRING", data.get("productName")),
                bigquery.ScalarQueryParameter("sellingPrice", "FLOAT64", float(data.get("sellingPrice")) if data.get("sellingPrice") is not None else None),
                bigquery.ScalarQueryParameter("skuId", "STRING", data.get("skuId")),
                bigquery.ScalarQueryParameter("status", "STRING", data.get("status")),
                bigquery.ScalarQueryParameter("storeId", "STRING", data.get("storeId")),
                bigquery.ScalarQueryParameter("totalStock", "INT64", int(data.get("totalStock")) if data.get("totalStock") is not None else None),
                bigquery.ScalarQueryParameter("uid", "STRING", data.get("uid")),
                bigquery.ScalarQueryParameter("unitType", "STRING", data.get("unitType")),
                bigquery.ScalarQueryParameter("updatedAt", "TIMESTAMP", data.get("updatedAt").isoformat() if data.get("updatedAt") else None),
                bigquery.ScalarQueryParameter("updatedBy", "STRING", data.get("updatedBy"))
            ]

            job_config = bigquery.QueryJobConfig(query_parameters=params)
            query_job = client.query(merge_query, job_config=job_config)
            query_job.result()  # Wait for completion
            print(f"✅ MERGE completed for product {product_id}")

        except Exception as e:
            # If MERGE fails, fallback to insert_rows_json (best-effort)
            print(f"⚠️ MERGE failed: {e} — falling back to streaming insert")
            try:
                table = client.get_table(BIGQUERY_PRODUCTS_TABLE)
                errors = client.insert_rows_json(table, [payload])
                if errors:
                    print(f"❌ BigQuery insert fallback failed: {errors}")
                else:
                    print(f"✅ Fallback insert successful for product {product_id}")
            except Exception as ie:
                print(f"❌ Fallback insert also failed: {ie}")

    except Exception as e:
        print(f"❌ Unexpected error syncing product to BigQuery: {e}")


# Streaming insert variant (direct insert_rows_json) - mirrors orders/orderDetails behavior
@firestore_fn.on_document_created(document="products/{productId}", region="asia-east1")
def sync_products_to_bigquery_streaming(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    """Stream newly created Firestore product documents into BigQuery using insert_rows_json."""
    print("🔥 Firestore trigger activated for new product - BigQuery streaming insert")

    try:
        product_id = event.params.get("productId")
        data = event.data.to_dict()

        print(f"📄 Product Document ID: {product_id}")
        print(f"📦 Product data: {data}")

        if not data:
            print("⚠️ Warning: Product document data is empty!")
            return

        client = get_bigquery_client()

        # Build payload using centralized helper to standardize column names
        payload = build_product_payload(product_id, data)

        print(f"🧹 Final payload for streaming insert: {payload}")

        try:
            table = client.get_table(BIGQUERY_PRODUCTS_TABLE)
            errors = client.insert_rows_json(table, [payload])
            if errors:
                print(f"❌ BigQuery streaming insert failed with errors: {errors}")
            else:
                print(f"✅ BigQuery streaming insert successful for product {product_id}")
        except Exception as e:
            print(f"❌ Unexpected error during streaming insert: {e}")

    except Exception as e:
        print(f"❌ Unexpected error in streaming trigger: {e}")


# BigQuery trigger for updated product documents
@firestore_fn.on_document_updated(document="products/{productId}", region="asia-east1")
def sync_products_to_bigquery_update(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    """Sync updated Firestore product documents into BigQuery (MERGE -> update existing row).

    This performs a MERGE that updates the row when matched and inserts when not matched
    (idempotent)."""
    print("🔁 Firestore trigger activated for updated product - BigQuery sync")

    try:
        product_id = event.params.get("productId")
        # event.data has before/after; use after
        after = event.data.to_dict()

        print(f"📄 Product Document ID (updated): {product_id}")
        print(f"📦 New product data: {after}")

        if not after:
            print("⚠️ Warning: Updated product document has no data — skipping")
            return

        client = get_bigquery_client()

        # Build MERGE statement to update existing row or insert if missing
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

        # Prepare parameters (mirror create handler types)
        params = [
            bigquery.ScalarQueryParameter("productId", "STRING", product_id),
            bigquery.ScalarQueryParameter("barcodeId", "STRING", after.get("barcodeId")),
            bigquery.ScalarQueryParameter("category", "STRING", after.get("category")),
            bigquery.ScalarQueryParameter("companyId", "STRING", after.get("companyId")),
            bigquery.ScalarQueryParameter("createdAt", "TIMESTAMP", after.get("createdAt").isoformat() if after.get("createdAt") else None),
            bigquery.ScalarQueryParameter("createdBy", "STRING", after.get("createdBy")),
            bigquery.ScalarQueryParameter("description", "STRING", after.get("description")),
            bigquery.ScalarQueryParameter("discountType", "STRING", after.get("discountType")),
            bigquery.ScalarQueryParameter("discountValue", "FLOAT64", float(after.get("discountValue")) if after.get("discountValue") is not None else None),
            bigquery.ScalarQueryParameter("hasDiscount", "BOOL", bool(after.get("hasDiscount", False))),
            bigquery.ScalarQueryParameter("imageUrl", "STRING", after.get("imageUrl")),
            bigquery.ScalarQueryParameter("isFavorite", "BOOL", bool(after.get("isFavorite", False))),
            bigquery.ScalarQueryParameter("isVatApplicable", "BOOL", bool(after.get("isVatApplicable", False))),
            bigquery.ScalarQueryParameter("productCode", "STRING", after.get("productCode")),
            bigquery.ScalarQueryParameter("productName", "STRING", after.get("productName")),
            bigquery.ScalarQueryParameter("sellingPrice", "FLOAT64", float(after.get("sellingPrice")) if after.get("sellingPrice") is not None else None),
            bigquery.ScalarQueryParameter("skuId", "STRING", after.get("skuId")),
            bigquery.ScalarQueryParameter("status", "STRING", after.get("status")),
            bigquery.ScalarQueryParameter("storeId", "STRING", after.get("storeId")),
            bigquery.ScalarQueryParameter("totalStock", "INT64", int(after.get("totalStock")) if after.get("totalStock") is not None else None),
            bigquery.ScalarQueryParameter("uid", "STRING", after.get("uid")),
            bigquery.ScalarQueryParameter("unitType", "STRING", after.get("unitType")),
            bigquery.ScalarQueryParameter("updatedAt", "TIMESTAMP", after.get("updatedAt").isoformat() if after.get("updatedAt") else None),
            bigquery.ScalarQueryParameter("updatedBy", "STRING", after.get("updatedBy"))
        ]

        job_config = bigquery.QueryJobConfig(query_parameters=params)
        query_job = client.query(merge_query, job_config=job_config)
        query_job.result()
        print(f"✅ MERGE (update) completed for product {product_id}")

    except Exception as e:
        print(f"❌ Unexpected error syncing updated product to BigQuery: {e}")


# BigQuery trigger for deleted product documents
@firestore_fn.on_document_deleted(document="products/{productId}", region="asia-east1")
def sync_products_to_bigquery_delete(event: firestore_fn.Event[firestore_fn.DocumentSnapshot]) -> None:
    """Remove product row from BigQuery when Firestore product is deleted."""
    print("🗑️ Firestore trigger activated for product delete - BigQuery sync")

    try:
        product_id = event.params.get("productId")
        print(f"📄 Product Document ID (deleted): {product_id}")

        client = get_bigquery_client()

        delete_query = f"DELETE FROM `{BIGQUERY_PRODUCTS_TABLE}` WHERE productId = @productId"
        params = [bigquery.ScalarQueryParameter("productId", "STRING", product_id)]
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        query_job = client.query(delete_query, job_config=job_config)
        query_job.result()
        print(f"✅ Deleted product {product_id} from BigQuery (if existed)")

    except Exception as e:
        print(f"❌ Unexpected error deleting product from BigQuery: {e}")