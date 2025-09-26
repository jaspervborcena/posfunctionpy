from firebase_functions import https_fn
import requests
import json
from datetime import datetime, timedelta
from urllib.parse import quote

# Import configuration 
from config import SUPABASE_URL, get_supabase_headers, DEFAULT_HEADERS

# Import authentication middleware
from auth_middleware import require_auth, require_store_access, get_user_info

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

def validate_date_range(from_date_str, to_date_str):
    """
    Validate date range.
    
    Args:
        from_date_str: Start date in YYYYMMDD or YYYY-MM-DD format
        to_date_str: End date in YYYYMMDD or YYYY-MM-DD format
        
    Returns:
        tuple: (from_date_str, to_date_str, error_msg)
    """
    if not from_date_str or not to_date_str:
        return from_date_str, to_date_str, None
    
    # Parse dates using flexible format
    from_date = parse_date_string(from_date_str)
    to_date = parse_date_string(to_date_str)
    
    if not from_date or not to_date:
        return None, None, "Invalid date format. Use YYYYMMDD (e.g., 20250926) or YYYY-MM-DD (e.g., 2025-09-26)"
    
    # Check if from_date is after to_date
    if from_date > to_date:
        return None, None, "startDate cannot be later than endDate"
    
    # Return dates in YYYY-MM-DD format for consistency
    from_date_formatted = from_date.strftime("%Y-%m-%d")
    to_date_formatted = to_date.strftime("%Y-%m-%d")
    
    return from_date_formatted, to_date_formatted, None

