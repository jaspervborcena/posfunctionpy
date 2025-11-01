from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict

import requests
from firebase_functions import https_fn

PAYPAL_BASE = os.getenv("PAYPAL_BASE", "https://api-m.sandbox.paypal.com")


def _get_paypal_credentials() -> Dict[str, str]:
    client_id = os.getenv("PAYPAL_CLIENT_ID")
    client_secret = os.getenv("PAYPAL_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing PayPal credentials. Set env PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET."
        )
    return {"client_id": client_id, "client_secret": client_secret}


def _get_access_token() -> str:
    creds = _get_paypal_credentials()
    auth = base64.b64encode(f"{creds['client_id']}:{creds['client_secret']}".encode()).decode()
    url = f"{PAYPAL_BASE}/v1/oauth2/token"
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    resp = requests.post(url, headers=headers, data="grant_type=client_credentials", timeout=30)
    if not resp.ok:
        raise RuntimeError(f"PayPal auth failed: {resp.status_code} {resp.text}")
    data = resp.json()
    return data.get("access_token")


@https_fn.on_request(region="asia-east1")
def paypal_create_order(req: https_fn.Request) -> https_fn.Response:
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        })
    if req.method != "POST":
        return https_fn.Response(json.dumps({"error": "Invalid method"}), status=405)
    try:
        body = req.get_json(silent=True) or {}
        amount = body.get("amount")
        currency = body.get("currency", "PHP")
        description = body.get("description", "Subscription payment")
        if not amount or float(amount) <= 0:
            return https_fn.Response(json.dumps({"error": "Invalid amount"}), status=400)
        access_token = _get_access_token()
        order_body = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {"currency_code": currency, "value": str(amount)},
                    "description": description,
                }
            ],
        }
        r = requests.post(
            f"{PAYPAL_BASE}/v2/checkout/orders",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            json=order_body,
            timeout=30,
        )
        data = r.json() if r.text else {}
        status = 200 if r.ok else 500
        return https_fn.Response(json.dumps(data), status=status, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"})
    except Exception as e:
        return https_fn.Response(json.dumps({"error": str(e)}), status=500, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"})


@https_fn.on_request(region="asia-east1")
def paypal_capture_order(req: https_fn.Request) -> https_fn.Response:
    if req.method == "OPTIONS":
        return https_fn.Response("", status=204, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        })
    if req.method != "POST":
        return https_fn.Response(json.dumps({"error": "Invalid method"}), status=405)
    try:
        body = req.get_json(silent=True) or {}
        order_id = body.get("orderId")
        if not order_id:
            return https_fn.Response(json.dumps({"error": "Missing orderId"}), status=400)
        access_token = _get_access_token()
        r = requests.post(
            f"{PAYPAL_BASE}/v2/checkout/orders/{order_id}/capture",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            timeout=30,
        )
        data = r.json() if r.text else {}
        status = 200 if r.ok else 500
        return https_fn.Response(json.dumps(data), status=status, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"})
    except Exception as e:
        return https_fn.Response(json.dumps({"error": str(e)}), status=500, headers={"Access-Control-Allow-Origin": "*", "Content-Type": "application/json"})
