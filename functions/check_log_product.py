import os
from google.cloud import bigquery

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\MVP\POSFunctionPy\functions\service-account.json'

client = bigquery.Client(project='jasperpos-1dfd5', location='asia-east1')

# Check if the product from the logs exists in BigQuery
query = """
SELECT productId, productName, totalStock, updatedAt, barcodeId, companyId
FROM `tovrika_pos.products`
WHERE productId = 'zztWFFBMf6mzz25dc6iw'
"""

results = client.query(query)
rows = list(results)

print('=== CHECKING LOG PRODUCT ID ===')
if rows:
    row = rows[0]
    print(f'✅ FOUND: ID: {row.productId}, Name: {row.productName}, Stock: {row.totalStock}')
    print(f'   Updated: {row.updatedAt}, Barcode: {row.barcodeId}')
    if row.totalStock == 990:
        print('🎉 SUCCESS! The trigger updated BigQuery with totalStock 990!')
    else:
        print(f'❌ Stock mismatch: Expected 990, got {row.totalStock}')
else:
    print('❌ Product zztWFFBMf6mzz25dc6iw not found in BigQuery')

# Check ALL products with your companyId
query2 = """
SELECT productId, productName, totalStock, updatedAt, barcodeId
FROM `tovrika_pos.products`
WHERE companyId = 'fuREf6Lixrhhi2qiAa5N'
ORDER BY updatedAt DESC
"""

results2 = client.query(query2)
rows2 = list(results2)

print('\n=== ALL PRODUCTS FOR YOUR COMPANY ===')
if rows2:
    for row in rows2:
        print(f'ID: {row.productId}, Name: {row.productName}, Stock: {row.totalStock}, Barcode: {row.barcodeId}')
        print(f'   Updated: {row.updatedAt}')
        print()
else:
    print('❌ No products found for your company')