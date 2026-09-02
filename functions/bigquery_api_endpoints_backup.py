from firebase_functions import https_fn
import json
from datetime import datetime, timedelta

# Import configuration 
from config import get_bigquery_client, BIGQUERY_ORDERS_TABLE, BIGQUERY_ORDER_DETAILS_TABLE, BIGQUERY_PRODUCTS_TABLE, DEFAULT_HEADERS, BACKFILL_PRESETS
from config import BQ_TABLES, COLLECTIONS

# Import authentication middleware
from auth_middleware import require_auth, require_store_access, get_user_info
from firebase_admin import firestore
from datetime import timezone, timedelta

try:
    from google.cloud import bigquery
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    print("WARNING: BigQuery library not available. BigQuery functions will be disabled.")

def parse_date_string(date_str):
    """
    Parse date string in either YYYYMMDD or YYYY-MM-DD format
    
    Args:
        date_str: Date string in YYYYMMDD or YYYY-MM-DD format
        
    Returns:
        datetime object or None if parsing fails
    """
    if not date_str:
        return None
    
    # Try YYYYMMDD format first
    if len(date_str) == 8 and date_str.isdigit():
        try:
            return datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            pass
    
    # Try YYYY-MM-DD format
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        pass
    
    return None

# API endpoint to get orders by storeId from BigQuery
@https_fn.on_request(region="asia-east1")
@require_auth
@require_store_access
def get_orders_by_store_bq(req: https_fn.Request) -> https_fn.Response:
    """Get all orders for a specific store ID from BigQuery"""
    
    # Handle CORS for web requests
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)
    
    # Get storeId and date filters from query parameters
    # Prefer explicit query param, but fall back to decorator-injected req.store_id
    store_id = None
    if hasattr(req, 'args'):
        store_id = req.args.get('storeId') or req.args.get('store_id')
    if not store_id and hasattr(req, 'store_id'):
        store_id = getattr(req, 'store_id')
    from_date = req.args.get('from')  # Expected format: YYYYMMDD or YYYY-MM-DD
    to_date = req.args.get('to')      # Expected format: YYYYMMDD or YYYY-MM-DD
    
    if not store_id:
        return https_fn.Response(
            json.dumps({"error": "storeId parameter is required"}),
            status=400,
            headers=DEFAULT_HEADERS
        )
    
    try:
        client = get_bigquery_client()
        
        # Build query
        query = f"""
        SELECT *
        FROM `{BIGQUERY_ORDERS_TABLE}`
        WHERE storeId = @store_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("store_id", "STRING", store_id)
            ]
        )
        
        # Add date filtering if provided
        if from_date and to_date:
            from_dt = parse_date_string(from_date)
            to_dt = parse_date_string(to_date)
            
            if from_dt and to_dt:
                query += " AND DATE(createdAt) BETWEEN @from_date AND @to_date"
                job_config.query_parameters.extend([
                    bigquery.ScalarQueryParameter("from_date", "DATE", from_dt.date()),
                    bigquery.ScalarQueryParameter("to_date", "DATE", to_dt.date())
                ])
        
        query += " ORDER BY createdAt DESC"
        
        print(f"🔍 BigQuery query: {query}")
        print(f"📋 Parameters: store_id={store_id}, from_date={from_date}, to_date={to_date}")
        
        # Execute query
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        
        # Convert results to list
        orders = []
        for row in results:
            order = dict(row)
            # Convert datetime objects to ISO strings for JSON serialization
            for key, value in order.items():
                if isinstance(value, datetime):
                    order[key] = value.isoformat()
            orders.append(order)
        
        response_data = {
            "success": True,
            "count": len(orders),
            "store_id": store_id,
            "filters": {
                "from_date": from_date,
                "to_date": to_date
            },
            "orders": orders
        }
        
        return https_fn.Response(
            json.dumps(response_data),
            status=200,
            headers=DEFAULT_HEADERS
        )
        
    except Exception as e:
        print(f"❌ BigQuery query error: {str(e)}")
        return https_fn.Response(
            json.dumps({
                "success": False,
                "error": str(e),
                "message": "Failed to query orders from BigQuery"
            }),
            status=500,
            headers=DEFAULT_HEADERS
        )

# API endpoint to get order details by storeId and orderId from BigQuery
@https_fn.on_request(region="asia-east1")
@require_auth
@require_store_access
def get_order_details_bq(req: https_fn.Request) -> https_fn.Response:
    """Get order details for a specific store and order from BigQuery"""
    
    # Handle CORS for web requests
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)
    
    # Get parameters from query string
    store_id = req.args.get('storeId')
    order_id = req.args.get('orderId')
    
    if not store_id:
        return https_fn.Response(
            json.dumps({"error": "storeId parameter is required"}),
            status=400,
            headers=DEFAULT_HEADERS
        )
    
    if not order_id:
        return https_fn.Response(
            json.dumps({"error": "orderId parameter is required"}),
            status=400,
            headers=DEFAULT_HEADERS
        )
    
    try:
        client = get_bigquery_client()
        
        # Query order details
        query = f"""
        SELECT *
        FROM `{BIGQUERY_ORDER_DETAILS_TABLE}`
        WHERE storeId = @store_id AND orderId = @order_id
        ORDER BY createdAt DESC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("store_id", "STRING", store_id),
                bigquery.ScalarQueryParameter("order_id", "STRING", order_id)
            ]
        )
        
        print(f"🔍 BigQuery order details query: {query}")
        print(f"📋 Parameters: store_id={store_id}, order_id={order_id}")
        
        # Execute query
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        
        # Convert results to list
        order_details = []
        for row in results:
            detail = dict(row)
            # Convert datetime objects to ISO strings for JSON serialization
            for key, value in detail.items():
                if isinstance(value, datetime):
                    detail[key] = value.isoformat()
            order_details.append(detail)
        
        response_data = {
            "success": True,
            "count": len(order_details),
            "store_id": store_id,
            "order_id": order_id,
            "order_details": order_details
        }
        
        return https_fn.Response(
            json.dumps(response_data),
            status=200,
            headers=DEFAULT_HEADERS
        )
        
    except Exception as e:
        print(f"❌ BigQuery order details query error: {str(e)}")
        return https_fn.Response(
            json.dumps({
                "success": False,
                "error": str(e),
                "message": "Failed to query order details from BigQuery"
            }),
            status=500,
            headers=DEFAULT_HEADERS
        )


