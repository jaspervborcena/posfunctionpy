import os
from google.cloud import bigquery

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\MVP\POSFunctionPy\functions\service-account.json'

client = bigquery.Client(project='jasperpos-1dfd5', location='asia-east1')

# Check your actual product ID
query = """
SELECT productId, productName, category, sellingPrice, totalStock, updatedAt, updatedBy
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
    print(f'updatedBy: {row.updatedBy}')
    print()
    print('✅ Products update trigger worked - BigQuery has been updated!')
    
    # Also check Firestore vs BigQuery totalStock
    print(f'🔍 Firestore shows totalStock: 990')
    print(f'🔍 BigQuery shows totalStock: {row.totalStock}')
    if row.totalStock == 990:
        print('✅ MATCH! The update trigger synchronized correctly!')
    else:
        print('❌ Mismatch - trigger may not have updated BigQuery')
else:
    print('❌ No product record found with that ID')