# API endpoint to get orders by storeId
@https_fn.on_request(region="asia-east1")
@require_auth
@require_store_access
def get_orders_by_store(req: https_fn.Request) -> https_fn.Response:
    """Get all orders for a specific store ID"""
    
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
    from_date = req.args.get('from')  # Expected format: YYYYMMDD (20250926) or YYYY-MM-DD (2025-09-26)
    to_date = req.args.get('to')      # Expected format: YYYYMMDD (20250926) or YYYY-MM-DD (2025-09-26)
    
    if not store_id:
        return https_fn.Response(
            json.dumps({"error": "storeId parameter is required"}),
            status=400,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
    
    # Validate date range if provided
    validated_from, validated_to, date_error = validate_date_range(from_date, to_date)
    
    if date_error:
        return https_fn.Response(
            json.dumps({"error": date_error}),
            status=400,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
    
    headers = get_supabase_headers()
    
    try:
        # Use custom Supabase function for efficient querying
        if validated_from and validated_to:
            # Convert dates to YYYYMMDD format for the function
            from_date_formatted = datetime.strptime(validated_from, "%Y-%m-%d").strftime("%Y%m%d")
            to_date_formatted = datetime.strptime(validated_to, "%Y-%m-%d").strftime("%Y%m%d")
            
            # Call the custom Supabase function
            url = f"{SUPABASE_URL}/rest/v1/rpc/get_orders_by_store_and_date"
            payload = {
                "p_store_id": store_id,
                "p_from_date": from_date_formatted,
                "p_to_date": to_date_formatted
            }
            
            print(f"🔍 Calling custom function with store: {store_id}")
            print(f"📅 Date range: {validated_from} to {validated_to} (formatted: {from_date_formatted} to {to_date_formatted})")
            print(f"📦 Function payload: {payload}")
            print(f"📡 Request URL: {url}")
            
            response = requests.post(url, json=payload, headers=headers)
        else:
            # Fallback to direct table query if no date filters
            url = f"{SUPABASE_URL}/rest/v1/orders?store_id=eq.{store_id}&order=created_at.desc"
            
            print(f"🔍 Fetching orders for store: {store_id} (no date filter)")
            print(f"📡 Request URL: {url}")
            
            response = requests.get(url, headers=headers)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📄 Response body: {response.text}")
        
        if response.status_code == 200:
            orders = response.json()
            
            response_data = {
                "success": True,
                "store_id": store_id,
                "total_orders": len(orders),
                "filters_applied": {
                    "from": validated_from,
                    "to": validated_to
                },
                "orders": orders
            }
            
            return https_fn.Response(
                json.dumps(response_data, indent=2, default=str),
                status=200,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
        else:
            error_response = {
                "success": False,
                "error": "Failed to fetch orders",
                "status_code": response.status_code,
                "message": response.text
            }
            
            return https_fn.Response(
                json.dumps(error_response, indent=2),
                status=response.status_code,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
            
    except Exception as e:
        error_response = {
            "success": False,
            "error": "Server error",
            "message": str(e)
        }
        
        return https_fn.Response(
            json.dumps(error_response, indent=2),
            status=500,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )

# API endpoint to get order details by storeId and orderId
@https_fn.on_request(region="asia-east1")
@require_auth
@require_store_access
def get_order_details(req: https_fn.Request) -> https_fn.Response:
    """Get order details for a specific store and order"""
    
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
    from_date = req.args.get('from')  # Optional date filter: YYYYMMDD (20250926) or YYYY-MM-DD (2025-09-26)
    to_date = req.args.get('to')      # Optional date filter: YYYYMMDD (20250926) or YYYY-MM-DD (2025-09-26)
    
    if not store_id:
        return https_fn.Response(
            json.dumps({"error": "storeId parameter is required"}),
            status=400,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
    
    if not order_id:
        return https_fn.Response(
            json.dumps({"error": "orderId parameter is required"}),
            status=400,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
    
    # Validate date range if provided
    validated_from, validated_to, date_error = validate_date_range(from_date, to_date)
    
    if date_error:
        return https_fn.Response(
            json.dumps({"error": date_error}),
            status=400,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
    
    headers = get_supabase_headers()
    
    try:
        # Use custom SQL function if date filters are provided
        if validated_from and validated_to:
            # Convert dates to YYYYMMDD format for the SQL function
            from_date_formatted = datetime.strptime(validated_from, '%Y-%m-%d').strftime('%Y%m%d')
            to_date_formatted = datetime.strptime(validated_to, '%Y-%m-%d').strftime('%Y%m%d')
            
            # Use custom SQL function (now requires order_id parameter)
            url = f"{SUPABASE_URL}/rest/v1/rpc/get_order_details_by_store_and_date"
            payload = {
                "p_store_id": store_id,
                "p_from_date": from_date_formatted,
                "p_to_date": to_date_formatted,
                "p_order_id": order_id
            }
            
            print(f"🔍 Using custom SQL function for order details")
            print(f"📅 Date range: {validated_from} to {validated_to} (formatted: {from_date_formatted} to {to_date_formatted})")
            print(f"🏪 Store ID: {store_id}, Order ID: {order_id}")
            print(f"📦 Function payload: {payload}")
            print(f"📡 Request URL: {url}")
            
            response = requests.post(url, json=payload, headers=headers)
            
            print(f"📊 Response status: {response.status_code}")
            print(f"📄 Response body: {response.text}")
            
            if response.status_code == 200:
                order_details = response.json()
                
                # No need to filter by order_id anymore since it's handled in the SQL function
                
                # Calculate totals
                total_items = len(order_details)
                total_amount = sum(item.get('total', 0) for item in order_details)
                
                response_data = {
                    "success": True,
                    "store_id": store_id,
                    "order_id": order_id,
                    "total_items": total_items,
                    "total_amount": total_amount,
                    "filters_applied": {
                        "from": validated_from,
                        "to": validated_to
                    },
                    "order_details": order_details
                }
                
                return https_fn.Response(
                    json.dumps(response_data, indent=2, default=str),
                    status=200,
                    headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
                )
            else:
                error_response = {
                    "success": False,
                    "error": "Failed to fetch order details from custom function",
                    "status_code": response.status_code,
                    "message": response.text
                }
                
                return https_fn.Response(
                    json.dumps(error_response, indent=2),
                    status=response.status_code,
                    headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
                )
        else:
            # Fallback to direct table query when no date filters
            url = f"{SUPABASE_URL}/rest/v1/order_details?store_id=eq.{store_id}&order_id=eq.{order_id}&order=order_details_id.asc"
            
            print(f"🔍 Fetching order details for store: {store_id}, order: {order_id} (no date filter)")
            print(f"📡 Request URL: {url}")
            
            response = requests.get(url, headers=headers)
            
            print(f"📊 Response status: {response.status_code}")
            print(f"📄 Response body: {response.text}")
            
            if response.status_code == 200:
                order_details = response.json()
                
                # Calculate totals
                total_items = len(order_details)
                total_amount = sum(item.get('total', 0) for item in order_details)
                
                response_data = {
                    "success": True,
                    "store_id": store_id,
                    "order_id": order_id,
                    "total_items": total_items,
                    "total_amount": total_amount,
                    "order_details": order_details
                }
                
                return https_fn.Response(
                    json.dumps(response_data, indent=2, default=str),
                    status=200,
                    headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
                )
            else:
                error_response = {
                    "success": False,
                    "error": "Failed to fetch order details",
                    "status_code": response.status_code,
                    "message": response.text
                }
                
                return https_fn.Response(
                    json.dumps(error_response, indent=2),
                    status=response.status_code,
                    headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
                )
            
    except Exception as e:
        error_response = {
            "success": False,
            "error": "Server error",
            "message": str(e)
        }
        
        return https_fn.Response(
            json.dumps(error_response, indent=2),
            status=500,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
# API endpoint to get orders by date range
@https_fn.on_request(region="asia-east1")
@require_auth
def get_orders_by_date(req: https_fn.Request) -> https_fn.Response:
    """Get orders filtered by date range with optional store filter
    
    Query Parameters:
    - storeId (optional): Filter by specific store
    - from (required): Start date in YYYYMMDD (20250926) or YYYY-MM-DD (2025-09-26) format
    - to (required): End date in YYYYMMDD (20250926) or YYYY-MM-DD (2025-09-26) format
    
    Examples: 
    - /get_orders_by_date?from=20250926&to=20250927&storeId=store123
    - /get_orders_by_date?from=2025-09-26&to=2025-09-27&storeId=store123
    """
    
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
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
    
    if not to_date:
        return https_fn.Response(
            json.dumps({"error": "to parameter is required (format: YYYYMMDD or YYYY-MM-DD)"}),
            status=400,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
    
    # Validate date range
    validated_from, validated_to, date_error = validate_date_range(from_date, to_date)
    
    if date_error:
        return https_fn.Response(
            json.dumps({"error": date_error}),
            status=400,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
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
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
    
    headers = get_supabase_headers()
    
    try:
        # Convert dates to YYYYMMDD format for the function
        from_date_formatted = datetime.strptime(validated_from, "%Y-%m-%d").strftime("%Y%m%d")
        to_date_formatted = datetime.strptime(validated_to, "%Y-%m-%d").strftime("%Y%m%d")
        
        if store_id:
            # Use custom function with store filter
            url = f"{SUPABASE_URL}/rest/v1/rpc/get_orders_by_store_and_date"
            payload = {
                "p_store_id": store_id,
                "p_from_date": from_date_formatted,
                "p_to_date": to_date_formatted
            }
            
            print(f"🔍 Calling custom function with store: {store_id}")
            print(f"📅 Date range: {validated_from} to {validated_to} (formatted: {from_date_formatted} to {to_date_formatted})")
            print(f"📦 Function payload: {payload}")
            print(f"📡 Request URL: {url}")
            
            response = requests.post(url, json=payload, headers=headers)
        else:
            # Fallback to direct table query for all stores (no store-specific function available)
            from_datetime = datetime.strptime(validated_from, "%Y-%m-%d")
            to_datetime = datetime.strptime(validated_to, "%Y-%m-%d")
            from_iso = from_datetime.strftime("%Y-%m-%dT00:00:00+00:00")
            to_iso = to_datetime.strftime("%Y-%m-%dT23:59:59+00:00")
            
            query_filters = [
                f"created_at=gte.{quote(from_iso)}",
                f"created_at=lte.{quote(to_iso)}"
            ]
            filter_string = "&".join(query_filters)
            url = f"{SUPABASE_URL}/rest/v1/orders?{filter_string}&order=created_at.desc"
            
            print(f"🔍 Fetching orders by date range (all stores)")
            print(f"📅 Date range: {validated_from} to {validated_to}")
            print(f"📡 Request URL: {url}")
            
            response = requests.get(url, headers=headers)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📄 Response body: {response.text}")
        
        if response.status_code == 200:
            orders = response.json()
            
            # Calculate summary statistics
            total_amount = sum(order.get('total_amount', 0) for order in orders)
            
            response_data = {
                "success": True,
                "date_range": {
                    "from": validated_from,
                    "to": validated_to
                },
                "store_id": store_id,
                "total_orders": len(orders),
                "total_amount": total_amount,
                "orders": orders
            }
            
            return https_fn.Response(
                json.dumps(response_data, indent=2, default=str),
                status=200,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
        else:
            error_response = {
                "success": False,
                "error": "Failed to fetch orders",
                "status_code": response.status_code,
                "message": response.text
            }
            
            return https_fn.Response(
                json.dumps(error_response, indent=2),
                status=response.status_code,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
            
    except Exception as e:
        error_response = {
            "success": False,
            "error": "Server error",
            "message": str(e)
        }
        
        return https_fn.Response(
            json.dumps(error_response, indent=2),
            status=500,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )

