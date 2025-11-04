import os
import time
import json
from datetime import datetime

try:
    from firebase_admin import credentials, initialize_app, firestore
except Exception as e:
    print("ERROR: firebase_admin not installed or failed to import:", e)
    raise


def main():
    # Try service account first, then ADC
    cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    cred = None
    try:
        if cred_path and os.path.exists(cred_path):
            print(f"Using service account from: {cred_path}")
            cred = credentials.Certificate(cred_path)
        else:
            print("No service account env var set or file not found; trying Application Default Credentials...")
            cred = credentials.ApplicationDefault()
    except Exception as e:
        print("Failed to obtain credentials:", e)
        return 2

    try:
        initialize_app(cred)
    except Exception as e:
        # initialize_app may be called multiple times in same process; ignore that error
        print("initialize_app warning/info:", e)

    db = firestore.client()

    doc_id = f"test-orderdetails-robot-{int(time.time())}"
    now = datetime.utcnow()

    payload = {
        "batchNumber": 1,
        "companyId": "company_test",
        "createdAt": now,
        "createdBy": "robot@test",
        "orderId": "order_test_123",
        "storeId": "store_1",
        "uid": "robot_user",
        "updatedAt": now,
        "updatedBy": "robot@test",
        "items": [
            {
                "productId": "prod_1",
                "productName": "Widget A",
                "quantity": 2,
                "price": 100,
                "discount": 0,
                "vat": 12,
                "isVatExempt": False,
                "total": 224
            }
        ]
    }

    print(f"Writing test document to orderDetails/{doc_id}")
    try:
        db.collection('orderDetails').document(doc_id).set(payload)
        print("Write succeeded")
        print(json.dumps({"docId": doc_id, "payload": payload}, default=str, indent=2))
        return 0
    except Exception as e:
        print("Write failed:", e)
        return 3


if __name__ == '__main__':
    exit(main())
