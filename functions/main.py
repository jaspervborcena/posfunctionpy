from firebase_functions import https_fn
from firebase_admin import initialize_app

# Initialize Firebase Admin SDK
initialize_app()

# Import BigQuery modules
from bigquery_api_endpoints import get_orders_count_by_date_bq, get_orders_count_by_status_bq, get_sales_summary_bq, get_products_bq, get_orders_bq
from bigquery_triggers import sync_order_to_bigquery, sync_order_details_to_bigquery, sync_products_to_bigquery, sync_products_to_bigquery_update, sync_products_to_bigquery_delete, sync_order_to_bigquery_update, sync_order_to_bigquery_delete, sync_order_details_update, sync_order_details_delete
# app_logs endpoint removed; previously provided an HTTP logging endpoint
from reconciliation import reconcile_daily
from paypal_endpoints import paypal_create_order, paypal_capture_order
from product_inventory_api import get_product_inventory_bq

# Products APIs (Firestore)  
from products_api import update_product

# Testing and utilities
from test_auth import test_auth_basic, test_auth_store

# Optional test endpoint removed.
# The simple `on_request_example` test HTTP function was removed to avoid
# exposing an unneeded endpoint in production.

# All available functions:
# 
# BIGQUERY APIs:
# - get_products_bq: Get products by store from BigQuery  
# - get_orders_bq: Get orders by store from BigQuery (paginated)
# - get_orders_count_by_date_bq: Get order count statistics aggregated by date from BigQuery
# - get_orders_count_by_status_bq: Get order count statistics aggregated by date with amounts from BigQuery
# - get_sales_summary_bq: Get sales summary with aggregated data (defaults to today)
# - get_product_inventory_bq: Get product inventory by store/product from BigQuery
# - sync_order_to_bigquery: Firestore trigger to sync orders to BigQuery
# - sync_order_details_to_bigquery: Firestore trigger to sync orderDetails to BigQuery
#
# PRODUCTS APIs (FIRESTORE):
# - get_products: DEPRECATED (use BigQuery `get_products_bq`)
# - update_product: Update existing product in Firestore
#
# TESTING & UTILITIES:
# - test_auth_basic: Test basic authentication
# - test_auth_store: Test store access authentication  
# - reconcile_daily: Scheduled reconciliation (2AM Asia/Manila)
# - paypal_create_order / paypal_capture_order: PayPal sandbox endpoints