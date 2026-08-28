from firebase_admin import initialize_app

# Initialize Firebase Admin SDK once at startup.
initialize_app()

# Only import the functions required for the current deployment.
# Importing the full BigQuery/Firestore trigger graph at startup can exceed the
# Firebase backend bootstrap timeout during deploy discovery.
from paypal_endpoints import paypal_client_config, paypal_create_order, paypal_capture_order
from bigquery_triggers import (
    sync_order_to_bigquery,
    sync_order_to_bigquery_update,
    sync_order_selling_tracking_to_bigquery,
    sync_order_selling_tracking_update,
    sync_order_selling_tracking_delete,
    sync_order_details_to_bigquery,
    sync_order_details_update,
    sync_order_details_delete,
)
from bigquery_api_endpoints import get_sales_summary_bq

__all__ = [
    "paypal_client_config",
    "paypal_create_order",
    "paypal_capture_order",
    "sync_order_to_bigquery",
    "sync_order_to_bigquery_update",
    "sync_order_selling_tracking_to_bigquery",
    "sync_order_selling_tracking_update",
    "sync_order_selling_tracking_delete",
    "sync_order_details_to_bigquery",
    "sync_order_details_update",
    "sync_order_details_delete",
    "get_sales_summary_bq",
]
