import os
from google.cloud import bigquery

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\MVP\POSFunctionPy\functions\service-account.json'

client = bigquery.Client(project='jasperpos-1dfd5', location='asia-east1')

# Check if your Americano product was inserted
query = """
SELECT productId, productName, totalStock, sellingPrice, createdAt, updatedAt, barcodeId
FROM `tovrika_pos.products`
WHERE productId = 'aXsTBL2bQVRrQ8dK0gzi'
"""

results = client.query(query)
rows = list(results)

print('=== AMERICANO PRODUCT INSERT VERIFICATION ===')
if rows:
    row = rows[0]
    print(f'✅ FOUND: Product inserted successfully!')
    print(f'ID: {row.productId}')
    print(f'Name: {row.productName}')
    print(f'Stock: {row.totalStock}')
    print(f'Price: {row.sellingPrice}')
    print(f'Barcode: {row.barcodeId}')
    print(f'Created: {row.createdAt}')
    print(f'Updated: {row.updatedAt}')
    print()
    print('🎉 Products INSERT trigger worked perfectly!')
else:
    print('❌ Product not found - insert trigger may have failed')

# Also check recent inserts
query2 = """
SELECT productId, productName, totalStock, createdAt
FROM `tovrika_pos.products`
WHERE createdAt >= '2025-11-04 16:00:00'
ORDER BY createdAt DESC
"""

results2 = client.query(query2)
rows2 = list(results2)

print('\n=== RECENT PRODUCT INSERTS (after 16:00 UTC) ===')
if rows2:
    for row in rows2:
        print(f'ID: {row.productId}, Name: {row.productName}, Stock: {row.totalStock}, Created: {row.createdAt}')
else:
    print('❌ No recent product inserts found')