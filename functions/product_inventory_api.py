from firebase_functions import https_fn
import json
from datetime import datetime

# Import configuration 
from config import get_bigquery_client, DEFAULT_HEADERS

# Import authentication middleware
from auth_middleware import require_auth, require_store_access, get_user_info

try:
    from google.cloud import bigquery
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    print("WARNING: BigQuery library not available. BigQuery functions will be disabled.")

# BigQuery table name for product inventory
BIGQUERY_PRODUCT_INVENTORY_TABLE = "jasperpos-1dfd5.tovrika_pos.productInventory"

# API endpoint to insert product inventory to BigQuery
@https_fn.on_request(region="asia-east1")
@require_auth
@require_store_access
def insert_product_inventory_bq(req: https_fn.Request) -> https_fn.Response:
    """Insert product inventory record to BigQuery"""
    
    # Handle CORS for web requests
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)
    
    if req.method != 'POST':
        return https_fn.Response(
            json.dumps({"error": "Only POST method is allowed"}),
            status=405,
            headers=DEFAULT_HEADERS
        )
    
    try:
        # Get request body
        data = req.get_json()
        if not data:
            return https_fn.Response(
                json.dumps({"error": "Request body is required"}),
                status=400,
                headers=DEFAULT_HEADERS
            )
        
        # Validate required fields
        required_fields = ['batchId', 'companyId', 'storeId', 'productId', 'quantity', 'costPrice', 'unitPrice', 'unitType']
        for field in required_fields:
            if field not in data:
                return https_fn.Response(
                    json.dumps({"error": f"Required field '{field}' is missing"}),
                    status=400,
                    headers=DEFAULT_HEADERS
                )
        
        # Validate store access
        from auth_middleware import check_store_access
        has_access, access_error = check_store_access(req.user, data.get('storeId'))
        if not has_access:
            return https_fn.Response(
                json.dumps({
                    "success": False,
                    "error": "Access denied",
                    "message": access_error,
                    "requested_store": data.get('storeId'),
                    "user_store": req.user.get('permissions', {}).get('storeId')
                }),
                status=403,
                headers=DEFAULT_HEADERS
            )
        
        client = get_bigquery_client()
        
        # Prepare inventory record for BigQuery
        current_time = datetime.now().isoformat()
        inventory_record = {
            "batchId": str(data.get('batchId')),
            "companyId": str(data.get('companyId')),
            "costPrice": float(data.get('costPrice', 0)),
            "createdAt": current_time,
            "createdBy": str(data.get('createdBy', req.user.get('uid', ''))),
            "productId": str(data.get('productId')),
            "quantity": int(data.get('quantity', 0)),
            "receivedAt": {
                "seconds": int(data.get('receivedAt', {}).get('seconds', datetime.now().timestamp())),
                "nanoseconds": int(data.get('receivedAt', {}).get('nanoseconds', 0))
            },
            "status": str(data.get('status', 'active')),
            "storeId": str(data.get('storeId')),
            "uid": str(data.get('uid', req.user.get('uid', ''))),
            "unitPrice": float(data.get('unitPrice', 0)),
            "unitType": str(data.get('unitType', 'pieces')),
            "updatedAt": current_time,
            "updatedBy": str(data.get('updatedBy', req.user.get('uid', '')))
        }
        
        print(f"🔍 Inserting product inventory: {inventory_record}")
        
        # Insert into BigQuery
        table = client.get_table(BIGQUERY_PRODUCT_INVENTORY_TABLE)
        errors = client.insert_rows_json(table, [inventory_record])
        
        if errors:
            print(f"❌ BigQuery insert failed with errors: {errors}")
            return https_fn.Response(
                json.dumps({
                    "success": False,
                    "error": "Failed to insert product inventory",
                    "details": errors
                }),
                status=500,
                headers=DEFAULT_HEADERS
            )
        
        print(f"✅ Product inventory inserted successfully: {data.get('batchId')}")
        
        return https_fn.Response(
            json.dumps({
                "success": True,
                "message": "Product inventory inserted successfully",
                "batchId": data.get('batchId'),
                "productId": data.get('productId'),
                "storeId": data.get('storeId')
            }),
            status=200,
            headers=DEFAULT_HEADERS
        )
        
    except Exception as e:
        print(f"❌ Insert product inventory error: {str(e)}")
        return https_fn.Response(
            json.dumps({
                "success": False,
                "error": str(e),
                "message": "Failed to insert product inventory to BigQuery"
            }),
            status=500,
            headers=DEFAULT_HEADERS
        )

# API endpoint to get product inventory from BigQuery
@https_fn.on_request(region="asia-east1")
@require_auth
@require_store_access
def get_product_inventory_bq(req: https_fn.Request) -> https_fn.Response:
    """Get product inventory by storeId and optionally productId from BigQuery"""
    
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
    product_id = req.args.get('productId')  # Optional
    status_filter = req.args.get('status', 'active')  # Default to active
    
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
        SELECT 
            batchId,
            companyId,
            costPrice,
            createdAt,
            createdBy,
            productId,
            quantity,
            receivedAt,
            status,
            storeId,
            uid,
            unitPrice,
            unitType,
            updatedAt,
            updatedBy
        FROM `{BIGQUERY_PRODUCT_INVENTORY_TABLE}`
        WHERE storeId = @store_id
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("store_id", "STRING", store_id)
            ]
        )
        
        # Add product filter if provided
        if product_id:
            query += " AND productId = @product_id"
            job_config.query_parameters.append(
                bigquery.ScalarQueryParameter("product_id", "STRING", product_id)
            )
        
        # Add status filter
        if status_filter:
            query += " AND status = @status"
            job_config.query_parameters.append(
                bigquery.ScalarQueryParameter("status", "STRING", status_filter)
            )
        
        query += " ORDER BY createdAt DESC"
        
        print(f"🔍 BigQuery product inventory query: {query}")
        print(f"📋 Parameters: store_id={store_id}, product_id={product_id}, status={status_filter}")
        
        # Execute query
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        
        # Convert results to list
        inventory_items = []
        for row in results:
            item = dict(row)
            # Convert datetime objects to ISO strings for JSON serialization
            for key, value in item.items():
                if isinstance(value, datetime):
                    item[key] = value.isoformat()
            inventory_items.append(item)
        
        response_data = {
            "success": True,
            "count": len(inventory_items),
            "storeId": store_id,
            "productId": product_id,
            "status": status_filter,
            "inventory": inventory_items
        }
        
        return https_fn.Response(
            json.dumps(response_data),
            status=200,
            headers=DEFAULT_HEADERS
        )
        
    except Exception as e:
        print(f"❌ BigQuery product inventory query error: {str(e)}")
        return https_fn.Response(
            json.dumps({
                "success": False,
                "error": str(e),
                "message": "Failed to query product inventory from BigQuery"
            }),
            status=500,
            headers=DEFAULT_HEADERS
        )