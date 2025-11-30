from firebase_functions import https_fn
import json
from datetime import datetime

# Import configuration 
from config import get_bigquery_client, DEFAULT_HEADERS, get_bigquery_project_id, get_bigquery_dataset_id

# Import authentication middleware
from auth_middleware import require_auth, require_store_access, get_user_info

try:
    from google.cloud import bigquery
    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    print("WARNING: BigQuery library not available. BigQuery functions will be disabled.")

# BigQuery table name for product inventory - dynamically constructed based on environment
def _get_product_inventory_table():
    """Get fully qualified BigQuery table name for product inventory"""
    return f"{get_bigquery_project_id()}.{get_bigquery_dataset_id()}.productInventory"

# The HTTP endpoint `insert_product_inventory_bq` was removed.
# In this project, inserting product inventory to BigQuery is handled
# by administrative tooling or other services. If you need to re-enable
# an HTTP endpoint for inserting product inventory, re-add the function
# below with proper authentication and validation.

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
        table_name = _get_product_inventory_table()
        
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
        FROM `{table_name}`
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