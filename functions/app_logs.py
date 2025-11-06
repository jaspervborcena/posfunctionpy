from __future__ import annotationsfrom __future__ import annotations



import jsonimport json

import osimport os

from typing import Any, Dictfrom typing import Any, Dict

from datetime import datetime, timezonefrom datetime import datetime, timezone



from firebase_functions import https_fnfrom firebase_functions import https_fn

from firebase_admin import firestore, authfrom firebase_admin import firestore, auth

from google.cloud import logging as cloud_loggingfrom google.cloud import logging as cloud_logging



# Basic CORS helpers# Basic CORS helpers

ALLOWED_ORIGINS = os.getenv("CLOUD_LOGGING_ALLOWED_ORIGINS", "*")ALLOWED_ORIGINS = os.getenv("CLOUD_LOGGING_ALLOWED_ORIGINS", "*")

REQUIRE_API_KEY = os.getenv("CLOUD_LOGGING_REQUIRE_API_KEY", "false").lower() in ("1", "true", "yes")REQUIRE_API_KEY = os.getenv("CLOUD_LOGGING_REQUIRE_API_KEY", "false").lower() in ("1", "true", "yes")

API_KEY = os.getenv("CLOUD_LOGGING_API_KEY")API_KEY = os.getenv("CLOUD_LOGGING_API_KEY")



# Initialize Cloud Logging client with service account# Initialize Cloud Logging client with service account

try:try:

    logging_client = cloud_logging.Client()    logging_client = cloud_logging.Client()

    logging_client.setup_logging()    logging_client.setup_logging()

except Exception as e:except Exception as e:

    print(f"Warning: Cloud Logging client initialization failed: {e}")    print(f"Warning: Cloud Logging client initialization failed: {e}")

    logging_client = None    logging_client = None





def _cors_headers(origin: str | None) -> Dict[str, str]:def _cors_headers(origin: str | None) -> Dict[str, str]:

    allow_origin = "*" if ALLOWED_ORIGINS == "*" else (origin if origin and origin in ALLOWED_ORIGINS.split(",") else "")    allow_origin = "*" if ALLOWED_ORIGINS == "*" else (origin if origin and origin in ALLOWED_ORIGINS.split(",") else "")

    headers = {    headers = {

        "Access-Control-Allow-Origin": allow_origin or "*",        "Access-Control-Allow-Origin": allow_origin or "*",

        "Access-Control-Allow-Methods": "POST, OPTIONS",        "Access-Control-Allow-Methods": "POST, OPTIONS",

        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, X-API-Key",        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, X-API-Key",

        "Access-Control-Max-Age": "3600",        "Access-Control-Max-Age": "3600",

        "Content-Type": "application/json",        "Content-Type": "application/json",

    }    }

    return headers    return headers





def _bad_request(message: str, origin: str | None) -> https_fn.Response:def _bad_request(message: str, origin: str | None) -> https_fn.Response:

    return https_fn.Response(json.dumps({"ok": False, "error": message}), status=400, headers=_cors_headers(origin))    return https_fn.Response(json.dumps({"ok": False, "error": message}), status=400, headers=_cors_headers(origin))





def _server_error(message: str, origin: str | None) -> https_fn.Response:def _server_error(message: str, origin: str | None) -> https_fn.Response:

    return https_fn.Response(json.dumps({"ok": False, "error": message}), status=500, headers=_cors_headers(origin))    return https_fn.Response(json.dumps({"ok": False, "error": message}), status=500, headers=_cors_headers(origin))





def _ok(origin: str | None) -> https_fn.Response:def _ok(origin: str | None) -> https_fn.Response:

    return https_fn.Response(json.dumps({"ok": True}), status=200, headers=_cors_headers(origin))    return https_fn.Response(json.dumps({"ok": True}), status=200, headers=_cors_headers(origin))





