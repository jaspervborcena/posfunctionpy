import json
import sys
from firebase_admin import credentials, initialize_app, firestore

SERVICE_ACCOUNT_PATH = "functions/service-account.json"
UID = "ZQKZPAKaUAcvMZ8BwKrdpkVGTlA3"

try:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    initialize_app(cred)
except Exception as e:
    print(json.dumps({"success": False, "error": f"Failed to init firebase admin: {e}"}))
    sys.exit(1)

try:
    db = firestore.client()
    doc_ref = db.collection('users').document(UID)
    doc = doc_ref.get()
    if not doc.exists:
        print(json.dumps({"success": False, "error": f"User doc {UID} not found"}))
        sys.exit(1)

    data = doc.to_dict()
    print(json.dumps({"found": True, "doc_before": data}, default=str))

    # Normalize permissions to a dict
    perms = data.get('permissions')
    if isinstance(perms, list):
        # Try to merge list items into a single dict
        merged = {}
        for item in perms:
            if isinstance(item, dict):
                merged.update(item)
        perms = merged
    elif isinstance(perms, dict):
        # already fine
        perms = perms
    else:
        perms = {}

    if 'roleId' not in perms:
        perms['roleId'] = 'creator'

    # Update the document
    doc_ref.update({'permissions': perms})
    doc2 = doc_ref.get().to_dict()
    print(json.dumps({"success": True, "doc_after": doc2}, default=str))

except Exception as e:
    print(json.dumps({"success": False, "error": f"Failed to update user doc: {e}"}))
    sys.exit(1)
