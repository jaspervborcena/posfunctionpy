from __future__ import annotations

import base64
import json
import os
from decimal import Decimal, InvalidOperation
from typing import Any, Dict

import requests
from firebase_functions import https_fn

from auth_middleware import require_auth
from config import get_cloud_function_base_url, get_paypal_base_url, is_dev_environment

PAYPAL_BASE = get_paypal_base_url()


def _json_response(payload: Dict[str, Any], status: int = 200) -> https_fn.Response:
    return https_fn.Response(
        json.dumps(payload),
        status=status,
        headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
    )


def _get_paypal_credentials() -> Dict[str, str]:
    if is_dev_environment():
        client_id = os.getenv("PAYPAL_CLIENT_ID_SANDBOX") or os.getenv("PAYPAL_CLIENT_ID")
        client_secret = os.getenv("PAYPAL_CLIENT_SECRET_SANDBOX") or os.getenv("PAYPAL_CLIENT_SECRET")
        mode = "sandbox"
    else:
        client_id = os.getenv("PAYPAL_CLIENT_ID_LIVE") or os.getenv("PAYPAL_CLIENT_ID")
        client_secret = os.getenv("PAYPAL_CLIENT_SECRET_LIVE") or os.getenv("PAYPAL_CLIENT_SECRET")
        mode = "live"

    if not client_id or not client_secret:
        raise RuntimeError(
            f"Missing PayPal {mode} credentials. Set the environment variables for this deployment."
        )
    return {"client_id": client_id, "client_secret": client_secret}


def _get_access_token() -> str:
    creds = _get_paypal_credentials()
    auth = base64.b64encode(f"{creds['client_id']}:{creds['client_secret']}".encode()).decode()
    url = f"{PAYPAL_BASE}/v1/oauth2/token"
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Accept-Language": "en_US",
    }
    resp = requests.post(url, headers=headers, data="grant_type=client_credentials", timeout=30)
    if not resp.ok:
        raise RuntimeError(f"PayPal auth failed: {resp.status_code} {resp.text}")

    data = resp.json()
    access_token = data.get("access_token")
    if not access_token:
        raise RuntimeError("PayPal did not return an access token.")
    return access_token


def _parse_json(req: https_fn.Request) -> Dict[str, Any]:
    try:
        data = req.get_json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_request_value(req: https_fn.Request, body: Dict[str, Any], key: str, default: Any = None) -> Any:
    if key in body and body.get(key) not in (None, ""):
        return body.get(key)
    if hasattr(req, "args") and req.args:
        value = req.args.get(key)
        if value not in (None, ""):
            return value
    return default


def _normalize_amount(value: Any) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid amount")

    if amount <= 0:
        raise ValueError("Invalid amount")

    return f"{amount:.2f}"


def _safe_json(resp: requests.Response) -> Dict[str, Any]:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"data": data}
    except Exception:
        return {"raw": resp.text}


@https_fn.on_request(cors=True, region="asia-east1")
@require_auth
def paypal_client_config(req: https_fn.Request) -> https_fn.Response:
    """Return the safe PayPal client config for authenticated users."""
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204)

    if req.method != "GET":
        return _json_response({"error": "Method not allowed"}, 405)

    client_id = os.getenv("PAYPAL_CLIENT_ID")
    if not client_id:
        return _json_response({"error": "PayPal client configuration is missing"}, 500)

    function_base_url = get_cloud_function_base_url()

    return _json_response(
        {
            "clientId": client_id,
            "sandbox": "sandbox" in PAYPAL_BASE,
            "environment": "dev" if is_dev_environment() else "prod",
            "apiBase": PAYPAL_BASE,
            "functionBaseUrl": function_base_url,
            "createOrderUrl": f"{function_base_url}/paypal_create_order",
            "captureOrderUrl": f"{function_base_url}/paypal_capture_order",
        }
    )


@https_fn.on_request(cors=True, region="asia-east1")
@require_auth
def paypal_create_order(req: https_fn.Request) -> https_fn.Response:
    """Create a PayPal order for an authenticated Firebase user."""
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204)

    if req.method != "POST":
        return _json_response({"error": "Method not allowed"}, 405)

    try:
        body = _parse_json(req)
        amount = _normalize_amount(_get_request_value(req, body, "amount"))
        currency = str(_get_request_value(req, body, "currency", "PHP")).upper()
        description = str(_get_request_value(req, body, "description", "Subscription payment"))[:127]

        user = getattr(req, "user", {}) or {}
        access_token = _get_access_token()

        order_body = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": currency,
                        "value": amount,
                    },
                    "description": description,
                    "custom_id": str(user.get("uid") or user.get("doc_id") or ""),
                }
            ],
        }

        resp = requests.post(
            f"{PAYPAL_BASE}/v2/checkout/orders",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            json=order_body,
            timeout=30,
        )
        data = _safe_json(resp)

        if not resp.ok:
            return _json_response({"error": "create-order-failed", "details": data}, 500)

        return _json_response(data)

    except ValueError as exc:
        return _json_response({"error": str(exc)}, 400)
    except Exception as exc:
        print(f"create-order error: {exc}")
        return _json_response({"error": str(exc) or "server-error"}, 500)


@https_fn.on_request(cors=True, region="asia-east1")
@require_auth
def paypal_capture_order(req: https_fn.Request) -> https_fn.Response:
    """Capture a PayPal order for an authenticated Firebase user."""
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204)

    if req.method != "POST":
        return _json_response({"error": "Method not allowed"}, 405)

    try:
        body = _parse_json(req)
        order_id = body.get("orderId")
        if not order_id:
            return _json_response({"error": "Missing orderId"}, 400)

        access_token = _get_access_token()
        resp = requests.post(
            f"{PAYPAL_BASE}/v2/checkout/orders/{order_id}/capture",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            timeout=30,
        )
        data = _safe_json(resp)

        if not resp.ok:
            return _json_response({"error": "capture-order-failed", "details": data}, 500)

        return _json_response(data)

    except Exception as exc:
        print(f"capture-order error: {exc}")
        return _json_response({"error": str(exc) or "server-error"}, 500)

