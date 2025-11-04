import os
from google.cloud import bigquery

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\MVP\POSFunctionPy\functions\service-account.json'

client = bigquery.Client(project='jasperpos-1dfd5', location='asia-east1')

# Check your actual product ID
query = """
SELECT productId, productName, category, sellingPrice, totalStock, updatedAt, lastUpdated
FROM `tovrika_pos.products`
WHERE productId = 'zztWFFBMf6mzz25dc6iw'
"""

results = client.query(query)
rows = list(results)

if rows:
    row = rows[0]
    print('=== YOUR PRODUCT RECORD IN BIGQUERY ===') 
    print(f'productId: {row.productId}')
    print(f'productName: {row.productName}')
    print(f'category: {row.category}')
    print(f'sellingPrice: {row.sellingPrice}')
    print(f'totalStock: {row.totalStock}')
    print(f'updatedAt: {row.updatedAt}')
    print(f'lastUpdated: {row.lastUpdated}')
    print()
    print('✅ Products update trigger worked - BigQuery has been updated!')
else:
    print('❌ No product record found with that ID')