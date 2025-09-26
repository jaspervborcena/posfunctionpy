from firebase_functions import https_fn
from firebase_admin import initialize_app

# Initialize Firebase Admin SDK
initialize_app()

# Import from separate modules
from api_endpoints import get_orders_by_store, get_order_details, get_orders_by_date
from firestore_triggers import sync_order_to_supabase, sync_order_details_to_supabase
from mock_endpoints import test_supabase_connection, mock_order_insert, mock_order_details_insert

# Optional test endpoint - kept for basic testing
@https_fn.on_request(region="asia-east1")
def on_request_example(req: https_fn.Request) -> https_fn.Response:
    return https_fn.Response("Hello world!")

# All other functions are now imported from separate modules:
# - API endpoints (get_orders_by_store, get_order_details, get_orders_by_date) from api_endpoints.py
# - Firestore triggers (sync_order_to_supabase, sync_order_details_to_supabase) from firestore_triggers.py  
# - Mock/test endpoints (test_supabase_connection, mock_order_insert, mock_order_details_insert) from mock_endpoints.py
# - Configuration constants from config.py