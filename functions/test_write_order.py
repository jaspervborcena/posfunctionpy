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

    doc_id = f"test-order-robot-{int(time.time())}"
    now = datetime.utcnow()

    # Build a test order payload matching expected fields, including payments as a nested dict
    payload = {
        "assignedCashierEmail": "robot@tests",
        "assignedCashierId": "cashier_robot",
        "assignedCashierName": "Robot Cashier",
        "atpOrOcn": None,
        "birPermitNo": None,
        "cashSale": True,
        "companyAddress": "123 Test St",
        "companyEmail": "company@test",
        "companyId": "company_test",
        "companyName": "TestCo",
        "companyPhone": "1234567890",
        "companyTaxId": "TAX123",
        "createdAt": now,
        "createdBy": "robot@test",
        "customerInfo": {
            "address": "Customer Addr",
            "customerId": "cust_123",
            "fullName": "Test Customer",
            "tin": "TIN123"
        },
        "date": now,
        "discountAmount": 0.0,
        "grossAmount": 100.0,
        "inclusiveSerialNumber": None,
        "invoiceNumber": "INV-TEST-001",
        "message": "test order",
        "netAmount": 88.0,
        "payments": {
            "amountTendered": 100.0,
            "changeAmount": 12.0,
            "paymentDescription": "cash"
        },
        "status": "active",
        "storeId": "store_1",
        "totalAmount": 100.0,
        "uid": "robot_user",
        "updatedAt": now,
        "updatedBy": "robot@test",
        "vatAmount": 12.0,
        "vatExemptAmount": 0.0,
        "vatableSales": 88.0,
        "zeroRatedSales": 0.0
    }

    print(f"Writing test document to orders/{doc_id}")
    try:
        db.collection('orders').document(doc_id).set(payload)
        print("Write succeeded")
        print(json.dumps({"docId": doc_id, "payload": payload}, default=str, indent=2))
        return 0
    except Exception as e:
        print("Write failed:", e)
        return 3


if __name__ == '__main__':
    exit(main())