def _validate_api_key(req: https_fn.Request) -> bool:def _validate_api_key(req: https_fn.Request) -> bool:

    if not REQUIRE_API_KEY:    if not REQUIRE_API_KEY:

        return True        return True

    provided = req.headers.get("x-api-key") or req.headers.get("X-API-Key")    provided = req.headers.get("x-api-key") or req.headers.get("X-API-Key")

    return bool(API_KEY) and provided == API_KEY    return bool(API_KEY) and provided == API_KEY





def _verify_firebase_uid(uid: str) -> tuple[Dict[str, Any] | None, str | None]:def _verify_firebase_uid(uid: str) -> tuple[Dict[str, Any] | None, str | None]:

    """    """

    Verify Firebase UID and get user data from Firestore    Verify Firebase UID and get user data from Firestore

    Returns (user_data, error_message)    Returns (user_data, error_message)

    """    """

    try:    try:

        if not uid or not isinstance(uid, str):        if not uid or not isinstance(uid, str):

            return None, "Invalid UID format"            return None, "Invalid UID format"

                

        # Verify UID exists in Firebase Auth (lightweight check)        # Verify UID exists in Firebase Auth (lightweight check)

        try:        try:

            user_record = auth.get_user(uid)            user_record = auth.get_user(uid)

            email = user_record.email            email = user_record.email

        except auth.UserNotFoundError:        except auth.UserNotFoundError:

            return None, f"Firebase user not found for UID: {uid}"            return None, f"Firebase user not found for UID: {uid}"

        except Exception as e:        except Exception as e:

            return None, f"Firebase Auth verification failed: {str(e)}"            return None, f"Firebase Auth verification failed: {str(e)}"

                

        # Get user data from Firestore        # Get user data from Firestore

        db = firestore.client()        db = firestore.client()

        try:        try:

            user_doc_ref = db.collection('users').document(uid)            user_doc_ref = db.collection('users').document(uid)

            user_snapshot = user_doc_ref.get()            user_snapshot = user_doc_ref.get()

                        

            if user_snapshot.exists:            if user_snapshot.exists:

                user_data = user_snapshot.to_dict()                user_data = user_snapshot.to_dict()

                user_data['doc_id'] = user_snapshot.id                user_data['doc_id'] = user_snapshot.id

                user_data['firebase_email'] = email  # Add Firebase email for reference                user_data['firebase_email'] = email  # Add Firebase email for reference

            else:            else:

                # Fallback: search by uid field                # Fallback: search by uid field

                users_ref = db.collection('users')                users_ref = db.collection('users')

                user_query = users_ref.where('uid', '==', uid).limit(1)                user_query = users_ref.where('uid', '==', uid).limit(1)

                user_docs = user_query.get()                user_docs = user_query.get()

                                

                if not user_docs:                if not user_docs:

                    return None, f"User not found in Firestore for UID: {uid}"                    return None, f"User not found in Firestore for UID: {uid}"

                                

                user_doc = user_docs[0]                user_doc = user_docs[0]

                user_data = user_doc.to_dict()                user_data = user_doc.to_dict()

                user_data['doc_id'] = user_doc.id                user_data['doc_id'] = user_doc.id

                user_data['firebase_email'] = email                user_data['firebase_email'] = email

                

        except Exception as e:        except Exception as e:

            return None, f"Firestore user lookup failed: {str(e)}"            return None, f"Firestore user lookup failed: {str(e)}"

                

        # Check if user is active        # Check if user is active

        if user_data.get('status') != 'active':        if user_data.get('status') != 'active':

            return None, f"User account is inactive. Status: {user_data.get('status')}"            return None, f"User account is inactive. Status: {user_data.get('status')}"

                

        return user_data, None        return user_data, None

                

    except Exception as e:    except Exception as e:

        return None, f"UID verification failed: {str(e)}"        return None, f"UID verification failed: {str(e)}"