# API endpoint to get products by storeId from BigQuery
@https_fn.on_request(region="asia-east1")
@require_auth
@require_store_access
def get_products_bq(req: https_fn.Request) -> https_fn.Response:
    """Get products for a specific store from BigQuery"""

    # Handle CORS preflight
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)

    store_id = req.args.get('storeId')
    product_code = req.args.get('productCode')
    sku_id = req.args.get('skuId')
    status = req.args.get('status')
    limit = int(req.args.get('limit', 100))

    if not store_id:
        return https_fn.Response(
            json.dumps({"error": "storeId parameter is required"}),
            status=400,
            headers=DEFAULT_HEADERS
        )

    try:
        client = get_bigquery_client()

        # Build base query
        query = f"""
        SELECT *
        FROM `{BIGQUERY_PRODUCTS_TABLE}`
        WHERE storeId = @store_id
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("store_id", "STRING", store_id)
            ]
        )

        # Add optional filters
        if product_code:
            query += " AND productCode = @product_code"
            job_config.query_parameters.append(
                bigquery.ScalarQueryParameter("product_code", "STRING", product_code)
            )

        if sku_id:
            query += " AND skuId = @sku_id"
            job_config.query_parameters.append(
                bigquery.ScalarQueryParameter("sku_id", "STRING", sku_id)
            )

        if status:
            query += " AND status = @status"
            job_config.query_parameters.append(
                bigquery.ScalarQueryParameter("status", "STRING", status)
            )

        query += " ORDER BY updatedAt DESC"

        # Apply explicit limit
        query += f" LIMIT {limit}"

        print(f"🔍 BigQuery products query: {query}")
        print(f"📋 Parameters: store_id={store_id}, product_code={product_code}, sku_id={sku_id}, status={status}, limit={limit}")

        query_job = client.query(query, job_config=job_config)
        results = query_job.result()

        products = []
        for row in results:
            prod = dict(row)
            # Convert timestamps to ISO strings
            for key, value in prod.items():
                if isinstance(value, datetime):
                    prod[key] = value.isoformat()
            products.append(prod)

        response_data = {
            "success": True,
            "count": len(products),
            "store_id": store_id,
            "products": products
        }

        return https_fn.Response(
            json.dumps(response_data),
            status=200,
            headers=DEFAULT_HEADERS
        )

    except Exception as e:
        print(f"❌ BigQuery products query error: {str(e)}")
        return https_fn.Response(
            json.dumps({
                "success": False,
                "error": str(e),
                "message": "Failed to query products from BigQuery"
            }),
            status=500,
            headers=DEFAULT_HEADERS
        )


# Manual backfill endpoint for products -> BigQuery
@https_fn.on_request(region="asia-east1")
@require_auth
@require_store_access
def backfill_products_bq(req: https_fn.Request) -> https_fn.Response:
    """Backfill products into BigQuery for a date range.

    Accepts JSON POST body or query params:
    - mode: 'last2weeks' | 'range'  (enum)
    - start: YYYY-MM-DD (required if mode=='range')
    - end: YYYY-MM-DD   (required if mode=='range')
    - storeId: optional store filter
    """

    # CORS preflight
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)

    if req.method != 'POST':
        return https_fn.Response(json.dumps({"error": "Method not allowed"}), status=405, headers=DEFAULT_HEADERS)

    try:
        body = req.get_json(silent=True) or {}
    except Exception:
        body = {}

    mode = (body.get('mode') or req.args.get('mode') or 'last2weeks')
    store_id = body.get('storeId') or req.args.get('storeId')

    # Determine date range
    try:
        # Preset enum mapping lives in config.py as BACKFILL_PRESETS
        preset = body.get('preset') or req.args.get('preset')
        if preset:
            if preset not in BACKFILL_PRESETS:
                return https_fn.Response(json.dumps({"error": f"Unknown preset: {preset}"}), status=400, headers=DEFAULT_HEADERS)
            start_str, end_str = BACKFILL_PRESETS[preset]
            start_dt = datetime.fromisoformat(start_str)
            end_dt = datetime.fromisoformat(end_str)
        else:
            if mode == 'last2weeks':
                end_dt = datetime.utcnow()
                start_dt = end_dt - timedelta(days=14)
            elif mode == 'range':
                start_str = body.get('start') or req.args.get('start')
                end_str = body.get('end') or req.args.get('end')
                if not start_str or not end_str:
                    return https_fn.Response(json.dumps({"error": "start and end required for mode=range"}), status=400, headers=DEFAULT_HEADERS)
                start_dt = datetime.fromisoformat(start_str)
                end_dt = datetime.fromisoformat(end_str)
            else:
                return https_fn.Response(json.dumps({"error": "invalid mode"}), status=400, headers=DEFAULT_HEADERS)
    except Exception as e:
        return https_fn.Response(json.dumps({"error": f"Invalid date format: {e}"}), status=400, headers=DEFAULT_HEADERS)

    # Optional store access validation done by require_store_access decorator, but also pass to query
    try:
        db = firestore.client()
        client = get_bigquery_client()

        # Query Firestore for products within date range.
        # NOTE: we intentionally do NOT add an index-creating filter on storeId here
        # because the combination of range on createdAt + equality on storeId requires
        # a composite index in Firestore. To avoid that deployment-time index
        # requirement, we fetch by date range and filter by storeId in Python.
        coll = db.collection(COLLECTIONS.get('products', 'products'))
        query = coll.where('createdAt', '>=', start_dt).where('createdAt', '<=', end_dt)

        docs = list(query.stream())
        inserted = 0
        errors = []

        for doc in docs:
            d = doc.to_dict()
            pid = doc.id
            # If a storeId was requested, filter client-side to avoid Firestore
            # composite index requirement (range + equality).
            if store_id and d.get('storeId') != store_id:
                continue

            # Prepare MERGE like in trigger
            merge_query = f"""
            MERGE `{BIGQUERY_PRODUCTS_TABLE}` T
            USING (SELECT @productId AS productId) S
            ON T.productId = S.productId
            WHEN NOT MATCHED THEN
              INSERT (productId, barcodeId, category, companyId, createdAt, createdBy, description, discountType, discountValue, hasDiscount, imageUrl, isFavorite, isVatApplicable, productCode, productName, sellingPrice, skuId, status, storeId, totalStock, uid, unitType, updatedAt, updatedBy)
              VALUES(@productId, @barcodeId, @category, @companyId, SAFE_CAST(@createdAt AS TIMESTAMP), @createdBy, @description, @discountType, @discountValue, @hasDiscount, @imageUrl, @isFavorite, @isVatApplicable, @productCode, @productName, @sellingPrice, @skuId, @status, @storeId, @totalStock, @uid, @unitType, SAFE_CAST(@updatedAt AS TIMESTAMP), @updatedBy)
            """

            from bq_helpers import build_product_payload
            # Build canonical payload using helper to ensure consistent column names
            payload = build_product_payload(pid, d)
            # Attempt MERGE like in trigger using canonical keys
            params = [
                bigquery.ScalarQueryParameter("productId", "STRING", pid),
                bigquery.ScalarQueryParameter("barcodeId", "STRING", d.get('barcodeId')),
                bigquery.ScalarQueryParameter("category", "STRING", d.get('category')),
                bigquery.ScalarQueryParameter("companyId", "STRING", d.get('companyId')),
                bigquery.ScalarQueryParameter("createdAt", "TIMESTAMP", d.get('createdAt').isoformat() if d.get('createdAt') else None),
                bigquery.ScalarQueryParameter("createdBy", "STRING", d.get('createdBy')),
                bigquery.ScalarQueryParameter("description", "STRING", d.get('description')),
                bigquery.ScalarQueryParameter("discountType", "STRING", d.get('discountType')),
                bigquery.ScalarQueryParameter("discountValue", "FLOAT64", float(d.get('discountValue')) if d.get('discountValue') is not None else None),
                bigquery.ScalarQueryParameter("hasDiscount", "BOOL", bool(d.get('hasDiscount', False))),
                bigquery.ScalarQueryParameter("imageUrl", "STRING", d.get('imageUrl')),
                bigquery.ScalarQueryParameter("isFavorite", "BOOL", bool(d.get('isFavorite', False))),
                bigquery.ScalarQueryParameter("isVatApplicable", "BOOL", bool(d.get('isVatApplicable', False))),
                bigquery.ScalarQueryParameter("productCode", "STRING", d.get('productCode')),
                bigquery.ScalarQueryParameter("productName", "STRING", d.get('productName')),
                bigquery.ScalarQueryParameter("sellingPrice", "FLOAT64", float(d.get('sellingPrice')) if d.get('sellingPrice') is not None else None),
                bigquery.ScalarQueryParameter("skuId", "STRING", d.get('skuId')),
                bigquery.ScalarQueryParameter("status", "STRING", d.get('status')),
                bigquery.ScalarQueryParameter("storeId", "STRING", d.get('storeId')),
                bigquery.ScalarQueryParameter("totalStock", "INT64", int(d.get('totalStock')) if d.get('totalStock') is not None else None),
                bigquery.ScalarQueryParameter("uid", "STRING", d.get('uid')),
                bigquery.ScalarQueryParameter("unitType", "STRING", d.get('unitType')),
                bigquery.ScalarQueryParameter("updatedAt", "TIMESTAMP", d.get('updatedAt').isoformat() if d.get('updatedAt') else None),
                bigquery.ScalarQueryParameter("updatedBy", "STRING", d.get('updatedBy'))
            ]

            try:
                job_config = bigquery.QueryJobConfig(query_parameters=params)
                query_job = client.query(merge_query, job_config=job_config)
                query_job.result()
                inserted += 1
            except Exception as e:
                errors.append({"productId": pid, "error": str(e)})

        return https_fn.Response(json.dumps({"success": True, "inserted": inserted, "errors": errors}), status=200, headers=DEFAULT_HEADERS)

    except Exception as e:
        print(f"❌ Backfill failed: {e}")
        return https_fn.Response(json.dumps({"success": False, "error": str(e)}), status=500, headers=DEFAULT_HEADERS)


# Manual backfill endpoint for orders -> BigQuery
@https_fn.on_request(region="asia-east1")
@require_auth
@require_store_access
def backfill_orders_bq(req: https_fn.Request) -> https_fn.Response:
    """Backfill orders into BigQuery for a date range.

    Accepts same payload as products backfill: mode/preset/range and optional storeId.
    """

    # CORS preflight
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)

    if req.method != 'POST':
        return https_fn.Response(json.dumps({"error": "Method not allowed"}), status=405, headers=DEFAULT_HEADERS)

    try:
        body = req.get_json(silent=True) or {}
    except Exception:
        body = {}

    mode = (body.get('mode') or req.args.get('mode') or 'last2weeks')
    store_id = body.get('storeId') or req.args.get('storeId')

    # Determine date range (reuse logic from products backfill)
    try:
        preset = body.get('preset') or req.args.get('preset')
        if preset:
            if preset not in BACKFILL_PRESETS:
                return https_fn.Response(json.dumps({"error": f"Unknown preset: {preset}"}), status=400, headers=DEFAULT_HEADERS)
            start_str, end_str = BACKFILL_PRESETS[preset]
            start_dt = datetime.fromisoformat(start_str)
            end_dt = datetime.fromisoformat(end_str)
        else:
            if mode == 'last2weeks':
                end_dt = datetime.utcnow()
                start_dt = end_dt - timedelta(days=14)
            elif mode == 'range':
                start_str = body.get('start') or req.args.get('start')
                end_str = body.get('end') or req.args.get('end')
                if not start_str or not end_str:
                    return https_fn.Response(json.dumps({"error": "start and end required for mode=range"}), status=400, headers=DEFAULT_HEADERS)
                start_dt = datetime.fromisoformat(start_str)
                end_dt = datetime.fromisoformat(end_str)
            else:
                return https_fn.Response(json.dumps({"error": "invalid mode"}), status=400, headers=DEFAULT_HEADERS)
    except Exception as e:
        return https_fn.Response(json.dumps({"error": f"Invalid date format: {e}"}), status=400, headers=DEFAULT_HEADERS)

    try:
        db = firestore.client()
        client = get_bigquery_client()

        coll = db.collection(COLLECTIONS.get('orders', 'orders'))
        query = coll.where('createdAt', '>=', start_dt).where('createdAt', '<=', end_dt)

        docs = list(query.stream())
        inserted = 0
        errors = []

        for doc in docs:
            d = doc.to_dict()
            oid = doc.id
            if store_id and d.get('storeId') != store_id:
                continue

            # Attempt MERGE (insert if not exists) similar to products approach
            merge_query = f"""
            MERGE `{BIGQUERY_ORDERS_TABLE}` T
            USING (SELECT @orderId AS orderId) S
            ON T.orderId = S.orderId
            WHEN NOT MATCHED THEN
              INSERT (orderId, assignedCashierEmail, assignedCashierId, assignedCashierName, atpOrOcn, birPermitNo, cashSale, companyAddress, companyEmail, companyId, companyName, companyPhone, companyTaxId, createdAt, createdBy, customerInfo, date, discountAmount, grossAmount, inclusiveSerialNumber, invoiceNumber, message, netAmount, payments, status, storeId, totalAmount, uid, updatedAt, updatedBy, vatAmount, vatExemptAmount, vatableSales, zeroRatedSales)
                            VALUES(@orderId, @assignedCashierEmail, @assignedCashierId, @assignedCashierName, @atpOrOcn, @birPermitNo, @cashSale, @companyAddress, @companyEmail, @companyId, @companyName, @companyPhone, @companyTaxId, SAFE_CAST(@createdAt AS TIMESTAMP), @createdBy, STRUCT(@customer_address AS address, @customer_customerId AS customerId, @customer_fullName AS fullName, @customer_tin AS tin), SAFE_CAST(@date AS TIMESTAMP), @discountAmount, @grossAmount, @inclusiveSerialNumber, @invoiceNumber, @message, @netAmount, STRUCT(@payments_amountTendered AS amountTendered, @payments_changeAmount AS changeAmount, @payments_paymentDescription AS paymentDescription), @status, @storeId, @totalAmount, @uid, SAFE_CAST(@updatedAt AS TIMESTAMP), @updatedBy, @vatAmount, @vatExemptAmount, @vatableSales, @zeroRatedSales)
            """

            # Prepare parameters (many are nullable)
            params = [
                bigquery.ScalarQueryParameter("orderId", "STRING", oid),
                bigquery.ScalarQueryParameter("assignedCashierEmail", "STRING", d.get('assignedCashierEmail')),
                bigquery.ScalarQueryParameter("assignedCashierId", "STRING", d.get('assignedCashierId')),
                bigquery.ScalarQueryParameter("assignedCashierName", "STRING", d.get('assignedCashierName')),
                bigquery.ScalarQueryParameter("atpOrOcn", "STRING", d.get('atpOrOcn')),
                bigquery.ScalarQueryParameter("birPermitNo", "STRING", d.get('birPermitNo')),
                bigquery.ScalarQueryParameter("cashSale", "BOOL", bool(d.get('cashSale', False))),
                bigquery.ScalarQueryParameter("companyAddress", "STRING", d.get('companyAddress')),
                bigquery.ScalarQueryParameter("companyEmail", "STRING", d.get('companyEmail')),
                bigquery.ScalarQueryParameter("companyId", "STRING", d.get('companyId')),
                bigquery.ScalarQueryParameter("companyName", "STRING", d.get('companyName')),
                bigquery.ScalarQueryParameter("companyPhone", "STRING", d.get('companyPhone')),
                bigquery.ScalarQueryParameter("companyTaxId", "STRING", d.get('companyTaxId')),
                bigquery.ScalarQueryParameter("createdAt", "TIMESTAMP", d.get('createdAt').isoformat() if d.get('createdAt') else None),
                bigquery.ScalarQueryParameter("createdBy", "STRING", d.get('createdBy')),
                bigquery.ScalarQueryParameter("customer_address", "STRING", d.get('customerInfo', {}).get('address') if d.get('customerInfo') else None),
                bigquery.ScalarQueryParameter("customer_customerId", "STRING", d.get('customerInfo', {}).get('customerId') if d.get('customerInfo') else None),
                bigquery.ScalarQueryParameter("customer_fullName", "STRING", d.get('customerInfo', {}).get('fullName') if d.get('customerInfo') else None),
                bigquery.ScalarQueryParameter("customer_tin", "STRING", d.get('customerInfo', {}).get('tin') if d.get('customerInfo') else None),
                bigquery.ScalarQueryParameter("date", "TIMESTAMP", d.get('date').isoformat() if d.get('date') else None),
                bigquery.ScalarQueryParameter("discountAmount", "FLOAT64", float(d.get('discountAmount', 0)) if d.get('discountAmount') is not None else None),
                bigquery.ScalarQueryParameter("grossAmount", "FLOAT64", float(d.get('grossAmount', 0)) if d.get('grossAmount') is not None else None),
                bigquery.ScalarQueryParameter("inclusiveSerialNumber", "STRING", d.get('inclusiveSerialNumber')),
                bigquery.ScalarQueryParameter("invoiceNumber", "STRING", d.get('invoiceNumber') or oid),
                bigquery.ScalarQueryParameter("message", "STRING", d.get('message')),
                bigquery.ScalarQueryParameter("netAmount", "FLOAT64", float(d.get('netAmount', 0)) if d.get('netAmount') is not None else None),
                # Pass payments subfields as scalars so SQL can construct a STRUCT for the payments column
                bigquery.ScalarQueryParameter("payments_amountTendered", "FLOAT64", float(d.get('payments', {}).get('amountTendered')) if d.get('payments') and d.get('payments').get('amountTendered') is not None else None),
                bigquery.ScalarQueryParameter("payments_changeAmount", "FLOAT64", float(d.get('payments', {}).get('changeAmount')) if d.get('payments') and d.get('payments').get('changeAmount') is not None else None),
                bigquery.ScalarQueryParameter("payments_paymentDescription", "STRING", d.get('payments', {}).get('paymentDescription') if d.get('payments') else None),
                bigquery.ScalarQueryParameter("status", "STRING", d.get('status')),
                bigquery.ScalarQueryParameter("storeId", "STRING", d.get('storeId')),
                bigquery.ScalarQueryParameter("totalAmount", "FLOAT64", float(d.get('totalAmount', 0)) if d.get('totalAmount') is not None else None),
                bigquery.ScalarQueryParameter("uid", "STRING", d.get('uid')),
                bigquery.ScalarQueryParameter("updatedAt", "TIMESTAMP", d.get('updatedAt').isoformat() if d.get('updatedAt') else None),
                bigquery.ScalarQueryParameter("updatedBy", "STRING", d.get('updatedBy')),
                bigquery.ScalarQueryParameter("vatAmount", "FLOAT64", float(d.get('vatAmount', 0)) if d.get('vatAmount') is not None else None),
                bigquery.ScalarQueryParameter("vatExemptAmount", "FLOAT64", float(d.get('vatExemptAmount', 0)) if d.get('vatExemptAmount') is not None else None),
                bigquery.ScalarQueryParameter("vatableSales", "FLOAT64", float(d.get('vatableSales', 0)) if d.get('vatableSales') is not None else None),
                bigquery.ScalarQueryParameter("zeroRatedSales", "FLOAT64", float(d.get('zeroRatedSales', 0)) if d.get('zeroRatedSales') is not None else None)
            ]

            try:
                job_config = bigquery.QueryJobConfig(query_parameters=params)
                query_job = client.query(merge_query, job_config=job_config)
                query_job.result()
                inserted += 1
            except Exception as e:
                # fallback to streaming insert for complex nested fields
                try:
                    table = client.get_table(BIGQUERY_ORDERS_TABLE)
                    # build payload similar to sync_order_to_bigquery
                    payload = d.copy()
                    payload['orderId'] = oid
                    # convert datetimes
                    for k, v in list(payload.items()):
                        if isinstance(v, datetime):
                            payload[k] = v.isoformat()
                    errors_local = client.insert_rows_json(table, [payload])
                    if errors_local:
                        errors.append({"orderId": oid, "error": str(errors_local)})
                    else:
                        inserted += 1
                except Exception as ie:
                    errors.append({"orderId": oid, "error": str(ie)})

        return https_fn.Response(json.dumps({"success": True, "inserted": inserted, "errors": errors}), status=200, headers=DEFAULT_HEADERS)

    except Exception as e:
        print(f"❌ Backfill orders failed: {e}")
        return https_fn.Response(json.dumps({"success": False, "error": str(e)}), status=500, headers=DEFAULT_HEADERS)


# Manual backfill endpoint for orderDetails -> BigQuery
@https_fn.on_request(region="asia-east1")
@require_auth
@require_store_access
def backfill_order_details_bq(req: https_fn.Request) -> https_fn.Response:
    """Backfill orderDetails into BigQuery for a date range.

    This uses streaming insert fallback because orderDetails contains nested items arrays.
    """
    # CORS preflight
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)

    if req.method != 'POST':
        return https_fn.Response(json.dumps({"error": "Method not allowed"}), status=405, headers=DEFAULT_HEADERS)

    try:
        body = req.get_json(silent=True) or {}
    except Exception:
        body = {}

    mode = (body.get('mode') or req.args.get('mode') or 'last2weeks')
    store_id = body.get('storeId') or req.args.get('storeId')

    # Determine date range
    try:
        preset = body.get('preset') or req.args.get('preset')
        if preset:
            if preset not in BACKFILL_PRESETS:
                return https_fn.Response(json.dumps({"error": f"Unknown preset: {preset}"}), status=400, headers=DEFAULT_HEADERS)
            start_str, end_str = BACKFILL_PRESETS[preset]
            start_dt = datetime.fromisoformat(start_str)
            end_dt = datetime.fromisoformat(end_str)
        else:
            if mode == 'last2weeks':
                end_dt = datetime.utcnow()
                start_dt = end_dt - timedelta(days=14)
            elif mode == 'range':
                start_str = body.get('start') or req.args.get('start')
                end_str = body.get('end') or req.args.get('end')
                if not start_str or not end_str:
                    return https_fn.Response(json.dumps({"error": "start and end required for mode=range"}), status=400, headers=DEFAULT_HEADERS)
                start_dt = datetime.fromisoformat(start_str)
                end_dt = datetime.fromisoformat(end_str)
            else:
                return https_fn.Response(json.dumps({"error": "invalid mode"}), status=400, headers=DEFAULT_HEADERS)
    except Exception as e:
        return https_fn.Response(json.dumps({"error": f"Invalid date format: {e}"}), status=400, headers=DEFAULT_HEADERS)

    try:
        db = firestore.client()
        client = get_bigquery_client()

        coll = db.collection(COLLECTIONS.get('orderDetails', 'orderDetails'))
        query = coll.where('createdAt', '>=', start_dt).where('createdAt', '<=', end_dt)

        docs = list(query.stream())
        inserted = 0
        errors = []

        for doc in docs:
            d = doc.to_dict()
            odid = doc.id
            if store_id and d.get('storeId') != store_id:
                continue

            # Build payload as per trigger
            payload = {
                "batchNumber": int(d.get("batchNumber")) if d.get("batchNumber") else None,
                "companyId": d.get("companyId"),
                "createdAt": d.get("createdAt").isoformat() if d.get("createdAt") else None,
                "createdBy": d.get("createdBy"),
                "orderId": d.get("orderId"),
                "storeId": d.get("storeId"),
                "uid": d.get("uid"),
                "updatedAt": d.get("updatedAt").isoformat() if d.get("updatedAt") else None,
                "updatedBy": d.get("updatedBy"),
                "items": []
            }

            for item in d.get("items", []):
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
            payload["orderDetailsId"] = odid

            try:
                table = client.get_table(BIGQUERY_ORDER_DETAILS_TABLE)
                errors_local = client.insert_rows_json(table, [payload])
                if errors_local:
                    errors.append({"orderDetailsId": odid, "error": str(errors_local)})
                else:
                    inserted += 1
            except Exception as e:
                errors.append({"orderDetailsId": odid, "error": str(e)})

        return https_fn.Response(json.dumps({"success": True, "inserted": inserted, "errors": errors}), status=200, headers=DEFAULT_HEADERS)

    except Exception as e:
        print(f"❌ Backfill orderDetails failed: {e}")
        return https_fn.Response(json.dumps({"success": False, "error": str(e)}), status=500, headers=DEFAULT_HEADERS)

# API endpoint to get orders by date range from BigQuery
@https_fn.on_request(region="asia-east1")
@require_auth
def get_orders_by_date_bq(req: https_fn.Request) -> https_fn.Response:
    """Get orders filtered by date range with optional store filter from BigQuery"""
    
    # Handle CORS for web requests
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)
    
    # Get parameters from query string
    from_date = req.args.get('from')
    to_date = req.args.get('to')
    store_id = req.args.get('storeId')  # Optional
    
    # Validate required parameters
    if not from_date:
        return https_fn.Response(
            json.dumps({"error": "from parameter is required (format: YYYYMMDD or YYYY-MM-DD)"}),
            status=400,
            headers=DEFAULT_HEADERS
        )
    
    if not to_date:
        return https_fn.Response(
            json.dumps({"error": "to parameter is required (format: YYYYMMDD or YYYY-MM-DD)"}),
            status=400,
            headers=DEFAULT_HEADERS
        )
    
    # Parse dates
    from_dt = parse_date_string(from_date)
    to_dt = parse_date_string(to_date)
    
    if not from_dt:
        return https_fn.Response(
            json.dumps({"error": "Invalid from date format. Use YYYYMMDD or YYYY-MM-DD"}),
            status=400,
            headers=DEFAULT_HEADERS
        )
    
    if not to_dt:
        return https_fn.Response(
            json.dumps({"error": "Invalid to date format. Use YYYYMMDD or YYYY-MM-DD"}),
            status=400,
            headers=DEFAULT_HEADERS
        )
    
    # Validate store access if storeId is provided
    if store_id:
        from auth_middleware import check_store_access, extract_user_permissions
        has_access, access_error = check_store_access(req.user, store_id)
        if not has_access:
            perms = extract_user_permissions(req.user)
            return https_fn.Response(
                json.dumps({
                    "success": False,
                    "error": "Access denied",
                    "message": access_error,
                    "requested_store": store_id,
                    "user_store": perms.get('storeId')
                }),
                status=403,
                headers=DEFAULT_HEADERS
            )
    
    try:
        client = get_bigquery_client()
        
        # Build query parameters list
        query_parameters = [
            bigquery.ScalarQueryParameter("from_date", "DATE", from_dt.date()),
            bigquery.ScalarQueryParameter("to_date", "DATE", to_dt.date())
        ]
        
        # Build query
        query = f"""
        SELECT *
        FROM `{BIGQUERY_ORDERS_TABLE}`
        WHERE DATE(createdAt) BETWEEN @from_date AND @to_date
        """
        
        # Add store filter if provided
        if store_id:
            query += " AND storeId = @store_id"
            query_parameters.append(
                bigquery.ScalarQueryParameter("store_id", "STRING", store_id)
            )
        
        query += " ORDER BY createdAt DESC"
        
        # Create job configuration with all parameters
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        
        print(f"🔍 BigQuery date range query: {query}")
        print(f"📋 Parameters: from_date={from_dt.date()}, to_date={to_dt.date()}, store_id={store_id}")
        
        # Execute query with timeout and error handling
        print(f"⏳ Starting BigQuery job...")
        query_job = client.query(query, job_config=job_config)
        
        # Wait for job completion with timeout
        try:
            results = query_job.result(timeout=30)  # 30 second timeout
            print(f"✅ BigQuery job completed, processing results...")
        except Exception as job_error:
            print(f"❌ BigQuery job failed or timed out: {job_error}")
            # Check if it's a timeout vs actual failure
            if "timeout" in str(job_error).lower():
                print(f"⚠️ Query timed out but may still be running. Job ID: {query_job.job_id}")
            raise job_error
        
        # Convert results to list with better error handling
        orders = []
        row_count = 0
        try:
            for row in results:
                row_count += 1
                order = {}
                # Safer conversion of row data
                for key, value in row.items():
                    try:
                        if value is None:
                            order[key] = None
                        elif isinstance(value, datetime):
                            order[key] = value.isoformat()
                        elif hasattr(value, 'isoformat'):  # Other datetime-like objects
                            order[key] = value.isoformat()
                        else:
                            order[key] = value
                    except Exception as conv_error:
                        print(f"⚠️ Error converting field {key}: {conv_error}")
                        order[key] = str(value) if value is not None else None
                orders.append(order)
                
                # Safety check for large result sets
                if row_count > 10000:  # Limit to prevent memory issues
                    print(f"⚠️ Result set truncated at {row_count} rows to prevent memory issues")
                    break
            
            print(f"📊 Successfully processed {len(orders)} orders")
        except Exception as processing_error:
            print(f"❌ Error processing results: {processing_error}")
            raise processing_error
        
        response_data = {
            "success": True,
            "count": len(orders),
            "filters": {
                "from_date": from_date,
                "to_date": to_date,
                "store_id": store_id
            },
            "orders": orders
        }
        
        return https_fn.Response(
            json.dumps(response_data),
            status=200,
            headers=DEFAULT_HEADERS
        )
        
    except Exception as e:
        print(f"❌ BigQuery date range query error: {str(e)}")
        return https_fn.Response(
            json.dumps({
                "success": False,
                "error": str(e),
                "message": "Failed to query orders by date from BigQuery"
            }),
            status=500,
            headers=DEFAULT_HEADERS
        )

# API endpoint to get sales summary from BigQuery
@https_fn.on_request(region="asia-east1")
@require_auth
def get_sales_summary_bq(req: https_fn.Request) -> https_fn.Response:
    """Get sales summary with aggregated data from BigQuery - defaults to today"""
    
    # Handle CORS for web requests
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)
    
    # Get parameters from query string - default to today
    today = datetime.now().strftime("%Y-%m-%d")
    from_date = req.args.get('from', today)  # Default to today
    to_date = req.args.get('to', today)      # Default to today
    store_id = req.args.get('storeId')       # Optional
    
    # Parse dates
    from_dt = parse_date_string(from_date)
    to_dt = parse_date_string(to_date)
    
    if not from_dt:
        return https_fn.Response(
            json.dumps({"error": "Invalid from date format. Use YYYYMMDD or YYYY-MM-DD"}),
            status=400,
            headers=DEFAULT_HEADERS
        )
    
    if not to_dt:
        return https_fn.Response(
            json.dumps({"error": "Invalid to date format. Use YYYYMMDD or YYYY-MM-DD"}),
            status=400,
            headers=DEFAULT_HEADERS
        )
    
    # Validate store access if storeId is provided
    if store_id:
        from auth_middleware import check_store_access, extract_user_permissions
        has_access, access_error = check_store_access(req.user, store_id)
        if not has_access:
            perms = extract_user_permissions(req.user)
            return https_fn.Response(
                json.dumps({
                    "success": False,
                    "error": "Access denied",
                    "message": access_error,
                    "requested_store": store_id,
                    "user_store": perms.get('storeId')
                }),
                status=403,
                headers=DEFAULT_HEADERS
            )
    
    try:
        client = get_bigquery_client()
        
        # Build summary query - get all orders with aggregated data
        query = f"""
        SELECT 
            orderId,
            storeId,
            companyId,
            DATE(createdAt) as order_date,
            createdAt,
            invoiceNumber,
            status,
            totalAmount,
            netAmount,
            grossAmount,
            vatAmount,
            vatExemptAmount,
            vatableSales,
            zeroRatedSales,
            discountAmount,
            assignedCashierName,
            assignedCashierEmail,
            customerInfo,
            payments
        FROM `{BIGQUERY_ORDERS_TABLE}`
        WHERE DATE(createdAt) BETWEEN @from_date AND @to_date
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("from_date", "DATE", from_dt.date()),
                bigquery.ScalarQueryParameter("to_date", "DATE", to_dt.date())
            ]
        )
        
        # Add store filter if provided
        if store_id:
            query += " AND storeId = @store_id"
            job_config.query_parameters.append(
                bigquery.ScalarQueryParameter("store_id", "STRING", store_id)
            )
        
        query += " ORDER BY createdAt DESC"
        
        print(f"🔍 BigQuery sales summary query: {query}")
        print(f"📋 Parameters: from_date={from_dt.date()}, to_date={to_dt.date()}, store_id={store_id}")
        
        # Execute query for detailed orders
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        
        # Convert results to list and calculate summary
        orders = []
        total_sales = 0
        total_orders = 0
        total_vat = 0
        total_discount = 0
        stores_summary = {}
        
        for row in results:
            order = dict(row)
            # Convert datetime objects to ISO strings for JSON serialization
            for key, value in order.items():
                if isinstance(value, datetime):
                    order[key] = value.isoformat()
            orders.append(order)
            
            # Calculate aggregates
            total_amount = float(order.get('totalAmount', 0))
            vat_amount = float(order.get('vatAmount', 0))
            discount_amount = float(order.get('discountAmount', 0))
            order_store_id = order.get('storeId', 'unknown')
            
            total_sales += total_amount
            total_orders += 1
            total_vat += vat_amount
            total_discount += discount_amount
            
            # Store-wise summary
            if order_store_id not in stores_summary:
                stores_summary[order_store_id] = {
                    'storeId': order_store_id,
                    'totalSales': 0,
                    'orderCount': 0,
                    'totalVat': 0,
                    'totalDiscount': 0
                }
            
            stores_summary[order_store_id]['totalSales'] += total_amount
            stores_summary[order_store_id]['orderCount'] += 1
            stores_summary[order_store_id]['totalVat'] += vat_amount
            stores_summary[order_store_id]['totalDiscount'] += discount_amount
        
        # Summary data
        summary = {
            'totalSales': round(total_sales, 2),
            'totalOrders': total_orders,
            'totalVat': round(total_vat, 2),
            'totalDiscount': round(total_discount, 2),
            'averageOrderValue': round(total_sales / total_orders, 2) if total_orders > 0 else 0,
            'storesSummary': list(stores_summary.values())
        }
        
        response_data = {
            "success": True,
            "dateRange": {
                "from": from_date,
                "to": to_date,
                "fromParsed": from_dt.date().isoformat(),
                "toParsed": to_dt.date().isoformat()
            },
            "filters": {
                "storeId": store_id
            },
            "summary": summary,
            "orders": orders,
            "count": len(orders)
        }
        
        return https_fn.Response(
            json.dumps(response_data),
            status=200,
            headers=DEFAULT_HEADERS
        )
        
    except Exception as e:
        print(f"❌ BigQuery sales summary query error: {str(e)}")
        return https_fn.Response(
            json.dumps({
                "success": False,
                "error": str(e),
                "message": "Failed to query sales summary from BigQuery"
            }),
            status=500,
            headers=DEFAULT_HEADERS
        )

