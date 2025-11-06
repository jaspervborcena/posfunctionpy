from __future__ import annotations

import json
import os
from typing import Any, Dict
from datetime import datetime, timezone

from firebase_functions import https_fn
from firebase_admin import firestore, auth

# Basic CORS helpers
ALLOWED_ORIGINS = os.getenv("CLOUD_LOGGING_ALLOWED_ORIGINS", "*")
REQUIRE_API_KEY = os.getenv("CLOUD_LOGGING_REQUIRE_API_KEY", "false").lower() in ("1", "true", "yes")
API_KEY = os.getenv("CLOUD_LOGGING_API_KEY")

# Initialize Cloud Logging client with service account
try:
    from google.cloud import logging as cloud_logging
    logging_client = cloud_logging.Client()
    logging_client.setup_logging()
except ImportError:
    print("Google Cloud Logging not available - using Firestore only")
    logging_client = None
except Exception as e:
    print(f"Warning: Cloud Logging client initialization failed: {e}")
    logging_client = None


def _cors_headers(origin: str | None) -> Dict[str, str]:
    allow_origin = "*" if ALLOWED_ORIGINS == "*" else (origin if origin and origin in ALLOWED_ORIGINS.split(",") else "")
    headers = {
        "Access-Control-Allow-Origin": allow_origin or "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, X-API-Key",
        "Access-Control-Max-Age": "3600",
        "Content-Type": "application/json",
    }
    return headers


def _bad_request(message: str, origin: str | None) -> https_fn.Response:
    return https_fn.Response(json.dumps({"ok": False, "error": message}), status=400, headers=_cors_headers(origin))


def _server_error(message: str, origin: str | None) -> https_fn.Response:
    return https_fn.Response(json.dumps({"ok": False, "error": message}), status=500, headers=_cors_headers(origin))


def _ok(origin: str | None) -> https_fn.Response:
    return https_fn.Response(json.dumps({"ok": True}), status=200, headers=_cors_headers(origin))


def _validate_api_key(req: https_fn.Request) -> bool:
    if not REQUIRE_API_KEY:
        return True
    provided = req.headers.get("x-api-key") or req.headers.get("X-API-Key")
    return bool(API_KEY) and provided == API_KEY


def _verify_firebase_uid(uid: str) -> tuple[Dict[str, Any] | None, str | None]:
    """
    Verify Firebase UID and get user data from Firestore
    Returns (user_data, error_message)
    """
    try:
        if not uid or not isinstance(uid, str):
            return None, "Invalid UID format"
        
        print(f"🔍 Verifying Firebase UID: {uid}")
        
        # Verify UID exists in Firebase Auth
        try:
            user_record = auth.get_user(uid)
            email = user_record.email
            print(f"✅ Firebase Auth verification successful - Email: {email}")
        except auth.UserNotFoundError:
            print(f"❌ Firebase user not found for UID: {uid}")
            return None, f"Firebase user not found for UID: {uid}"
        except Exception as e:
            print(f"❌ Firebase Auth verification failed: {str(e)}")
            return None, f"Firebase Auth verification failed: {str(e)}"
        
        # Get user data from Firestore users collection
        db = firestore.client()
        try:
            print(f"🔍 Looking up user in Firestore users collection...")
            user_doc_ref = db.collection('users').document(uid)
            user_snapshot = user_doc_ref.get()
            
            if user_snapshot.exists:
                user_data = user_snapshot.to_dict()
                user_data['doc_id'] = user_snapshot.id
                user_data['firebase_email'] = email
                print(f"✅ User found by document ID: {user_snapshot.id}")
                print(f"📋 User data fields: {list(user_data.keys())}")
            else:
                print(f"🔍 User not found by document ID, searching by uid field...")
                # Fallback: search by uid field
                users_ref = db.collection('users')
                user_query = users_ref.where('uid', '==', uid).limit(1)
                user_docs = user_query.get()
                
                if not user_docs:
                    print(f"❌ User not found in Firestore users collection for UID: {uid}")
                    return None, f"User not found in Firestore users collection for UID: {uid}"
                
                user_doc = user_docs[0]
                user_data = user_doc.to_dict()
                user_data['doc_id'] = user_doc.id
                user_data['firebase_email'] = email
                print(f"✅ User found by uid field query: {user_doc.id}")
                print(f"📋 User data fields: {list(user_data.keys())}")
        
        except Exception as e:
            print(f"❌ Firestore user lookup failed: {str(e)}")
            return None, f"Firestore user lookup failed: {str(e)}"
        
        # Check if user is active
        user_status = user_data.get('status')
        print(f"🔍 User status: {user_status}")
        if user_status != 'active':
            print(f"❌ User account is inactive. Status: {user_status}")
            return None, f"User account is inactive. Status: {user_status}"
        
        # Log user details for verification
        print(f"✅ User verification successful:")
        print(f"   📧 Email: {user_data.get('email', 'N/A')} / Firebase: {email}")
        print(f"   👤 Name: {user_data.get('displayName', 'N/A')}")
        print(f"   🏢 Permissions: {user_data.get('permissions', 'N/A')}")
        print(f"   📄 Document ID: {user_data.get('doc_id', 'N/A')}")
        
        return user_data, None
        
    except Exception as e:
        print(f"❌ UID verification failed: {str(e)}")
        return None, f"UID verification failed: {str(e)}"


