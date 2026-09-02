import os
from google.cloud import bigquery

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\MVP\POSFunctionPy\functions\service-account.json'

client = bigquery.Client(project='jasperpos-1dfd5', location='asia-east1')

# Check what products exist in BigQuery
query = """
SELECT productId, productName, totalStock, updatedAt
FROM `tovrika_pos.products`
ORDER BY updatedAt DESC
LIMIT 10
"""

results = client.query(query)
rows = list(results)

print('=== ALL PRODUCTS IN BIGQUERY (Latest 10) ===')
if rows:
    for row in rows:
        print(f'ID: {row.productId}, Name: {row.productName}, Stock: {row.totalStock}, Updated: {row.updatedAt}')
else:
    print('❌ No products found in BigQuery table')

# Also check specifically for your product name "Americano"
query2 = """
SELECT productId, productName, totalStock, updatedAt, barcodeId
FROM `tovrika_pos.products`
WHERE productName = 'Americano' OR barcodeId = '2323'
ORDER BY updatedAt DESC
"""

results2 = client.query(query2)
rows2 = list(results2)

print('\n=== AMERICANO PRODUCTS ===')
if rows2:
    for row in rows2:
        print(f'ID: {row.productId}, Name: {row.productName}, Stock: {row.totalStock}, Barcode: {row.barcodeId}, Updated: {row.updatedAt}')
else:
    print('❌ No Americano products found')