import json
import sys
from firebase_admin import credentials, initialize_app, firestore

SERVICE_ACCOUNT_PATH = "functions/service-account.json"
UID = "ZQKZPAKaUAcvMZ8BwKrdpkVGTlA3"

try:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    initialize_app(cred)
except Exception as e:
    print(json.dumps({"error": f"Failed to init firebase admin: {e}"}))
    sys.exit(1)

try:
    db = firestore.client()
    doc = db.collection('users').document(UID).get()
    if not doc.exists:
        print(json.dumps({"found": False, "message": f"No user doc for UID {UID}"}))
    else:
        data = doc.to_dict()
        print(json.dumps({"found": True, "uid": UID, "doc": data}, default=str, indent=2))
except Exception as e:
    print(json.dumps({"error": f"Failed to read user doc: {e}"}))
    sys.exit(1)
