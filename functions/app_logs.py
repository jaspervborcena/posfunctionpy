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
    """Write log entry to Google Cloud Logging using service account (fault-tolerant)"""
    if not logging_client:
        return False
    
    try:
        severity_map = {
            'DEBUG': 'DEBUG',
            'INFO': 'INFO', 
            'WARNING': 'WARNING',
            'ERROR': 'ERROR'
        }
        
        # Use safe defaults
        severity = severity_map.get(log_entry.get('severity', 'INFO'), 'INFO')
        
        # Prepare structured payload with safe field access
        structured_payload = {}
        try:
            structured_payload = {
                'message': str(log_entry.get('message', 'No message provided')),
                'level': str(log_entry.get('level', 'info')),
                'timestamp': str(log_entry.get('timestamp', datetime.now(timezone.utc).isoformat())),
                'user': user_context if isinstance(user_context, dict) else {},
                'context': {
                    'area': str(log_entry.get('area', '')),
                    'api': str(log_entry.get('api', '')),
                    'collectionPath': str(log_entry.get('collectionPath', '')),
                    'docId': str(log_entry.get('docId', '')),
                    'correlationId': str(log_entry.get('correlationId', '')),
                    'status': log_entry.get('status'),
                    'success': log_entry.get('success'),
                    'durationMs': log_entry.get('durationMs'),
                },
                'labels': log_entry.get('labels', {}) if isinstance(log_entry.get('labels'), dict) else {},
                'payload': log_entry.get('payload'),
                'error': log_entry.get('error'),
                'originalLogEntry': log_entry if isinstance(log_entry, dict) else {}
            }
        except Exception as e:
            print(f"⚠️ Error preparing Cloud Logging payload (using minimal): {e}")
            structured_payload = {
                'message': str(log_entry.get('message', 'Logging payload preparation failed')),
                'level': 'error',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': f'Payload preparation failed: {str(e)}'
            }

        # Clean up context safely
        try:
            if 'context' in structured_payload and isinstance(structured_payload['context'], dict):
                structured_payload['context'] = {k: v for k, v in structured_payload['context'].items() 
                                               if v is not None and v != ''}
        except Exception as e:
            print(f"⚠️ Error cleaning context (continuing): {e}")

        # Get logger and write (with fallbacks)
        try:
            logger = logging_client.logger("app-logs")
            
            # Prepare safe labels
            labels = {}
            try:
                labels = {
                    'source': 'firebase-function',
                    'function': 'app_logs',
                    'userId': str(user_context.get('userId', 'unknown')),
                    'userEmail': str(user_context.get('userEmail', 'unknown')),
                    'userName': str(user_context.get('userName', 'unknown')),
                    'storeId': str(user_context.get('storeId', 'unknown')),
                    'companyId': str(user_context.get('companyId', 'unknown')),
                    'roleId': str(user_context.get('roleId', 'unknown')),
                    'userStatus': str(user_context.get('userStatus', 'unknown'))
                }
            except Exception as e:
                print(f"⚠️ Error preparing labels (using minimal): {e}")
                labels = {'source': 'firebase-function', 'function': 'app_logs'}
            
            # Write to Cloud Logging
            logger.log_struct(structured_payload, severity=severity, labels=labels)
            return True
            
        except Exception as e:
            print(f"⚠️ Cloud Logging write failed: {e}")
            return False
        
    except Exception as e:
        print(f"⚠️ Complete Cloud Logging failure: {e}")
        return False


REQUIRED_FIELDS = [
    "timestamp",
    "level",
    "severity", 
    "message",
    "uid"  # Firebase UID instead of full auth
]


def _validate_payload(body: Dict[str, Any]) -> str | None:
    """Validate payload but never throw exceptions (fault-tolerant)"""
    try:
        if not isinstance(body, dict):
            return "Body is not a dictionary object"
        
        # Check for required fields (but don't fail completely)
        missing_fields = []
        for f in REQUIRED_FIELDS:
            if f not in body:
                missing_fields.append(f)
        
        if missing_fields:
            return f"Missing fields: {', '.join(missing_fields)} (will use defaults)"
        
        # Basic type checks with safe defaults
        try:
            message = body.get("message")
            if message is not None and not isinstance(message, str):
                return "Field 'message' should be a string (will convert)"
        except Exception:
            pass
        
        try:
            uid = body.get("uid")
            if uid is not None and (not isinstance(uid, str) or not str(uid).strip()):
                return "Field 'uid' should be a non-empty string (will use fallback)"
        except Exception:
            pass
        
        # Optional field validations (non-blocking)
        try:
            status = body.get("status")
            if status is not None and status not in (200, 400, 500):
                return f"Field 'status' should be 200, 400, or 500 (got {status})"
        except Exception:
            pass
        
        try:
            success = body.get("success")
            if success is not None and not isinstance(success, bool):
                return f"Field 'success' should be boolean (got {type(success).__name__})"
        except Exception:
            pass
        
        return None  # All validations passed
        
    except Exception as e:
        return f"Validation check failed: {str(e)} (will proceed anyway)"


