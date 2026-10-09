# posfunctionpy

## Cloud Functions (Python)

Deployed endpoints:

- BigQuery APIs
	- get_orders_by_store_bq (asia-east1)
	- get_order_details_bq (asia-east1)
	- get_orders_by_date_bq (asia-east1)
	- get_sales_summary_details_bq (asia-east1)
	- get_sales_summary_order_details_bq (asia-east1)
- Firestore → BigQuery Triggers
	- sync_order_to_bigquery (asia-east1)
	- sync_order_details_to_bigquery (asia-east1)
- App Logs
	- app_logs (asia-east1): HTTP endpoint for structured UI logs

## TODO

- [ ] Extend `get_sales_summary_bq` to accept a named period (`today`, `yesterday`, `this_week`, `last_week`, `this_month`, or `last_month`) or a custom `from`/`to` date range (`YYYY-MM-DD`). The current endpoint accepts 14-digit timestamps; standardize the date-range contract and convert calendar periods to start-inclusive/end-exclusive timestamps.
- [ ] Define the timezone used for day, week, and month boundaries.
- [ ] Preserve Firebase authentication (`Authorization: Bearer <Firebase ID token>`) and verify the caller can access the requested `storeId`.
- [ ] Query BigQuery through the server-side `get_bigquery_client()` and runtime service-account credentials; never require or expose BigQuery credentials in the request.
- [ ] Test each preset, custom ranges, invalid ranges, and authentication/store-access failures.

Docs:
- docs/cloud-logging-endpoint.md — contract, examples, and configuration for `app_logs`
