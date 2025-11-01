# posfunctionpy

## Cloud Functions (Python)

Deployed endpoints:

- BigQuery APIs
	- get_orders_by_store_bq (asia-east1)
	- get_order_details_bq (asia-east1)
	- get_orders_by_date_bq (asia-east1)
- Firestore → BigQuery Triggers
	- sync_order_to_bigquery (asia-east1)
	- sync_order_details_to_bigquery (asia-east1)
- App Logs
	- app_logs (asia-east1): HTTP endpoint for structured UI logs

Docs:
- docs/cloud-logging-endpoint.md — contract, examples, and configuration for `app_logs`