def _sanitize(body: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure payload is JSON-serializable and keep size reasonable (fault-tolerant)
    try:
        out = dict(body) if isinstance(body, dict) else {}
    except Exception as e:
        print(f"⚠️ Failed to copy body dict (using empty): {e}")
        out = {}
    
    # Truncate large fields defensively
    try:
        msg = out.get("message")
        if isinstance(msg, str) and len(msg) > 2000:
            out["message"] = msg[:2000] + "…"
        elif msg is not None and not isinstance(msg, str):
            out["message"] = str(msg)[:2000]
    except Exception as e:
        print(f"⚠️ Message sanitization failed: {e}")
        out["message"] = "Message sanitization failed"
    
    # Handle payload safely
    try:
        payload = out.get("payload")
        if isinstance(payload, (dict, list)):
            try:
                dumps = json.dumps(payload)
                if len(dumps) > 20000:
                    out["payload"] = {"_note": "truncated", "size": len(dumps)}
            except Exception:
                out["payload"] = {"_note": "non-serializable", "type": str(type(payload))}
        elif payload is not None:
            # Convert non-dict/list payloads to strings safely
            try:
                out["payload"] = str(payload)[:1000]  # Limit string payloads too
            except Exception:
                out["payload"] = {"_note": "conversion-failed", "type": str(type(payload))}
    except Exception as e:
        print(f"⚠️ Payload sanitization failed: {e}")
        out["payload"] = {"_note": "sanitization-failed", "error": str(e)}
    
    return out


@https_fn.on_request(region="asia-east1")
def app_logs(req: https_fn.Request) -> https_fn.Response:
    origin = req.headers.get("Origin")

    # Handle CORS preflight
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204, headers=_cors_headers(origin))

    if req.method != "POST":
        return _bad_request("Only POST is supported", origin)

    # NEVER block for API key validation - just log the attempt
    try:
        if not _validate_api_key(req):
            print("⚠️ API key validation failed, but allowing request to proceed")
    except Exception as e:
        print(f"⚠️ API key validation error (proceeding anyway): {e}")

    content_type = (req.headers.get("Content-Type") or "").lower()
    if "application/json" not in content_type:
        print("⚠️ Invalid content type, but attempting to process anyway")

    # Try to parse JSON, but be very forgiving
    try:
        body = req.get_json(silent=True)
        if not body:
            # Try to parse manually if get_json fails
            try:
                body = json.loads(req.data.decode('utf-8') if req.data else '{}')
            except:
                body = {}
    except Exception as e:
        print(f"⚠️ JSON parsing failed (using empty body): {e}")
        body = {}

    if not isinstance(body, dict):
        print("⚠️ Body is not a dict, converting...")
        body = {}

    # NEVER block for validation errors - just log what we can
    validation_error = None
    try:
        validation_error = _validate_payload(body)
        if validation_error:
            print(f"⚠️ Validation warning (proceeding anyway): {validation_error}")
    except Exception as e:
        print(f"⚠️ Validation check failed (proceeding anyway): {e}")

    # Try to get UID, but don't fail if missing
    uid = body.get("uid", "unknown-uid")
    user_data = None
    user_context = {
        'userId': uid,
        'userEmail': 'unknown@logging-fallback.com',
        'userName': 'Unknown User',
        'userStatus': 'unknown',
        'companyId': 'unknown',
        'storeId': 'unknown',
        'roleId': 'unknown',
        'error': 'User verification was skipped to prevent blocking'
    }

    # Try to verify user, but NEVER block the operation
    if uid and uid != "unknown-uid":
        try:
            user_data, auth_error = _verify_firebase_uid(uid)
            if auth_error:
                print(f"⚠️ User verification failed (using fallback): {auth_error}")
            else:
                try:
                    user_context = _extract_user_context(user_data)
                    print(f"✅ User verification successful for logging")
                except Exception as e:
                    print(f"⚠️ User context extraction failed (using fallback): {e}")
        except Exception as e:
            print(f"⚠️ User verification process failed (using fallback): {e}")

    # Always try to log, but never fail the request
    try:
        # Sanitize what we can
        log_entry = {}
        try:
            log_entry = _sanitize(body)
        except Exception as e:
            print(f"⚠️ Sanitization failed (using raw body): {e}")
            log_entry = body.copy() if isinstance(body, dict) else {}

        # Add server metadata safely
        try:
            log_entry.update({
                'server_timestamp': datetime.now(timezone.utc).isoformat(),
                'source': 'ui-via-cloud-function',
                'function_version': '2.0-fault-tolerant',
                'validation_warning': validation_error,
                'fallback_mode': user_data is None
            })
        except Exception as e:
            print(f"⚠️ Failed to add server metadata: {e}")

        # Try Cloud Logging (best effort)
        cloud_logging_success = False
        try:
            cloud_logging_success = _write_to_cloud_logging(log_entry, user_context)
        except Exception as e:
            print(f"⚠️ Cloud Logging failed (continuing): {e}")

        # Try Firestore logging (best effort)
        firestore_success = False
        try:
            db = firestore.client()
            firestore_doc = {
                **log_entry,
                'user_context': user_context,
                'cloud_logging_success': cloud_logging_success,
                'logged_at': datetime.now(timezone.utc).isoformat()
            }
            db.collection("appLogs").add(firestore_doc)
            firestore_success = True
        except Exception as e:
            print(f"⚠️ Firestore logging failed (continuing): {e}")

        # Success logging (best effort)
        try:
            if firestore_success or cloud_logging_success:
                print(f"✅ Log written successfully - Cloud Logging: {cloud_logging_success}, Firestore: {firestore_success}")
                print(f"📊 User: {user_context.get('userEmail', 'unknown')}, Role: {user_context.get('roleId', 'unknown')}")
            else:
                print(f"⚠️ Both logging methods failed, but request succeeded")
        except Exception as e:
            print(f"⚠️ Success logging failed: {e}")

    except Exception as e:
        # Even if everything fails, still return success
        print(f"❌ Complete logging failure (but returning success): {e}")

    # ALWAYS return success - logging should never block the UI
    return _ok(origin)
