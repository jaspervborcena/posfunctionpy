from firebase_functions import https_fn
from firebase_admin import initialize_app

# Initialize Firebase Admin SDK
initialize_app()

# Import BigQuery modules
from bigquery_api_endpoints import get_orders_by_store_bq, get_order_details_bq, get_orders_by_date_bq, get_sales_summary_bq
from bigquery_triggers import sync_order_to_bigquery, sync_order_details_to_bigquery
from app_logs import app_logs
from reconciliation import reconcile_daily, reconcile_on_demand
from paypal_endpoints import paypal_create_order, paypal_capture_order

# Testing and utilities
from test_auth import test_auth_basic, test_auth_store

# Optional test endpoint - kept for basic testing
@https_fn.on_request(region="asia-east1")
def on_request_example(req: https_fn.Request) -> https_fn.Response:
    return https_fn.Response("Hello world!")

# All available functions:
# 
# BIGQUERY APIs:
# - get_orders_by_store_bq: Get orders by store from BigQuery  
# - get_order_details_bq: Get order details by store and order from BigQuery
# - get_orders_by_date_bq: Get orders by date range from BigQuery
# - get_sales_summary_bq: Get sales summary with aggregated data (defaults to today)
# - sync_order_to_bigquery: Firestore trigger to sync orders to BigQuery
# - sync_order_details_to_bigquery: Firestore trigger to sync order details to BigQuery
#
# TESTING & UTILITIES:
# - test_auth_basic: Test basic authentication
# - test_auth_store: Test store access authentication  
# - on_request_example: Basic test endpoint
# - reconcile_daily: Scheduled reconciliation (2AM Asia/Manila)
# - reconcile_on_demand: Callable function to reconcile by company/store
# - paypal_create_order / paypal_capture_order: PayPal sandbox endpoints