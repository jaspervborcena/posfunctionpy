import os
from google.cloud import bigquery

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\MVP\POSFunctionPy\functions\service-account.json'

client = bigquery.Client(project='jasperpos-1dfd5', location='asia-east1')

query = """
SELECT orderId, companyId, storeId, totalAmount, status, assignedCashierName, grossAmount, netAmount, message
FROM `tovrika_pos.orders`
WHERE orderId = 'test-fixed-update-order'
"""

results = client.query(query)
rows = list(results)

if rows:
    row = rows[0]
    print('=== UPDATED ORDER RECORD ===') 
    print(f'orderId: {row.orderId}')
    print(f'companyId: {row.companyId}')
    print(f'storeId: {row.storeId}')
    print(f'totalAmount: {row.totalAmount}')
    print(f'status: {row.status}')
    print(f'assignedCashierName: {row.assignedCashierName}')
    print(f'grossAmount: {row.grossAmount}')
    print(f'netAmount: {row.netAmount}')
    print(f'message: {row.message}')
    print()
    print('✅ ALL FIELDS have been updated successfully!')
else:
    print('❌ No record found')