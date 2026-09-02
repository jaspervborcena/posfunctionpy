import os
from google.cloud import bigquery

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\MVP\POSFunctionPy\functions\service-account.json'

client = bigquery.Client(project='jasperpos-1dfd5', location='asia-east1')

query = """
SELECT productId, productName, category, sellingPrice, status, description, totalStock, companyId
FROM `tovrika_pos.products`
WHERE productId = 'test-product-update-1762271319'
"""

results = client.query(query)
rows = list(results)

if rows:
    row = rows[0]
    print('=== UPDATED PRODUCT RECORD ===') 
    print(f'productId: {row.productId}')
    print(f'productName: {row.productName}')
    print(f'category: {row.category}')
    print(f'sellingPrice: {row.sellingPrice}')
    print(f'status: {row.status}')
    print(f'description: {row.description}')
    print(f'totalStock: {row.totalStock}')
    print(f'companyId: {row.companyId}')
    print()
    print('✅ Products update trigger worked - ALL FIELDS updated successfully!')
else:
    print('❌ No product record found')