def _extract_user_context(user_data: Dict[str, Any]) -> Dict[str, str]:def _extract_user_context(user_data: Dict[str, Any]) -> Dict[str, str]:

    """Extract user context for logging metadata"""    """Extract user context for logging metadata"""

    try:    try:

        permissions = user_data.get('permissions', {})        permissions = user_data.get('permissions', {})

                

        context = {        context = {

            'userId': user_data.get('uid') or user_data.get('doc_id', ''),            'userId': user_data.get('uid') or user_data.get('doc_id', ''),

            'userEmail': user_data.get('email') or user_data.get('firebase_email', ''),            'userEmail': user_data.get('email') or user_data.get('firebase_email', ''),

            'userName': user_data.get('displayName', ''),            'userName': user_data.get('displayName', ''),

        }        }

                

        # Extract company/store/role info        # Extract company/store/role info

        if isinstance(permissions, dict):        if isinstance(permissions, dict):

            context.update({            context.update({

                'companyId': permissions.get('companyId', ''),                'companyId': permissions.get('companyId', ''),

                'storeId': permissions.get('storeId', ''),                'storeId': permissions.get('storeId', ''),

                'roleId': permissions.get('roleId', '')                'roleId': permissions.get('roleId', '')

            })            })

        elif isinstance(permissions, list):        elif isinstance(permissions, list):

            # Handle permissions as list            # Handle permissions as list

            for p in permissions:            for p in permissions:

                if isinstance(p, dict):                if isinstance(p, dict):

                    if not context.get('companyId') and p.get('companyId'):                    if not context.get('companyId') and p.get('companyId'):

                        context['companyId'] = p.get('companyId')                        context['companyId'] = p.get('companyId')

                    if not context.get('storeId') and p.get('storeId'):                    if not context.get('storeId') and p.get('storeId'):

                        context['storeId'] = p.get('storeId')                        context['storeId'] = p.get('storeId')

                    if not context.get('roleId') and p.get('roleId'):                    if not context.get('roleId') and p.get('roleId'):

                        context['roleId'] = p.get('roleId')                        context['roleId'] = p.get('roleId')

                

        # Ensure all values are strings and not None        # Ensure all values are strings and not None

        return {k: str(v) if v else '' for k, v in context.items()}        return {k: str(v) if v else '' for k, v in context.items()}

                

    except Exception as e:    except Exception as e:

        print(f"Warning: Failed to extract user context: {e}")        print(f"Warning: Failed to extract user context: {e}")

        return {        return {

            'userId': user_data.get('uid', ''),            'userId': user_data.get('uid', ''),

            'userEmail': '',            'userEmail': '',

            'userName': '',            'userName': '',

            'companyId': '',            'companyId': '',

            'storeId': '',            'storeId': '',

            'roleId': ''            'roleId': ''

        }        }





