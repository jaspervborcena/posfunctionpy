from firebase_functions import https_fn
from firebase_admin import auth, firestore
import json
from functools import wraps

def verify_user_auth(req):
    """
    Verify Firebase ID token and validate user in Firestore users collection
    
    Returns:
        tuple: (user_data, error_message)
    """
    try:
        # Extract token from Authorization header
        auth_header = req.headers.get('Authorization')
        if not auth_header:
            return None, "Missing Authorization header"
        
        if not auth_header.startswith('Bearer '):
            return None, "Invalid Authorization header format. Use 'Bearer <token>'"
        
        id_token = auth_header.split('Bearer ')[1]
        
        # Verify the Firebase ID token
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        email = decoded_token.get('email')
        
        print(f"🔐 Token verified for UID: {uid}, Email: {email}")
        
        # Check user in Firestore users collection
        db = firestore.client()
        users_ref = db.collection('users')
        user_query = users_ref.where('uid', '==', uid).limit(1)
        user_docs = user_query.get()
        
        if not user_docs:
            print(f"❌ User not found in users collection for UID: {uid}")
            return None, f"User not found in system for UID: {uid}"
        
        user_doc = user_docs[0]
        user_data = user_doc.to_dict()
        user_data['doc_id'] = user_doc.id  # Add document ID for reference
        
        # Check if user is active
        if user_data.get('status') != 'active':
            print(f"❌ User account is not active. Status: {user_data.get('status')}")
            return None, f"User account is inactive. Status: {user_data.get('status')}"
        
        # Validate email match (optional additional security)
        if user_data.get('email') != email:
            print(f"⚠️ Email mismatch - Token: {email}, DB: {user_data.get('email')}")
            # Log but don't fail - email might be updated in Firebase Auth first
        
        print(f"✅ User authenticated successfully: {user_data.get('displayName')} ({user_data.get('email')})")
        print(f"🏢 Company: {user_data.get('permissions', {}).get('companyId', 'N/A')}")
        print(f"🏪 Store: {user_data.get('permissions', {}).get('storeId', 'N/A')}")
        print(f"👤 Role: {user_data.get('permissions', {}).get('roleId', 'N/A')}")
        
        return user_data, None
        
    except auth.InvalidIdTokenError:
        return None, "Invalid or expired ID token"
    except auth.ExpiredIdTokenError:
        return None, "ID token has expired"
    except Exception as e:
        print(f"❌ Authentication error: {str(e)}")
        return None, f"Authentication failed: {str(e)}"

def check_store_access(user_data, requested_store_id):
    """
    Check if user has access to the requested store
    
    Args:
        user_data: User document data from Firestore
        requested_store_id: Store ID being requested in the API
    
    Returns:
        tuple: (has_access: bool, error_message: str)
    """
    try:
        # Get user's store access from permissions field
        permissions = user_data.get('permissions', {})
        user_store_id = permissions.get('storeId')
        
        # Check if user has access to the requested store
        if user_store_id == requested_store_id:
            print(f"✅ Store access granted: User has access to store {requested_store_id}")
            return True, None
        
        # Check if user is a creator role (might have access to all stores in company)
        user_role = permissions.get('roleId')
        if user_role == 'creator':
            print(f"✅ Store access granted: User is creator role")
            return True, None
        
        print(f"❌ Store access denied: User store {user_store_id} != requested store {requested_store_id}")
        return False, f"Access denied: You don't have permission to access store {requested_store_id}"
        
    except Exception as e:
        print(f"❌ Store access check error: {str(e)}")
        return False, f"Store access validation failed: {str(e)}"

def require_auth(func):
    """
    Decorator to require Firebase authentication for API endpoints
    Adds user data to request object as req.user
    """
    @wraps(func)
    def wrapper(req):
        # Skip auth for OPTIONS requests (CORS preflight)
        if req.method == 'OPTIONS':
            return func(req)
        
        user_data, error = verify_user_auth(req)
        if error:
            return https_fn.Response(
                json.dumps({
                    "success": False,
                    "error": "Authentication required",
                    "message": error
                }),
                status=401,
                headers={
                    "Content-Type": "application/json", 
                    "Access-Control-Allow-Origin": "*",
                    "WWW-Authenticate": "Bearer"
                }
            )
        
        # Add user data to request object
        req.user = user_data
        return func(req)
    
    return wrapper

def require_store_access(func):
    """
    Decorator to require store access validation
    Must be used with @require_auth decorator
    Validates that user has access to the storeId parameter
    """
    @wraps(func)
    def wrapper(req):
        # Skip for OPTIONS requests
        if req.method == 'OPTIONS':
            return func(req)
        
        # Get storeId from query params or JSON body
        store_id = None
        
        # Try query parameters first
        if hasattr(req, 'args'):
            store_id = req.args.get('storeId') or req.args.get('store_id')
        
        # Try JSON body if not in query params
        if not store_id and req.method in ['POST', 'PUT', 'PATCH']:
            try:
                data = req.get_json()
                if data:
                    store_id = data.get('storeId') or data.get('store_id')
            except:
                pass
        
        if not store_id:
            return https_fn.Response(
                json.dumps({
                    "success": False,
                    "error": "Missing store ID",
                    "message": "storeId parameter is required"
                }),
                status=400,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
        
        # Check store access (req.user should be set by @require_auth)
        if not hasattr(req, 'user'):
            return https_fn.Response(
                json.dumps({
                    "success": False,
                    "error": "Authentication error",
                    "message": "User data not found. Ensure @require_auth is used before @require_store_access"
                }),
                status=500,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
        
        has_access, error = check_store_access(req.user, store_id)
        if not has_access:
            return https_fn.Response(
                json.dumps({
                    "success": False,
                    "error": "Access denied",
                    "message": error,
                    "requested_store": store_id,
                    "user_store": req.user.get('permissions', {}).get('storeId')
                }),
                status=403,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
            )
        
        return func(req)
    
    return wrapper

def get_user_info(req):
    """
    Helper function to get user info from authenticated request
    """
    if hasattr(req, 'user'):
        return req.user
    return None