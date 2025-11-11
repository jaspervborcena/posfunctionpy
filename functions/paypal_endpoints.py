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


# paypal_create_order and paypal_capture_order endpoints removed per cleanup.
# Helper functions remain for future PayPal integrations if reintroduced.


# paypal_create_order and paypal_capture_order endpoints removed per cleanup.
# Helper functions remain for future PayPal integrations if reintroduced.