def _write_to_cloud_logging(log_entry: Dict[str, Any], user_context: Dict[str, str]) -> bool:def _write_to_cloud_logging(log_entry: Dict[str, Any], user_context: Dict[str, str]) -> bool:

    """Write log entry to Google Cloud Logging using service account"""    """Write log entry to Google Cloud Logging using service account"""

    if not logging_client:    if not logging_client:

        return False        return False

        

    try:    try:

        # Create structured log entry for Cloud Logging        # Create structured log entry for Cloud Logging

        severity_map = {        severity_map = {

            'DEBUG': 'DEBUG',            'DEBUG': 'DEBUG',

            'INFO': 'INFO',             'INFO': 'INFO', 

            'WARNING': 'WARNING',            'WARNING': 'WARNING',

            'ERROR': 'ERROR'            'ERROR': 'ERROR'

        }        }

                

        severity = severity_map.get(log_entry.get('severity', 'INFO'), 'INFO')        severity = severity_map.get(log_entry.get('severity', 'INFO'), 'INFO')

                

        # Prepare structured payload        # Prepare structured payload

        structured_payload = {        structured_payload = {

            'message': log_entry.get('message', ''),            'message': log_entry.get('message', ''),

            'level': log_entry.get('level', 'info'),            'level': log_entry.get('level', 'info'),

            'timestamp': log_entry.get('timestamp', datetime.now(timezone.utc).isoformat()),            'timestamp': log_entry.get('timestamp', datetime.now(timezone.utc).isoformat()),

            'user': user_context,            'user': user_context,

            'context': {            'context': {

                'area': log_entry.get('area', ''),                'area': log_entry.get('area', ''),

                'api': log_entry.get('api', ''),                'api': log_entry.get('api', ''),

                'collectionPath': log_entry.get('collectionPath', ''),                'collectionPath': log_entry.get('collectionPath', ''),

                'docId': log_entry.get('docId', ''),                'docId': log_entry.get('docId', ''),

                'correlationId': log_entry.get('correlationId', ''),                'correlationId': log_entry.get('correlationId', ''),

                'status': log_entry.get('status'),                'status': log_entry.get('status'),

                'success': log_entry.get('success'),                'success': log_entry.get('success'),

                'durationMs': log_entry.get('durationMs'),                'durationMs': log_entry.get('durationMs'),

            },            },

            'labels': log_entry.get('labels', {}),            'labels': log_entry.get('labels', {}),

            'payload': log_entry.get('payload'),            'payload': log_entry.get('payload'),

            'error': log_entry.get('error')            'error': log_entry.get('error')

        }        }

                

        # Remove empty/null values to keep logs clean        # Remove empty/null values to keep logs clean

        structured_payload = {k: v for k, v in structured_payload.items()         structured_payload = {k: v for k, v in structured_payload.items() 

                            if v is not None and v != '' and v != {}}                            if v is not None and v != '' and v != {}}

        structured_payload['context'] = {k: v for k, v in structured_payload['context'].items()         structured_payload['context'] = {k: v for k, v in structured_payload['context'].items() 

                                       if v is not None and v != ''}                                       if v is not None and v != ''}

                

        # Get logger for the application        # Get logger for the application

        logger = logging_client.logger("app-logs")        logger = logging_client.logger("app-logs")

                

        # Write structured log entry        # Write structured log entry

        logger.log_struct(        logger.log_struct(

            structured_payload,            structured_payload,

            severity=severity,            severity=severity,

            labels={            labels={

                'source': 'firebase-function',                'source': 'firebase-function',

                'function': 'app_logs',                'function': 'app_logs',

                'userId': user_context.get('userId', ''),                'userId': user_context.get('userId', ''),

                'storeId': user_context.get('storeId', ''),                'storeId': user_context.get('storeId', ''),

                'companyId': user_context.get('companyId', '')                'companyId': user_context.get('companyId', '')

            }            }

        )        )

                

        return True        return True

                

    except Exception as e:    except Exception as e:

        print(f"Cloud Logging write failed: {e}")        print(f"Cloud Logging write failed: {e}")

        return False        return False

    for f in REQUIRED_FIELDS:

        if f not in body:

REQUIRED_FIELDS = [            return f"Missing required field: {f}"

    "timestamp",    # basic type checks

    "level",     if not isinstance(body.get("message"), str):

    "severity",        return "Field 'message' must be a string"

    "message",    if body.get("status") not in (200, 400):

    "uid"  # Firebase UID instead of full auth        # allow 500 from UI too, but map to contract

]        if body.get("status") != 500:

            return "Field 'status' must be one of 200, 400, 500"

    if not isinstance(body.get("success"), bool):

def _validate_payload(body: Dict[str, Any]) -> str | None:        return "Field 'success' must be boolean"

    for f in REQUIRED_FIELDS:    return None

        if f not in body:

            return f"Missing required field: {f}"

    def _sanitize(body: Dict[str, Any]) -> Dict[str, Any]:

    # Basic type checks    # Ensure payload is JSON-serializable and keep size reasonable

    if not isinstance(body.get("message"), str):    out = dict(body)

        return "Field 'message' must be a string"    # Truncate large fields defensively

        msg = out.get("message")

    if not isinstance(body.get("uid"), str) or not body.get("uid").strip():    if isinstance(msg, str) and len(msg) > 2000:

        return "Field 'uid' must be a non-empty string"        out["message"] = msg[:2000] + "…"

        payload = out.get("payload")

    # Optional field validations    if isinstance(payload, (dict, list)):

    if "status" in body and body.get("status") not in (200, 400, 500):        try:

        return "Field 'status' must be one of 200, 400, 500"            dumps = json.dumps(payload)

                if len(dumps) > 20000:

    if "success" in body and not isinstance(body.get("success"), bool):                out["payload"] = {"_note": "truncated", "size": len(dumps)}

        return "Field 'success' must be boolean"        except Exception:

                out["payload"] = {"_note": "non-serializable"}

    return None    return out





