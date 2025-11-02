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

        # Try direct document lookup by UID first (common pattern: users/{uid})
        try:
            user_doc_ref = db.collection('users').document(uid)
            user_snapshot = user_doc_ref.get()
            if user_snapshot.exists:
                user_data = user_snapshot.to_dict()
                user_data['doc_id'] = user_snapshot.id
                print(f"✅ User document found by doc ID for UID: {uid} (doc: {user_snapshot.id})")
            else:
                # Fallback: some projects store uid inside document fields instead of as doc ID
                users_ref = db.collection('users')
                user_query = users_ref.where('uid', '==', uid).limit(1)
                user_docs = user_query.get()
                if not user_docs:
                    print(f"❌ User not found in users collection for UID: {uid}")
                    return None, f"User not found in system for UID: {uid}"
                user_doc = user_docs[0]
                user_data = user_doc.to_dict()
                user_data['doc_id'] = user_doc.id  # Add document ID for reference
                print(f"✅ User document found by query for UID: {uid} (doc: {user_doc.id})")
        except Exception as e:
            print(f"❌ Firestore user lookup error for UID {uid}: {e}")
            return None, f"User lookup failed: {e}"
        
        # Check if user is active
        if user_data.get('status') != 'active':
            print(f"❌ User account is not active. Status: {user_data.get('status')}")
            return None, f"User account is inactive. Status: {user_data.get('status')}"
        
        # Validate email match (optional additional security)
        if user_data.get('email') != email:
            print(f"⚠️ Email mismatch - Token: {email}, DB: {user_data.get('email')}")
            # Log but don't fail - email might be updated in Firebase Auth first
        
        print(f"✅ User authenticated successfully: {user_data.get('displayName')} ({user_data.get('email')})")
        # Be defensive: permissions may be stored as dict, list, or other shapes.
        perms = user_data.get('permissions')
        try:
            if isinstance(perms, dict):
                company_id = perms.get('companyId', 'N/A')
                store_id = perms.get('storeId', 'N/A')
                role_id = perms.get('roleId', 'N/A')
            elif isinstance(perms, list):
                # Try to find first dict element with expected keys
                company_id = 'N/A'
                store_id = 'N/A'
                role_id = 'N/A'
                for p in perms:
                    if isinstance(p, dict):
                        if 'companyId' in p and company_id == 'N/A':
                            company_id = p.get('companyId') or 'N/A'
                        if 'storeId' in p and store_id == 'N/A':
                            store_id = p.get('storeId') or 'N/A'
                        if 'roleId' in p and role_id == 'N/A':
                            role_id = p.get('roleId') or 'N/A'
                # If list contains plain strings, check for storeId match later in access check
            else:
                # Unknown shape (None, string, etc.) - show raw value
                company_id = getattr(perms, '__repr__', lambda: str(perms))()
                store_id = getattr(perms, '__repr__', lambda: str(perms))()
                role_id = getattr(perms, '__repr__', lambda: str(perms))()
        except Exception as ex:
            print(f"⚠️ Warning while parsing permissions for logging: {ex}")
            company_id = 'N/A'
            store_id = 'N/A'
            role_id = 'N/A'

        print(f"🏢 Company: {company_id}")
        print(f"🏪 Store: {store_id}")
        print(f"👤 Role: {role_id}")
        
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
        # Get user's store access from permissions field and normalize
        permissions = user_data.get('permissions')

        # Default denial values
        user_store_id = None
        user_role = None

        # Handle dict-shaped permissions
        if isinstance(permissions, dict):
            user_store_id = permissions.get('storeId')
            user_role = permissions.get('roleId')

        # If permissions is a list, try to extract a dict-like entry or raw store id
        elif isinstance(permissions, list):
            # Look for first dict with storeId or roleId
            for p in permissions:
                if isinstance(p, dict):
                    if user_store_id is None and p.get('storeId'):
                        user_store_id = p.get('storeId')
                    if user_role is None and p.get('roleId'):
                        user_role = p.get('roleId')
            # If list contains simple strings, treat them as allowed store IDs
            if user_store_id is None:
                for p in permissions:
                    if isinstance(p, str) and p == requested_store_id:
                        user_store_id = requested_store_id
                        break

        else:
            # Unknown shape (None, string, etc.) - attempt to treat string as storeId
            if isinstance(permissions, str):
                user_store_id = permissions

        # Check if user has access to the requested store
        if user_store_id == requested_store_id:
            print(f"✅ Store access granted: User has access to store {requested_store_id}")
            return True, None

        # Check if user is a creator role (might have access to all stores in company)
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
        
        # If store_id not provided in query/body, try to derive from authenticated user permissions
        if not store_id:
            # req.user should be set by @require_auth (decorator order matters)
            if hasattr(req, 'user'):
                perms = req.user.get('permissions')
                derived_store = None
                try:
                    if isinstance(perms, dict):
                        derived_store = perms.get('storeId')
                    elif isinstance(perms, list):
                        for p in perms:
                            if isinstance(p, dict) and p.get('storeId'):
                                derived_store = p.get('storeId')
                                break
                            if isinstance(p, str):
                                # list of allowed store IDs
                                # if only one element, use it
                                if len(perms) == 1:
                                    derived_store = p
                                    break
                    elif isinstance(perms, str):
                        derived_store = perms
                except Exception:
                    derived_store = None

                if derived_store:
                    store_id = derived_store
                    # make available to handler
                    setattr(req, 'store_id', store_id)
                else:
                    return https_fn.Response(
                        json.dumps({
                            "success": False,
                            "error": "Missing store ID",
                            "message": "storeId parameter is required"
                        }),
                        status=400,
                        headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"}
                    )
            else:
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
            # Safely extract user's store from permissions for the error payload
            perms = req.user.get('permissions')
            user_store = None
            try:
                if isinstance(perms, dict):
                    user_store = perms.get('storeId')
                elif isinstance(perms, list):
                    for p in perms:
                        if isinstance(p, dict) and p.get('storeId'):
                            user_store = p.get('storeId')
                            break
                        if isinstance(p, str) and p == store_id:
                            user_store = p
                            break
                elif isinstance(perms, str):
                    user_store = perms
            except Exception:
                user_store = None

            return https_fn.Response(
                json.dumps({
                    "success": False,
                    "error": "Access denied",
                    "message": error,
                    "requested_store": store_id,
                    "user_store": user_store
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


def extract_user_permissions(user_data):
    """
    Normalize and extract common permission fields from a user document.

    Returns a dict with keys: companyId, storeId, roleId. Values may be None.
    """
    company_id = None
    store_id = None
    role_id = None

    try:
        perms = user_data.get('permissions') if user_data else None

        if isinstance(perms, dict):
            company_id = perms.get('companyId')
            store_id = perms.get('storeId')
            role_id = perms.get('roleId')

        elif isinstance(perms, list):
            # Prefer dict entries inside list
            for p in perms:
                if isinstance(p, dict):
                    if company_id is None and p.get('companyId'):
                        company_id = p.get('companyId')
                    if store_id is None and p.get('storeId'):
                        store_id = p.get('storeId')
                    if role_id is None and p.get('roleId'):
                        role_id = p.get('roleId')
            # If list contains plain strings and only one element, treat it as storeId
            if store_id is None:
                strings = [p for p in perms if isinstance(p, str)]
                if len(strings) == 1:
                    store_id = strings[0]

        elif isinstance(perms, str):
            # Permissions stored as a single store id string
            store_id = perms

    except Exception as e:
        print(f"⚠️ Warning while extracting permissions: {e}")

    return {"companyId": company_id, "storeId": store_id, "roleId": role_id}