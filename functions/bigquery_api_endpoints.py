from firebase_functions import https_fn
import json
from datetime import datetime, timedelta

# Import configuration 
from config import get_bigquery_client, BIGQUERY_ORDERS_TABLE, BIGQUERY_ORDER_DETAILS_TABLE, DEFAULT_HEADERS

# Import authentication middleware
from auth_middleware import require_auth, require_store_access, get_user_info

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
    store_id = req.args.get('storeId')
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
        from auth_middleware import check_store_access
        has_access, access_error = check_store_access(req.user, store_id)
        if not has_access:
            return https_fn.Response(
                json.dumps({
                    "success": False,
                    "error": "Access denied",
                    "message": access_error,
                    "requested_store": store_id,
                    "user_store": req.user.get('permissions', {}).get('storeId')
                }),
                status=403,
                headers=DEFAULT_HEADERS
            )
    
    try:
        client = get_bigquery_client()
        
        # Build query
        query = f"""
        SELECT *
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
        
        print(f"🔍 BigQuery date range query: {query}")
        print(f"📋 Parameters: from_date={from_dt.date()}, to_date={to_dt.date()}, store_id={store_id}")
        
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
        from auth_middleware import check_store_access
        has_access, access_error = check_store_access(req.user, store_id)
        if not has_access:
            return https_fn.Response(
                json.dumps({
                    "success": False,
                    "error": "Access denied",
                    "message": access_error,
                    "requested_store": store_id,
                    "user_store": req.user.get('permissions', {}).get('storeId')
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