from __future__ import annotations

import json
import os
from typing import Any, Dict

from firebase_functions import https_fn
from firebase_admin import firestore

# Basic CORS helpers
ALLOWED_ORIGINS = os.getenv("CLOUD_LOGGING_ALLOWED_ORIGINS", "*")
REQUIRE_API_KEY = os.getenv("CLOUD_LOGGING_REQUIRE_API_KEY", "false").lower() in ("1", "true", "yes")
API_KEY = os.getenv("CLOUD_LOGGING_API_KEY")


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


REQUIRED_FIELDS = [
    "timestamp",
    "level",
    "severity",
    "message",
    "status",
    "success",
]


def _validate_payload(body: Dict[str, Any]) -> str | None:
    for f in REQUIRED_FIELDS:
        if f not in body:
            return f"Missing required field: {f}"
    # basic type checks
    if not isinstance(body.get("message"), str):
        return "Field 'message' must be a string"
    if body.get("status") not in (200, 400):
        # allow 500 from UI too, but map to contract
        if body.get("status") != 500:
            return "Field 'status' must be one of 200, 400, 500"
    if not isinstance(body.get("success"), bool):
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

    # Sanitize and enrich
    log_entry = _sanitize(body)

    # Add server-side metadata
    # If Authorization header is provided with a Firebase ID token, we don't verify here by default
    # to keep the endpoint simple; an API key can be used instead when needed.

    try:
        db = firestore.client()
        db.collection("appLogs").add(log_entry)
    except Exception as e:
        # If Firestore write fails, still acknowledge to avoid blocking UI; log server-side error
        print(f"app-logs Firestore write failed: {e}")
        # best-effort OK to keep UI smooth, but include error response for observability
        return _server_error("Failed to persist log", origin)

    return _ok(origin)