# API endpoint to get order count statistics aggregated by date
@https_fn.on_request(region="asia-east1")
@require_auth
def get_orders_count_by_date_bq(req: https_fn.Request) -> https_fn.Response:
    """Get order count statistics aggregated by date (YYYYMMDD) based on updatedAt field"""
    
    # Handle CORS for web requests
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)
    
    # Get parameters from query string
    from_date = req.args.get('from')
    to_date = req.args.get('to')
    store_id = req.args.get('storeId')  # Optional
    
    # Validate required parameters
    if not from_date:
        return https_fn.Response(
            json.dumps({"error": "from parameter is required (format: YYYYMMDD)"}),
            status=400,
            headers=DEFAULT_HEADERS
        )
    
    if not to_date:
        return https_fn.Response(
            json.dumps({"error": "to parameter is required (format: YYYYMMDD)"}),
            status=400,
            headers=DEFAULT_HEADERS
        )
    
    # Parse dates (expect YYYYMMDD format)
    from_dt = parse_date_string(from_date)
    to_dt = parse_date_string(to_date)
    
    if not from_dt:
        return https_fn.Response(
            json.dumps({"error": "Invalid from date format. Use YYYYMMDD"}),
            status=400,
            headers=DEFAULT_HEADERS
        )
    
    if not to_dt:
        return https_fn.Response(
            json.dumps({"error": "Invalid to date format. Use YYYYMMDD"}),
            status=400,
            headers=DEFAULT_HEADERS
        )
    
    # Validate store access if storeId is provided
    if store_id:
        from auth_middleware import check_store_access, extract_user_permissions
        has_access, access_error = check_store_access(req.user, store_id)
        if not has_access:
            perms = extract_user_permissions(req.user)
            return https_fn.Response(
                json.dumps({
                    "success": False,
                    "error": "Access denied",
                    "message": access_error,
                    "requested_store": store_id,
                    "user_store": perms.get('storeId')
                }),
                status=403,
                headers=DEFAULT_HEADERS
            )
    
    try:
        client = get_bigquery_client()
        
        # Build query parameters list
        query_parameters = [
            bigquery.ScalarQueryParameter("from_date", "DATE", from_dt.date()),
            bigquery.ScalarQueryParameter("to_date", "DATE", to_dt.date())
        ]
        
        # Build aggregation query - count orders by date based on updatedAt
        query = f"""
        SELECT 
            FORMAT_DATE('%Y%m%d', DATE(updatedAt)) as date_yyyymmdd,
            DATE(updatedAt) as date,
            COUNT(*) as order_count
        FROM `{BIGQUERY_ORDERS_TABLE}`
        WHERE DATE(updatedAt) BETWEEN @from_date AND @to_date
        """
        
        # Add store filter if provided
        if store_id:
            query += " AND storeId = @store_id"
            query_parameters.append(
                bigquery.ScalarQueryParameter("store_id", "STRING", store_id)
            )
        
        query += """
        GROUP BY DATE(updatedAt)
        ORDER BY DATE(updatedAt) DESC
        """
        
        # Create job configuration with all parameters
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        
        print(f"🔍 BigQuery order count query: {query}")
        print(f"📋 Parameters: from_date={from_dt.date()}, to_date={to_dt.date()}, store_id={store_id}")
        
        # Execute query with timeout and error handling
        print(f"⏳ Starting BigQuery aggregation job...")
        query_job = client.query(query, job_config=job_config)
        
        # Wait for job completion with timeout
        try:
            results = query_job.result(timeout=30)  # 30 second timeout
            print(f"✅ BigQuery aggregation job completed, processing results...")
        except Exception as job_error:
            print(f"❌ BigQuery job failed or timed out: {job_error}")
            # Check if it's a timeout vs actual failure
            if "timeout" in str(job_error).lower():
                return https_fn.Response(
                    json.dumps({
                        "success": False,
                        "error": "Query timeout",
                        "message": "BigQuery aggregation query took too long to complete"
                    }),
                    status=408,
                    headers=DEFAULT_HEADERS
                )
            else:
                raise job_error
        
        # Process results
        daily_counts = []
        total_orders = 0
        row_count = 0
        
        try:
            for row in results:
                row_count += 1
                daily_count = {
                    "date": row.date_yyyymmdd,
                    "full_date": row.date.isoformat() if row.date else None,
                    "order_count": row.order_count
                }
                daily_counts.append(daily_count)
                total_orders += row.order_count
                
                print(f"📅 {row.date_yyyymmdd}: {row.order_count} orders")
                
                # Safety check for large result sets
                if row_count > 1000:  # Reasonable limit for daily aggregation
                    print(f"⚠️ Result set truncated at {row_count} days to prevent memory issues")
                    break
            
            print(f"📊 Successfully processed {len(daily_counts)} days with {total_orders} total orders")
        except Exception as processing_error:
            print(f"❌ Error processing aggregation results: {processing_error}")
            raise processing_error
        
        response_data = {
            "success": True,
            "total_days": len(daily_counts),
            "total_orders": total_orders,
            "filters": {
                "from_date": from_date,
                "to_date": to_date,
                "store_id": store_id
            },
            "daily_counts": daily_counts
        }
        
        return https_fn.Response(
            json.dumps(response_data),
            status=200,
            headers=DEFAULT_HEADERS
        )
        
    except Exception as e:
        print(f"❌ BigQuery order count aggregation error: {str(e)}")
        return https_fn.Response(
            json.dumps({
                "success": False,
                "error": str(e),
                "message": "Failed to query order count statistics from BigQuery"
            }),
            status=500,
            headers=DEFAULT_HEADERS
        )