from google.cloud import bigquery

TEST_IDS = ['test-orderdetails-robot-20251104-1','test-orderdetails-robot-20251104-2']
PROJECT = 'jasperpos-1dfd5'
DATASET = 'tovrika_pos'
TABLE = 'orderDetails'

client = bigquery.Client(project=PROJECT)
ids = ','.join([f"'{i}'" for i in TEST_IDS])
query = f"SELECT orderDetailsId, orderId, items FROM `{PROJECT}.{DATASET}.{TABLE}` WHERE orderDetailsId IN ({ids})"
print('Running query:', query)

job = client.query(query)
rows = list(job.result())
print('Found rows:', len(rows))
for r in rows:
    print(dict(r))