def _extract_user_context(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract comprehensive user context for logging metadata"""
    try:
        permissions = user_data.get('permissions', {})
        
        # Core user information
        context = {
            'userId': user_data.get('uid') or user_data.get('doc_id', ''),
            'userEmail': user_data.get('email') or user_data.get('firebase_email', ''),
            'userName': user_data.get('displayName', ''),
            'userStatus': user_data.get('status', ''),
            'userDocId': user_data.get('doc_id', ''),
            'firebaseEmail': user_data.get('firebase_email', ''),
        }
        
        # Extract company/store/role info
        if isinstance(permissions, dict):
            context.update({
                'companyId': permissions.get('companyId', ''),
                'storeId': permissions.get('storeId', ''),
                'roleId': permissions.get('roleId', ''),
                'permissions': permissions  # Include full permissions object
            })
        elif isinstance(permissions, list):
            # Handle permissions as list and extract all available info
            context['permissions'] = permissions
            for p in permissions:
                if isinstance(p, dict):
                    if not context.get('companyId') and p.get('companyId'):
                        context['companyId'] = p.get('companyId')
                    if not context.get('storeId') and p.get('storeId'):
                        context['storeId'] = p.get('storeId')
                    if not context.get('roleId') and p.get('roleId'):
                        context['roleId'] = p.get('roleId')
        else:
            context['permissions'] = permissions
        
        # Add additional user fields that might be useful for logging
        additional_fields = ['createdAt', 'updatedAt', 'lastLogin', 'phone', 'department']
        for field in additional_fields:
            if field in user_data:
                context[field] = user_data[field]
        
        # Include full user data snapshot for comprehensive logging
        context['fullUserData'] = user_data
        
        # Ensure string conversion for basic fields but keep objects as-is for detailed logging
        string_fields = ['userId', 'userEmail', 'userName', 'userStatus', 'userDocId', 'firebaseEmail', 'companyId', 'storeId', 'roleId']
        for field in string_fields:
            if field in context:
                context[field] = str(context[field]) if context[field] else ''
        
        return context
        
    except Exception as e:
        print(f"Warning: Failed to extract user context: {e}")
        return {
            'userId': user_data.get('uid', ''),
            'userEmail': '',
            'userName': '',
            'userStatus': '',
            'companyId': '',
            'storeId': '',
            'roleId': '',
            'error': f'Context extraction failed: {str(e)}',
            'fullUserData': user_data  # Still include full data even if extraction fails
        }


def _write_to_cloud_logging(log_entry: Dict[str, Any], user_context: Dict[str, Any]) -> bool:
    """Write log entry to Google Cloud Logging using service account"""
    if not logging_client:
        return False
    
    try:
        severity_map = {
            'DEBUG': 'DEBUG',
            'INFO': 'INFO', 
            'WARNING': 'WARNING',
            'ERROR': 'ERROR'
        }
        
        severity = severity_map.get(log_entry.get('severity', 'INFO'), 'INFO')
        
        # Prepare structured payload with complete user information
        structured_payload = {
            'message': log_entry.get('message', ''),
            'level': log_entry.get('level', 'info'),
            'timestamp': log_entry.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'user': user_context,  # Now includes comprehensive user data
            'context': {
                'area': log_entry.get('area', ''),
                'api': log_entry.get('api', ''),
                'collectionPath': log_entry.get('collectionPath', ''),
                'docId': log_entry.get('docId', ''),
                'correlationId': log_entry.get('correlationId', ''),
                'status': log_entry.get('status'),
                'success': log_entry.get('success'),
                'durationMs': log_entry.get('durationMs'),
            },
            'labels': log_entry.get('labels', {}),
            'payload': log_entry.get('payload'),  # Complete original payload
            'error': log_entry.get('error'),
            'originalLogEntry': log_entry  # Include complete original log entry
        }
        
        # Keep all data - don't remove empty values for comprehensive logging
        # Only remove the 'context' sub-object empty values to keep it clean
        if 'context' in structured_payload:
            structured_payload['context'] = {k: v for k, v in structured_payload['context'].items() 
                                           if v is not None and v != ''}
        
        # Get logger for the application
        logger = logging_client.logger("app-logs")
        
        # Write structured log entry with comprehensive labels
        logger.log_struct(
            structured_payload,
            severity=severity,
            labels={
                'source': 'firebase-function',
                'function': 'app_logs',
                'userId': user_context.get('userId', ''),
                'userEmail': user_context.get('userEmail', ''),
                'userName': user_context.get('userName', ''),
                'storeId': user_context.get('storeId', ''),
                'companyId': user_context.get('companyId', ''),
                'roleId': user_context.get('roleId', ''),
                'userStatus': user_context.get('userStatus', '')
            }
        )
        
        return True
        
    except Exception as e:
        print(f"Cloud Logging write failed: {e}")
        return False


REQUIRED_FIELDS = [
    "timestamp",
    "level",
    "severity", 
    "message",
    "uid"  # Firebase UID instead of full auth
]


def _validate_payload(body: Dict[str, Any]) -> str | None:
    for f in REQUIRED_FIELDS:
        if f not in body:
            return f"Missing required field: {f}"
    
    # Basic type checks
    if not isinstance(body.get("message"), str):
        return "Field 'message' must be a string"
    
    if not isinstance(body.get("uid"), str) or not body.get("uid").strip():
        return "Field 'uid' must be a non-empty string"
    
    # Optional field validations
    if "status" in body and body.get("status") not in (200, 400, 500):
        return "Field 'status' must be one of 200, 400, 500"
    
    if "success" in body and not isinstance(body.get("success"), bool):
        return "Field 'success' must be boolean"
    
    return None


def _sanitize(body: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure payload is JSON-serializable and keep size reasonable
    out = dict(body)
    # Truncate large fields defensively
    msg = out.get("message")
    if isinstance(msg, str) and len(msg) > 2000:
        out["message"] = msg[:2000] + "…"
    payload = out.get("payload")
    if isinstance(payload, (dict, list)):
        try:
            dumps = json.dumps(payload)
            if len(dumps) > 20000:
                out["payload"] = {"_note": "truncated", "size": len(dumps)}
        except Exception:
            out["payload"] = {"_note": "non-serializable"}
    return out


@https_fn.on_request(region="asia-east1")
def app_logs(req: https_fn.Request) -> https_fn.Response:
    origin = req.headers.get("Origin")

    # Handle CORS preflight
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204, headers=_cors_headers(origin))

    if req.method != "POST":
        return _bad_request("Only POST is supported", origin)

    if not _validate_api_key(req):
        return https_fn.Response(json.dumps({"ok": False, "error": "Unauthorized"}), status=401, headers=_cors_headers(origin))

    content_type = (req.headers.get("Content-Type") or "").lower()
    if "application/json" not in content_type:
        return _bad_request("Content-Type must be application/json", origin)

    try:
        body = req.get_json(silent=False)
    except Exception:
        return _bad_request("Invalid JSON body", origin)

    if not isinstance(body, dict):
        return _bad_request("JSON body must be an object", origin)

    err = _validate_payload(body)
    if err:
        return _bad_request(err, origin)

    # Verify Firebase UID and get user data
    uid = body.get("uid")
    user_data, auth_error = _verify_firebase_uid(uid)
    if auth_error:
        return https_fn.Response(
            json.dumps({"ok": False, "error": "Authentication failed", "message": auth_error}),
            status=401,
            headers=_cors_headers(origin)
        )

    # Extract user context for enriched logging
    user_context = _extract_user_context(user_data)

    # Sanitize and enrich
    log_entry = _sanitize(body)

    # Add server-side metadata
    log_entry.update({
        'server_timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'ui-via-cloud-function',
        'function_version': '2.0'
    })

    try:
        # Write to Cloud Logging using service account (primary)
        cloud_logging_success = _write_to_cloud_logging(log_entry, user_context)
        
        # Also write to Firestore for backup/analytics (secondary)
        db = firestore.client()
        firestore_doc = {
            **log_entry,
            'user_context': user_context,
            'cloud_logging_success': cloud_logging_success
        }
        db.collection("appLogs").add(firestore_doc)
        
        print(f"✅ Log written successfully - Cloud Logging: {cloud_logging_success}, Firestore: True")
        print(f"📊 User Details - Email: {user_context.get('userEmail', 'N/A')}, Name: {user_context.get('userName', 'N/A')}, Role: {user_context.get('roleId', 'N/A')}")
        print(f"🏢 Organization - Company: {user_context.get('companyId', 'N/A')}, Store: {user_context.get('storeId', 'N/A')}")
        print(f"🔍 User Status: {user_context.get('userStatus', 'N/A')}, UID: {uid}")
        
    except Exception as e:
        print(f"❌ Logging write failed: {e}")
        print(f"🔍 Failed for user: {user_context.get('userEmail', uid)}")
        return _server_error(f"Failed to write log: {str(e)}", origin)

    return _ok(origin)