def _sanitize(body: Dict[str, Any]) -> Dict[str, Any]:@https_fn.on_request(region="asia-east1")

    # Ensure payload is JSON-serializable and keep size reasonabledef app_logs(req: https_fn.Request) -> https_fn.Response:

    out = dict(body)    origin = req.headers.get("Origin")

    

    # Truncate large fields defensively    # Handle CORS preflight

    msg = out.get("message")    if req.method == "OPTIONS":

    if isinstance(msg, str) and len(msg) > 2000:        return https_fn.Response("", status=204, headers=_cors_headers(origin))

        out["message"] = msg[:2000] + "…"

        if req.method != "POST":

    payload = out.get("payload")        return _bad_request("Only POST is supported", origin)

    if isinstance(payload, (dict, list)):

        try:    if not _validate_api_key(req):

            dumps = json.dumps(payload)        return https_fn.Response(json.dumps({"ok": False, "error": "Unauthorized"}), status=401, headers=_cors_headers(origin))

            if len(dumps) > 20000:

                out["payload"] = {"_note": "truncated", "size": len(dumps)}    content_type = (req.headers.get("Content-Type") or "").lower()

        except Exception:    if "application/json" not in content_type:

            out["payload"] = {"_note": "non-serializable"}        return _bad_request("Content-Type must be application/json", origin)

    

    return out    try:

        body = req.get_json(silent=False)

    except Exception:

@https_fn.on_request(region="asia-east1")        return _bad_request("Invalid JSON body", origin)

def app_logs(req: https_fn.Request) -> https_fn.Response:

    origin = req.headers.get("Origin")    if not isinstance(body, dict):

        return _bad_request("JSON body must be an object", origin)

    # Handle CORS preflight

    if req.method == "OPTIONS":    err = _validate_payload(body)

        return https_fn.Response("", status=204, headers=_cors_headers(origin))    if err:

        return _bad_request(err, origin)

    if req.method != "POST":

        return _bad_request("Only POST is supported", origin)    # Sanitize and enrich

    log_entry = _sanitize(body)

    if not _validate_api_key(req):

        return https_fn.Response(json.dumps({"ok": False, "error": "Unauthorized"}), status=401, headers=_cors_headers(origin))    # Add server-side metadata

    # If Authorization header is provided with a Firebase ID token, we don't verify here by default

    content_type = (req.headers.get("Content-Type") or "").lower()    # to keep the endpoint simple; an API key can be used instead when needed.

    if "application/json" not in content_type:

        return _bad_request("Content-Type must be application/json", origin)    try:

        db = firestore.client()

    try:        db.collection("appLogs").add(log_entry)

        body = req.get_json(silent=False)    except Exception as e:

    except Exception:        # If Firestore write fails, still acknowledge to avoid blocking UI; log server-side error

        return _bad_request("Invalid JSON body", origin)        print(f"app-logs Firestore write failed: {e}")

        # best-effort OK to keep UI smooth, but include error response for observability

    if not isinstance(body, dict):        return _server_error("Failed to persist log", origin)

        return _bad_request("JSON body must be an object", origin)

    return _ok(origin)

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

    # Sanitize and enrich the log entry
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
        # Log the error but still return success to avoid blocking UI
        print(f"❌ Logging write failed: {e}")
        return _server_error(f"Failed to write log: {str(e)}", origin)

    return _ok(origin)