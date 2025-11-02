import json
import sys
import requests
from firebase_admin import credentials, initialize_app, auth, firestore

# Config - update as needed
SERVICE_ACCOUNT_PATH = "functions/service-account.json"
FIREBASE_API_KEY = "AIzaSyDNIYovvzNKVj40h99kxOHu5yfEUzx7OYA"  # web API key (safe)
BACKFILL_URL = "https://backfill-products-bq-7bpeqovfmq-de.a.run.app"


def main():
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        initialize_app(cred)
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Failed to initialize firebase admin: {e}"}))
        sys.exit(1)

    try:
        # Use the UID provided by the user which corresponds to an existing Firebase user
        uid = "ZQKZPAKaUAcvMZ8BwKrdpkVGTlA3"

        # Ensure a minimal user document exists in Firestore so the app's
        # auth middleware (which looks up users by uid) will find it.
        try:
            db = firestore.client()
            users_ref = db.collection('users')
            user_doc_ref = users_ref.document(uid)
            doc = user_doc_ref.get()
            if doc.exists:
                print(f"Firestore user document already exists for UID: {uid}, skipping create")
            else:
                minimal_user = {
                    'uid': uid,
                    'email': 'service-account@jasperpos-1dfd5.iam.gserviceaccount.com',
                    'displayName': 'Service Account Caller',
                    'status': 'active',
                    'permissions': {
                        # creator role grants access across company/stores per middleware
                        'roleId': 'creator'
                    }
                }
                user_doc_ref.set(minimal_user, merge=True)
                print(f"Created Firestore user document for UID: {uid}")
        except Exception as e:
            print(json.dumps({"success": False, "error": f"Failed to ensure user doc: {e}"}))
            sys.exit(1)

        custom_token = auth.create_custom_token(uid)
        # custom_token is bytes
        custom_token_str = custom_token.decode('utf-8')
        print("Got custom token")
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Failed to create custom token: {e}"}))
        sys.exit(1)

    try:
        # Exchange custom token for ID token
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_API_KEY}"
        payload = {"token": custom_token_str, "returnSecureToken": True}
        res = requests.post(url, json=payload)
        res.raise_for_status()
        data = res.json()
        id_token = data.get('idToken')
        if not id_token:
            print(json.dumps({"success": False, "error": "No idToken in response", "resp": data}))
            sys.exit(1)
        print("Exchanged custom token for idToken")
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Failed to exchange custom token: {e}", "resp_text": getattr(e, 'response', None).text if getattr(e, 'response', None) is not None else None}))
        sys.exit(1)

    try:
        headers = {"Authorization": f"Bearer {id_token}", "Content-Type": "application/json"}
        # Try to pull storeId from the user's Firestore document permissions
        try:
            db = firestore.client()
            user_doc = db.collection('users').document(uid).get()
            user_data = user_doc.to_dict() if user_doc and user_doc.exists else {}
            perms = user_data.get('permissions') or {}
            if isinstance(perms, list):
                # defensive: merge list into dict
                merged = {}
                for item in perms:
                    if isinstance(item, dict):
                        merged.update(item)
                perms = merged
            store_id = perms.get('storeId') if isinstance(perms, dict) else None
        except Exception:
            store_id = None

        body = {"mode": "last2weeks"}
        if store_id:
            body['storeId'] = store_id

        r = requests.post(BACKFILL_URL, json=body, headers=headers)
        # Print response status and body
        try:
            j = r.json()
        except Exception:
            j = {"text": r.text}
        print(json.dumps({"status_code": r.status_code, "response": j}))
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Failed to call backfill endpoint: {e}"}))
        sys.exit(1)


if __name__ == '__main__':
    main()
