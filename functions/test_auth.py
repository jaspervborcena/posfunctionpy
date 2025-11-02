from firebase_functions import https_fn
import json

# Import authentication middleware
from auth_middleware import require_auth, require_store_access, get_user_info, extract_user_permissions

# Test endpoint to verify authentication is working
@https_fn.on_request(region="asia-east1")
@require_auth
def test_auth_basic(req: https_fn.Request) -> https_fn.Response:
    """Test endpoint to verify authentication is working"""
    
    # Handle CORS for web requests
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)
    
    user = get_user_info(req)
    perms = extract_user_permissions(user)

    return https_fn.Response(
        json.dumps({
            "success": True,
            "message": "Authentication successful!",
            "user": {
                "uid": user.get('uid'),
                "display_name": user.get('displayName'),
                "email": user.get('email'),
                "status": user.get('status'),
                "permissions": user.get('permissions', {}),
                "company_id": perms.get('companyId'),
                "store_id": perms.get('storeId'),
                "role_id": perms.get('roleId')
            },
            "timestamp": req.headers.get('X-Request-Time', 'Not provided')
        }),
        status=200,
        headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
    )

# Test endpoint to verify store access authentication
@https_fn.on_request(region="asia-east1")
@require_auth
@require_store_access
def test_auth_store(req: https_fn.Request) -> https_fn.Response:
    """Test endpoint to verify store access authentication is working"""
    
    # Handle CORS for web requests
    if req.method == 'OPTIONS':
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Max-Age': '3600'
        }
        return https_fn.Response('', status=204, headers=headers)
    
    user = get_user_info(req)
    store_id = req.args.get('storeId') or req.args.get('store_id')
    perms = extract_user_permissions(user)

    return https_fn.Response(
        json.dumps({
            "success": True,
            "message": f"Store access authentication successful for store {store_id}!",
            "user": {
                "uid": user.get('uid'),
                "display_name": user.get('displayName'),
                "email": user.get('email'),
                "user_store_id": perms.get('storeId'),
                "requested_store_id": store_id,
                "role_id": perms.get('roleId')
            },
            "access_granted": True,
            "timestamp": req.headers.get('X-Request-Time', 'Not provided')
        }),
        status=200,
        headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
    )