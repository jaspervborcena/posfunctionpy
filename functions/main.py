from firebase_functions import https_fn
from firebase_admin import initialize_app

# Initialize Firebase Admin SDK
initialize_app()

# Import BigQuery modules
from bigquery_api_endpoints import get_orders_by_store_bq, get_order_details_bq, get_orders_by_date_bq, get_sales_summary_bq, get_products_bq, backfill_products_bq, backfill_orders_bq, backfill_order_details_bq
from bigquery_triggers import sync_order_to_bigquery, sync_order_details_to_bigquery, sync_products_to_bigquery, sync_products_to_bigquery_streaming, sync_products_to_bigquery_update, sync_products_to_bigquery_delete, sync_order_to_bigquery_update, sync_order_to_bigquery_delete, sync_order_details_to_bigquery_update, sync_order_details_to_bigquery_delete
from app_logs import app_logs
from reconciliation import reconcile_daily, reconcile_on_demand
from paypal_endpoints import paypal_create_order, paypal_capture_order
from product_inventory_api import insert_product_inventory_bq, get_product_inventory_bq

# Products APIs (Firestore)  
from products_api import insert_product, update_product

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
# - insert_product_inventory_bq: Insert product inventory to BigQuery
# - get_product_inventory_bq: Get product inventory by store/product from BigQuery
# - sync_order_to_bigquery: Firestore trigger to sync orders to BigQuery
# - sync_order_details_to_bigquery: Firestore trigger to sync order details to BigQuery
#
# PRODUCTS APIs (FIRESTORE):
# - insert_product: Insert new product to Firestore products collection
# - get_products: DEPRECATED (use BigQuery `get_products_bq`)
# - update_product: Update existing product in Firestore
#
# TESTING & UTILITIES:
# - test_auth_basic: Test basic authentication
# - test_auth_store: Test store access authentication  
# - on_request_example: Basic test endpoint
# - reconcile_daily: Scheduled reconciliation (2AM Asia/Manila)
# - reconcile_on_demand: Callable function to reconcile by company/store
# - paypal_create_order / paypal_capture_order: PayPal sandbox endpoints