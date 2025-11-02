"""
Products API endpoints for Firebase Firestore
Handles CRUD operations for products collection
"""

from firebase_functions import https_fn
from firebase_admin import firestore
import json
from datetime import datetime
from auth_middleware import require_auth
from typing import Dict, Any

@https_fn.on_request(cors=True, region="asia-east1")
@require_auth
def insert_product(req: https_fn.Request) -> https_fn.Response:
    """
    Insert a new product into Firestore products collection
    Requires Firebase authentication and store access validation
    
    Expected payload:
    {
        "barcodeId": "string (optional)",
        "category": "string (required)",
        "companyId": "string (required)", 
        "description": "string (optional)",
        "discountType": "percentage|fixed (optional, default: percentage)",
        "discountValue": number (optional, default: 0),
        "hasDiscount": boolean (optional, default: false),
        "imageUrl": "string (optional)",
        "isFavorite": boolean (optional, default: false),
        "isVatApplicable": boolean (optional, default: false),
        "productCode": "string (required)",
        "productName": "string (required)",
        "sellingPrice": number (required)",
        "skuId": "string (required)",
        "status": "active|inactive (optional, default: active)",
        "storeId": "string (required)",
        "totalStock": number (optional, default: 0)",
        "unitType": "pieces|kg|liters|etc (optional, default: pieces)"
    }
    """
    
    if req.method != 'POST':
        return https_fn.Response(
            json.dumps({"error": "Method not allowed"}), 
            status=405, 
            headers={"Content-Type": "application/json"}
        )
    
    try:
        # Initialize Firestore client
        db = firestore.client()
        
        # Parse request body
        try:
            data = req.get_json()
            if not data:
                return https_fn.Response(
                    json.dumps({"error": "Request body is required"}),
                    status=400,
                    headers={"Content-Type": "application/json"}
                )
        except Exception as e:
            return https_fn.Response(
                json.dumps({"error": "Invalid JSON format"}),
                status=400,
                headers={"Content-Type": "application/json"}
            )
        
        # Validate required fields
        required_fields = ['category', 'companyId', 'productCode', 'productName', 'sellingPrice', 'skuId', 'storeId']
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        
        if missing_fields:
            return https_fn.Response(
                json.dumps({"error": f"Missing required fields: {', '.join(missing_fields)}"}),
                status=400,
                headers={"Content-Type": "application/json"}
            )
        
        # Validate store access
        store_id = data['storeId']
        user_info = getattr(req, 'user_info', {})
        user_stores = user_info.get('stores', [])
        
        if store_id not in user_stores:
            return https_fn.Response(
                json.dumps({"error": "Access denied to this store"}),
                status=403,
                headers={"Content-Type": "application/json"}
            )
        
        # Get current timestamp
        current_time = firestore.SERVER_TIMESTAMP
        user_id = user_info.get('uid')
        
        # Prepare product document with defaults
        product_data = {
            'barcodeId': data.get('barcodeId'),
            'category': data['category'],
            'companyId': data['companyId'],
            'createdAt': current_time,
            'createdBy': user_id,
            'description': data.get('description'),
            'discountType': data.get('discountType', 'percentage'),
            'discountValue': data.get('discountValue', 0),
            'hasDiscount': data.get('hasDiscount', False),
            'imageUrl': data.get('imageUrl'),
            'isFavorite': data.get('isFavorite', False),
            'isVatApplicable': data.get('isVatApplicable', False),
            'productCode': data['productCode'],
            'productName': data['productName'],
            'sellingPrice': data['sellingPrice'],
            'skuId': data['skuId'],
            'status': data.get('status', 'active'),
            'storeId': data['storeId'],
            'totalStock': data.get('totalStock', 0),
            'uid': user_id,
            'unitType': data.get('unitType', 'pieces'),
            'updatedAt': current_time,
            'updatedBy': user_id
        }
        
        # Insert product into Firestore
        doc_ref = db.collection('products').document()
        doc_ref.set(product_data)
        
        # Get the inserted document for response
        inserted_doc = doc_ref.get()
        if inserted_doc.exists:
            response_data = inserted_doc.to_dict()
            response_data['id'] = inserted_doc.id
            
            # Convert Firestore timestamps to strings for JSON response
            if 'createdAt' in response_data and response_data['createdAt']:
                response_data['createdAt'] = response_data['createdAt'].isoformat()
            if 'updatedAt' in response_data and response_data['updatedAt']:
                response_data['updatedAt'] = response_data['updatedAt'].isoformat()
        else:
            response_data = {"id": doc_ref.id, "message": "Product created successfully"}
        
        return https_fn.Response(
            json.dumps({
                "success": True,
                "message": "Product inserted successfully",
                "data": response_data
            }),
            status=201,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        print(f"Error inserting product: {str(e)}")
        return https_fn.Response(
            json.dumps({"error": f"Failed to insert product: {str(e)}"}),
            status=500,
            headers={"Content-Type": "application/json"}
        )


# NOTE: Firestore-backed `get_products` endpoint removed. Use BigQuery-backed
# `get_products_bq` in `bigquery_api_endpoints.py` for product reads. We intentionally
# do not register a Firestore GET endpoint here to ensure all GET traffic goes
# through the BigQuery API for consistency and performance.

# NOTE: The Firestore-backed `get_products` endpoint has been deprecated in this
# project in favor of the BigQuery-backed `get_products_bq` API which provides
# analytics-ready queries and better performance for reads. If you intentionally
# want to re-enable Firestore reads, re-add a function here. For now, use
# `get_products_bq` defined in `bigquery_api_endpoints.py`.


@https_fn.on_request(cors=True, region="asia-east1")
@require_auth
def update_product(req: https_fn.Request) -> https_fn.Response:
    """
    Update an existing product in Firestore
    Requires Firebase authentication and store access validation
    
    URL parameter: productId (document ID)
    
    Expected payload: Any subset of product fields to update
    """
    
    if req.method != 'PUT' and req.method != 'PATCH':
        return https_fn.Response(
            json.dumps({"error": "Method not allowed"}), 
            status=405, 
            headers={"Content-Type": "application/json"}
        )
    
    try:
        # Initialize Firestore client
        db = firestore.client()
        
        # Get product ID from URL path
        product_id = req.args.get('productId')
        if not product_id:
            return https_fn.Response(
                json.dumps({"error": "productId parameter is required"}),
                status=400,
                headers={"Content-Type": "application/json"}
            )
        
        # Parse request body
        try:
            data = req.get_json()
            if not data:
                return https_fn.Response(
                    json.dumps({"error": "Request body is required"}),
                    status=400,
                    headers={"Content-Type": "application/json"}
                )
        except Exception as e:
            return https_fn.Response(
                json.dumps({"error": "Invalid JSON format"}),
                status=400,
                headers={"Content-Type": "application/json"}
            )
        
        # Get existing product to validate store access
        doc_ref = db.collection('products').document(product_id)
        existing_doc = doc_ref.get()
        
        if not existing_doc.exists:
            return https_fn.Response(
                json.dumps({"error": "Product not found"}),
                status=404,
                headers={"Content-Type": "application/json"}
            )
        
        existing_data = existing_doc.to_dict()
        store_id = existing_data.get('storeId')
        
        # Validate store access
        user_info = getattr(req, 'user_info', {})
        user_stores = user_info.get('stores', [])
        
        if store_id not in user_stores:
            return https_fn.Response(
                json.dumps({"error": "Access denied to this store"}),
                status=403,
                headers={"Content-Type": "application/json"}
            )
        
        # Prepare update data
        update_data = {}
        updatable_fields = [
            'barcodeId', 'category', 'description', 'discountType', 'discountValue',
            'hasDiscount', 'imageUrl', 'isFavorite', 'isVatApplicable', 'productCode',
            'productName', 'sellingPrice', 'skuId', 'status', 'totalStock', 'unitType'
        ]
        
        for field in updatable_fields:
            if field in data:
                update_data[field] = data[field]
        
        # Add update metadata
        update_data['updatedAt'] = firestore.SERVER_TIMESTAMP
        update_data['updatedBy'] = user_info.get('uid')
        
        # Update the document
        doc_ref.update(update_data)
        
        # Get updated document for response
        updated_doc = doc_ref.get()
        response_data = updated_doc.to_dict()
        response_data['id'] = updated_doc.id
        
        # Convert timestamps for JSON response
        if 'createdAt' in response_data and response_data['createdAt']:
            try:
                response_data['createdAt'] = response_data['createdAt'].isoformat()
            except:
                response_data['createdAt'] = str(response_data['createdAt'])
        
        if 'updatedAt' in response_data and response_data['updatedAt']:
            try:
                response_data['updatedAt'] = response_data['updatedAt'].isoformat()
            except:
                response_data['updatedAt'] = str(response_data['updatedAt'])
        
        return https_fn.Response(
            json.dumps({
                "success": True,
                "message": "Product updated successfully",
                "data": response_data
            }),
            status=200,
            headers={"Content-Type": "application/json"}
        )
        
    except Exception as e:
        print(f"Error updating product: {str(e)}")
        return https_fn.Response(
            json.dumps({"error": f"Failed to update product: {str(e)}"}),
            status=500,
            headers={"Content-Type": "application/json"}
        )