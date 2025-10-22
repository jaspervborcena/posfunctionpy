# Configuration constants for the Firebase Functions project

# BigQuery Configuration
BIGQUERY_PROJECT_ID = "jasperpos-1dfd5"
BIGQUERY_DATASET_ID = "tovrika_pos"
BIGQUERY_LOCATION = "asia-east1"  # Same region as your Firebase Functions

# Firebase Configuration
FIREBASE_REGION = "asia-east1"

# BigQuery Table Names
BIGQUERY_ORDERS_TABLE = f"{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET_ID}.orders"
BIGQUERY_ORDER_DETAILS_TABLE = f"{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET_ID}.order_details"

# Collection Names (Firestore)
ORDERS_COLLECTION = "orders"
ORDER_DETAILS_COLLECTION = "orderDetails"

# API Response Headers
DEFAULT_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS", 
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Content-Type": "application/json"
}

# BigQuery Client Helper
def get_bigquery_client():
    """Get BigQuery client instance"""
    try:
        from google.cloud import bigquery
        return bigquery.Client(project=BIGQUERY_PROJECT_ID, location=BIGQUERY_LOCATION)
    except ImportError:
        print("WARNING: BigQuery library not available")
        return None