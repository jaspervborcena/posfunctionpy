from google.cloud import firestore
from datetime import datetime

TOP_ID = 'test-orderdetails-robot-20251104-1'
SUB_ID = 'test-orderdetails-robot-20251104-2'
ORDER_ID = 'test-order-robot-20251104'

def write_docs():
    db = firestore.Client()
    # top-level
    top_ref = db.collection('orderDetails').document(TOP_ID)
    top_ref.set({
        'companyId': 'test-co',
        'orderId': ORDER_ID,
        'storeId': 'store-1',
        'items': [{'productId':'sku-1','productName':'Tst Top','quantity':1,'price':9.99,'total':9.99}],
        'createdAt': datetime.utcnow(),
        'updatedAt': datetime.utcnow()
    })
    print('WROTE_TOP', TOP_ID)

    # nested subcollection
    sub_ref = db.collection('orders').document(ORDER_ID).collection('orderDetails').document(SUB_ID)
    sub_ref.set({
        'companyId': 'test-co',
        'orderId': ORDER_ID,
        'storeId': 'store-1',
        'items': [{'productId':'sku-2','productName':'Tst Sub','quantity':2,'price':4.5,'total':9.0}],
        'createdAt': datetime.utcnow(),
        'updatedAt': datetime.utcnow()
    })
    print('WROTE_SUB', SUB_ID)

if __name__ == '__main__':
    write_docs()
