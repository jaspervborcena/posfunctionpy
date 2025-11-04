from google.cloud import logging as cloud_logging
import os

client = cloud_logging.Client()
logger = client.logger('')

# We'll use a filter to find logs mentioning our test IDs or the function name
filter_str = ('resource.type="cloud_run_revision" AND '
              '(textPayload:"test-orderdetails-robot-20251104-2" OR '
              'textPayload:"test-orderdetails-robot-20251104-1" OR '
              'resource.labels.service_name:"sync-order-details" OR '
              'resource.labels.revision_name:"sync-order-details" OR '
              'textPayload:"orderDetails payload" OR textPayload:"Order Detail" )')

print('Using filter:')
print(filter_str)
entries = client.list_entries(filter_=filter_str, page_size=50)
count = 0
for e in entries:
    count += 1
    ts = getattr(e, 'timestamp', None)
    payload = None
    if hasattr(e, 'payload'):
        payload = e.payload
    print('---')
    print('timestamp:', ts)
    print('payload:', payload)
    if count >= 50:
        break

print('Total entries returned (capped at 50):', count)
