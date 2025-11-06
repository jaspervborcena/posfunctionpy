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
    page_size = int(req.args.get('page_size', 20))
    page_number = int(req.args.get('page_number', 1))
    
    # Validate and enforce constraints
    if page_size > 100:
        page_size = 100
    if page_number <= 0:
        page_number = 1

    if not store_id:
        return https_fn.Response(
            json.dumps({"error": "storeId parameter is required"}),
            status=400,
            headers=DEFAULT_HEADERS
        )

    try:
        client = get_bigquery_client()

        # Use the exact query specified by user
        query = f"""
        SELECT *
        FROM `{BIGQUERY_PRODUCTS_TABLE}`
        WHERE storeId = @store_id
        ORDER BY updatedAt DESC
        LIMIT @page_size
        OFFSET (@page_number - 1) * @page_size
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("store_id", "STRING", store_id),
                bigquery.ScalarQueryParameter("page_size", "INT64", page_size),
                bigquery.ScalarQueryParameter("page_number", "INT64", page_number)
            ]
        )

        print(f"🔍 BigQuery products query: {query}")
        print(f"📋 Parameters: store_id={store_id}, page_size={page_size}, page_number={page_number}")

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
            "page_size": page_size,
            "page_number": page_number,
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


# API endpoint to get orders by storeId from BigQuery (paginated)
@https_fn.on_request(region="asia-east1")
@require_auth
def get_orders_bq(req: https_fn.Request) -> https_fn.Response:
    """Get orders for a specific store from BigQuery with pagination"""

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
    page_size = int(req.args.get('page_size', 20))
    page_number = int(req.args.get('page_number', 1))
    
    # Validate and enforce constraints
    if page_size > 100:
        page_size = 100
    if page_number <= 0:
        page_number = 1

    if not store_id:
        return https_fn.Response(
            json.dumps({"error": "storeId parameter is required"}),
            status=400,
            headers=DEFAULT_HEADERS
        )

    try:
        client = get_bigquery_client()

        # Use the exact query specified by user
        query = f"""
        SELECT *
        FROM `{BIGQUERY_ORDERS_TABLE}`
        WHERE storeId = @store_id
        ORDER BY updatedAt DESC
        LIMIT @page_size
        OFFSET (@page_number - 1) * @page_size
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("store_id", "STRING", store_id),
                bigquery.ScalarQueryParameter("page_size", "INT64", page_size),
                bigquery.ScalarQueryParameter("page_number", "INT64", page_number)
            ]
        )

        print(f"🔍 BigQuery orders query: {query}")
        print(f"📋 Parameters: store_id={store_id}, page_size={page_size}, page_number={page_number}")

        query_job = client.query(query, job_config=job_config)
        results = query_job.result()

        orders = []
        for row in results:
            order = dict(row)
            # Convert timestamps to ISO strings
            for key, value in order.items():
                if isinstance(value, datetime):
                    order[key] = value.isoformat()
            orders.append(order)

        response_data = {
            "success": True,
            "count": len(orders),
            "store_id": store_id,
            "page_size": page_size,
            "page_number": page_number,
            "orders": orders
        }

        return https_fn.Response(
            json.dumps(response_data),
            status=200,
            headers=DEFAULT_HEADERS
        )

    except Exception as e:
        print(f"❌ BigQuery orders query error: {str(e)}")
        return https_fn.Response(
            json.dumps({
                "success": False,
                "error": str(e),
                "message": "Failed to query orders from BigQuery"
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
    
    # Get parameters from query string
    date_param = req.args.get('date')  # Optional, format: YYYYMMDD or YYYY-MM-DD
    store_id = req.args.get('storeId')  # Optional
    
    # Default to today if no date provided
    if date_param:
        target_date = parse_date_string(date_param)
        if not target_date:
            return https_fn.Response(
                json.dumps({"error": "Invalid date format. Use YYYYMMDD or YYYY-MM-DD"}),
                status=400,
                headers=DEFAULT_HEADERS
            )
    else:
        target_date = datetime.now()
    
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
            bigquery.ScalarQueryParameter("target_date", "DATE", target_date.date())
        ]
        
        # Build aggregated sales summary query
        query = f"""
        SELECT 
            COUNT(*) as total_orders
        FROM `{BIGQUERY_ORDERS_TABLE}`
        WHERE DATE(createdAt) = @target_date
        """
        
        # Add store filter if provided
        if store_id:
            query += " AND storeId = @store_id"
            query_parameters.append(
                bigquery.ScalarQueryParameter("store_id", "STRING", store_id)
            )
        
        # Create job configuration with all parameters
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        
        print(f"🔍 BigQuery sales summary query: {query}")
        print(f"📋 Parameters: target_date={target_date.date()}, store_id={store_id}")
        
        # Execute query
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        
        # Process results
        summary = {}
        for row in results:
            summary = {
                "date": target_date.date().isoformat(),
                "store_id": store_id,
                "total_orders": row.total_orders or 0
            }
            break  # Should only be one row
        
        response_data = {
            "success": True,
            "summary": summary
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
            FORMAT_DATE('%Y%m%d', DATE(updatedAt)) as Date,
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

# API endpoint to get order count statistics aggregated by date with amounts
@https_fn.on_request(region="asia-east1")
@require_auth
def get_orders_count_by_status_bq(req: https_fn.Request) -> https_fn.Response:
    """Get order count statistics aggregated by updatedAt date with amounts and filtering"""
    
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
            FORMAT_DATE('%Y%m%d', DATE(updatedAt)) as Date,
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
        
        print(f"🔍 BigQuery order count by date query: {query}")
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
                    "date": row.Date,
                    "order_count": row.order_count
                }
                daily_counts.append(daily_count)
                total_orders += row.order_count
                
                print(f"📅 {row.Date}: {row.order_count} orders")
                
                # Safety check for large result sets
                if row_count > 1000:  # Reasonable limit for daily aggregation
                    print(f"⚠️ Result set truncated at {row_count} rows to prevent memory issues")
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