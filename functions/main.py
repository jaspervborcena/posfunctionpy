from firebase_admin import initialize_app

# Initialize Firebase Admin SDK once at startup.
initialize_app()

# Only import the functions required for the current deployment.
# Importing the full BigQuery/Firestore trigger graph at startup can exceed the
# Firebase backend bootstrap timeout during deploy discovery.
from paypal_endpoints import paypal_client_config, paypal_create_order, paypal_capture_order

__all__ = [
    "paypal_client_config",
    "paypal_create_order",
    "paypal_capture_order",
]
