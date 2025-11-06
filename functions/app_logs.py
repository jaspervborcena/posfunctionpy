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
        
        # Verify UID exists in Firebase Auth
        try:
            user_record = auth.get_user(uid)
            email = user_record.email
        except auth.UserNotFoundError:
            return None, f"Firebase user not found for UID: {uid}"
        except Exception as e:
            return None, f"Firebase Auth verification failed: {str(e)}"
        
        # Get user data from Firestore
        db = firestore.client()
        try:
            user_doc_ref = db.collection('users').document(uid)
            user_snapshot = user_doc_ref.get()
            
            if user_snapshot.exists:
                user_data = user_snapshot.to_dict()
                user_data['doc_id'] = user_snapshot.id
                user_data['firebase_email'] = email
            else:
                # Fallback: search by uid field
                users_ref = db.collection('users')
                user_query = users_ref.where('uid', '==', uid).limit(1)
                user_docs = user_query.get()
                
                if not user_docs:
                    return None, f"User not found in Firestore for UID: {uid}"
                
                user_doc = user_docs[0]
                user_data = user_doc.to_dict()
                user_data['doc_id'] = user_doc.id
                user_data['firebase_email'] = email
        
        except Exception as e:
            return None, f"Firestore user lookup failed: {str(e)}"
        
        # Check if user is active
        if user_data.get('status') != 'active':
            return None, f"User account is inactive. Status: {user_data.get('status')}"
        
        return user_data, None
        
    except Exception as e:
        return None, f"UID verification failed: {str(e)}"


def _extract_user_context(user_data: Dict[str, Any]) -> Dict[str, str]:
    """Extract user context for logging metadata"""
    try:
        permissions = user_data.get('permissions', {})
        
        context = {
            'userId': user_data.get('uid') or user_data.get('doc_id', ''),
            'userEmail': user_data.get('email') or user_data.get('firebase_email', ''),
            'userName': user_data.get('displayName', ''),
        }
        
        # Extract company/store/role info
        if isinstance(permissions, dict):
            context.update({
                'companyId': permissions.get('companyId', ''),
                'storeId': permissions.get('storeId', ''),
                'roleId': permissions.get('roleId', '')
            })
        elif isinstance(permissions, list):
            for p in permissions:
                if isinstance(p, dict):
                    if not context.get('companyId') and p.get('companyId'):
                        context['companyId'] = p.get('companyId')
                    if not context.get('storeId') and p.get('storeId'):
                        context['storeId'] = p.get('storeId')
                    if not context.get('roleId') and p.get('roleId'):
                        context['roleId'] = p.get('roleId')
        
        return {k: str(v) if v else '' for k, v in context.items()}
        
    except Exception as e:
        print(f"Warning: Failed to extract user context: {e}")
        return {
            'userId': user_data.get('uid', ''),
            'userEmail': '',
            'userName': '',
            'companyId': '',
            'storeId': '',
            'roleId': ''
        }


def _write_to_cloud_logging(log_entry: Dict[str, Any], user_context: Dict[str, str]) -> bool:
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
        
        # Prepare structured payload
        structured_payload = {
            'message': log_entry.get('message', ''),
            'level': log_entry.get('level', 'info'),
            'timestamp': log_entry.get('timestamp', datetime.now(timezone.utc).isoformat()),
            'user': user_context,
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
            'payload': log_entry.get('payload'),
            'error': log_entry.get('error')
        }
        
        # Remove empty values to keep logs clean
        structured_payload = {k: v for k, v in structured_payload.items() 
                            if v is not None and v != '' and v != {}}
        structured_payload['context'] = {k: v for k, v in structured_payload['context'].items() 
                                       if v is not None and v != ''}
        
        # Get logger for the application
        logger = logging_client.logger("app-logs")
        
        # Write structured log entry
        logger.log_struct(
            structured_payload,
            severity=severity,
            labels={
                'source': 'firebase-function',
                'function': 'app_logs',
                'userId': user_context.get('userId', ''),
                'storeId': user_context.get('storeId', ''),
                'companyId': user_context.get('companyId', '')
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
        
        print(f"✅ Log written successfully - Cloud Logging: {cloud_logging_success}, Firestore: True, User: {user_context.get('userEmail', uid)}")
        
    except Exception as e:
        print(f"❌ Logging write failed: {e}")
        return _server_error(f"Failed to write log: {str(e)}", origin)

    return _ok(origin)
