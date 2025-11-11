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

# NOTE: The Firestore-backed `insert_product` endpoint has been removed.
# If you need to re-enable product insertion via Cloud Functions, re-add
# an endpoint here or add an alternative integration. For now, writes
# should be performed by your backend tools or admin interfaces.


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