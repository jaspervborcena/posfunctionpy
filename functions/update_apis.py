from firebase_functions import https_fn
import requests
import json

# Import configuration 
from config import SUPABASE_URL, get_supabase_headers

# Import authentication middleware
from auth_middleware import require_auth, require_store_access, get_user_info

# API endpoint to update an order
@https_fn.on_request(region="asia-east1")
@require_auth
@require_store_access
def update_order(req: https_fn.Request) -> https_fn.Response:
    """Update an existing order in Supabase using stored procedure
    
    Method: PUT/PATCH
    Content-Type: application/json
    
    Required fields:
    - order_id: Order ID to update
    - store_id: Store ID for validation
    
    Optional fields:
    - invoice_number: Updated invoice number
    - total_amount: Updated total amount
    - gross_amount: Updated gross amount  
    - net_amount: Updated net amount
    - status: Updated order status
    """
    
    # Handle CORS for web requests
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'PUT, PATCH, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)
    
    # Only allow PUT and PATCH methods
    if req.method not in ['PUT', 'PATCH']:
        return https_fn.Response(
            json.dumps({"error": "Method not allowed. Use PUT or PATCH."}),
            status=405,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
    
    try:
        # Parse JSON body
        if not req.get_json():
            return https_fn.Response(
                json.dumps({"error": "Request body must be JSON"}),
                status=400,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
        
        data = req.get_json()
        
        # Validate required fields
        order_id = data.get('order_id')
        store_id = data.get('store_id')
        
        if not order_id:
            return https_fn.Response(
                json.dumps({"error": "order_id is required"}),
                status=400,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
        
        if not store_id:
            return https_fn.Response(
                json.dumps({"error": "store_id is required"}),
                status=400,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
        
        # Prepare parameters for stored procedure
        payload = {
            "p_order_id": order_id,
            "p_store_id": store_id,
            "p_invoice_number": data.get('invoice_number'),
            "p_total_amount": data.get('total_amount'),
            "p_gross_amount": data.get('gross_amount'),
            "p_net_amount": data.get('net_amount'),
            "p_status": data.get('status')
        }
        
        # Remove None values to use defaults
        payload = {k: v for k, v in payload.items() if v is not None}
        
        headers = get_supabase_headers()
        
        # Call the update_order stored procedure
        url = f"{SUPABASE_URL}/rest/v1/rpc/update_order"
        
        print(f"🔄 Updating order: {order_id} for store: {store_id}")
        print(f"📦 Update payload: {payload}")
        print(f"📡 Request URL: {url}")
        
        response = requests.post(url, json=payload, headers=headers)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📄 Response body: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Check if update was successful (stored procedure returns boolean)
            if result is True:
                response_data = {
                    "success": True,
                    "message": "Order updated successfully",
                    "order_id": order_id,
                    "store_id": store_id,
                    "updated_fields": [k.replace('p_', '') for k in payload.keys() if k.startswith('p_') and k not in ['p_order_id', 'p_store_id']]
                }
                
                return https_fn.Response(
                    json.dumps(response_data, indent=2),
                    status=200,
                    headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
                )
            else:
                return https_fn.Response(
                    json.dumps({
                        "success": False,
                        "error": "Order not found or update failed",
                        "order_id": order_id,
                        "store_id": store_id
                    }),
                    status=404,
                    headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
                )
        else:
            error_response = {
                "success": False,
                "error": "Failed to update order",
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

# API endpoint to update order details
@https_fn.on_request(region="asia-east1")
@require_auth
@require_store_access
def update_order_details(req: https_fn.Request) -> https_fn.Response:
    """Update existing order details in Supabase using stored procedure
    
    Method: PUT/PATCH
    Content-Type: application/json
    
    Required fields:
    - order_details_id: Order details ID to update
    - order_id: Order ID for validation
    - store_id: Store ID for validation
    
    Optional fields:
    - product_id: Updated product ID
    - product_name: Updated product name
    - quantity: Updated quantity
    - price: Updated price
    - discount: Updated discount amount
    - vat: Updated VAT amount
    - is_vat_exempt: Updated VAT exemption status
    - total: Updated total amount
    """
    
    # Handle CORS for web requests
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'PUT, PATCH, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)
    
    # Only allow PUT and PATCH methods
    if req.method not in ['PUT', 'PATCH']:
        return https_fn.Response(
            json.dumps({"error": "Method not allowed. Use PUT or PATCH."}),
            status=405,
            headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
        )
    
    try:
        # Parse JSON body
        if not req.get_json():
            return https_fn.Response(
                json.dumps({"error": "Request body must be JSON"}),
                status=400,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
        
        data = req.get_json()
        
        # Validate required fields
        order_details_id = data.get('order_details_id')
        order_id = data.get('order_id')
        store_id = data.get('store_id')
        
        if not order_details_id:
            return https_fn.Response(
                json.dumps({"error": "order_details_id is required"}),
                status=400,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
        
        if not order_id:
            return https_fn.Response(
                json.dumps({"error": "order_id is required"}),
                status=400,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
        
        if not store_id:
            return https_fn.Response(
                json.dumps({"error": "store_id is required"}),
                status=400,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
        
        # Prepare parameters for stored procedure
        payload = {
            "p_order_details_id": order_details_id,
            "p_order_id": order_id,
            "p_store_id": store_id,
            "p_product_id": data.get('product_id'),
            "p_product_name": data.get('product_name'),
            "p_quantity": data.get('quantity'),
            "p_price": data.get('price'),
            "p_discount": data.get('discount'),
            "p_vat": data.get('vat'),
            "p_is_vat_exempt": data.get('is_vat_exempt'),
            "p_total": data.get('total')
        }
        
        # Remove None values to use defaults
        payload = {k: v for k, v in payload.items() if v is not None}
        
        headers = get_supabase_headers()
        
        # Call the update_order_details stored procedure
        url = f"{SUPABASE_URL}/rest/v1/rpc/update_order_details"
        
        print(f"🔄 Updating order details: {order_details_id} for order: {order_id}")
        print(f"📦 Update payload: {payload}")
        print(f"📡 Request URL: {url}")
        
        response = requests.post(url, json=payload, headers=headers)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📄 Response body: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Check if update was successful (stored procedure returns boolean)
            if result is True:
                response_data = {
                    "success": True,
                    "message": "Order details updated successfully",
                    "order_details_id": order_details_id,
                    "order_id": order_id,
                    "store_id": store_id,
                    "updated_fields": [k.replace('p_', '') for k in payload.keys() if k.startswith('p_') and k not in ['p_order_details_id', 'p_order_id', 'p_store_id']]
                }
                
                return https_fn.Response(
                    json.dumps(response_data, indent=2),
                    status=200,
                    headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
                )
            else:
                return https_fn.Response(
                    json.dumps({
                        "success": False,
                        "error": "Order details not found or update failed",
                        "order_details_id": order_details_id,
                        "order_id": order_id,
                        "store_id": store_id
                    }),
                    status=404,
                    headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
                )
        else:
            error_response = {
                "success": False,
                "error": "Failed to update order details",
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