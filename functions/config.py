# Configuration constants for the Firebase Functions project
import os

def _get_environment():
    """Determine environment (dev or prod) based on project ID"""
    # K_SERVICE is set by Cloud Run/Functions, GCP_PROJECT is the project ID
    project_id = os.environ.get('GCP_PROJECT') or os.environ.get('GOOGLE_CLOUD_PROJECT', 'jasperpos-1dfd5')
    return project_id

def _is_dev():
    """Check if running in dev environment"""
    return _get_environment() == 'jasperpos-dev'

# Lazy-loaded configuration - call these functions instead of accessing constants directly
def get_bigquery_project_id():
    """Get BigQuery project ID based on environment"""
    return "jasperpos-dev" if _is_dev() else "jasperpos-1dfd5"

def get_bigquery_dataset_id():
    """Get BigQuery dataset ID based on environment"""
    return "tovrika_pos_dev" if _is_dev() else "tovrika_pos"

def get_service_account_file():
    """Get service account file path based on environment"""
    return "service-account-dev.json" if _is_dev() else "service-account.json"

# For backward compatibility - these will evaluate at runtime
BIGQUERY_PROJECT_ID = get_bigquery_project_id()
BIGQUERY_DATASET_ID = get_bigquery_dataset_id()
SERVICE_ACCOUNT_FILE = get_service_account_file()

BIGQUERY_LOCATION = "asia-east1"  # Same region as your Firebase Functions

# Firebase Configuration
FIREBASE_REGION = "asia-east1"

# Log current environment for debugging (only log on first access)
_logged = False
def _log_environment():
    global _logged
    if not _logged:
        env = 'DEV' if _is_dev() else 'PROD'
        print(f"Environment: {env} (Project: {get_bigquery_project_id()}, Dataset: {get_bigquery_dataset_id()})")
        _logged = True

# BigQuery Table Names - dynamically constructed
def _get_table_name(table):
    """Get fully qualified BigQuery table name"""
    _log_environment()
    return f"{get_bigquery_project_id()}.{get_bigquery_dataset_id()}.{table}"

BIGQUERY_ORDERS_TABLE = _get_table_name("orders")
BIGQUERY_ORDER_DETAILS_TABLE = _get_table_name("orderDetails")
BIGQUERY_PRODUCTS_TABLE = _get_table_name("products")
BIGQUERY_ORDER_SELLING_TRACKING_TABLE = _get_table_name("ordersSellingTracking")

# Collection Names (Firestore)
ORDERS_COLLECTION = "orders"
ORDER_DETAILS_COLLECTION = "orderDetails"

# Standardized names / aliases to help find resources quickly
def get_bq_tables():
    """Get BigQuery table names for current environment"""
    return {
        "orders": _get_table_name("orders"),
        "orderDetails": _get_table_name("orderDetails"),
        "products": _get_table_name("products"),
        "ordersSellingTracking": _get_table_name("ordersSellingTracking")
    }

# For backward compatibility
BQ_TABLES = get_bq_tables()

# Firestore collection name constants (already present but normalized)
COLLECTIONS = {
    "orders": ORDERS_COLLECTION,
    "orderDetails": ORDER_DETAILS_COLLECTION,
    "products": "products"
}

# Canonical BigQuery field names mapping (logical -> actual column name)
# Use these to standardize payload keys when inserting into BigQuery.
# Keys are grouped by resource type.
BQ_FIELD_NAMES = {
    "products": {
        "product_id": "productId",
        "barcode_id": "barcodeId",
        "category": "category",
        "company_id": "companyId",
        "created_at": "createdAt",
        "created_by": "createdBy",
        "description": "description",
        "discount_type": "discountType",
        "discount_value": "discountValue",
        "has_discount": "hasDiscount",
        "image_url": "imageUrl",
        "is_favorite": "isFavorite",
        "is_vat_applicable": "isVatApplicable",
        "product_code": "productCode",
        "product_name": "productName",
        "selling_price": "sellingPrice",
        "sku_id": "skuId",
        "status": "status",
        "store_id": "storeId",
        "total_stock": "totalStock",
        "uid": "uid",
        "unit_type": "unitType",
        "updated_at": "updatedAt",
        "updated_by": "updatedBy"
    }
}

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
        _log_environment()
        return bigquery.Client(project=get_bigquery_project_id(), location=BIGQUERY_LOCATION)
    except ImportError:
        print("WARNING: BigQuery library not available")
        return None


# Backfill presets for products (key -> (start_iso, end_iso))
# Update this mapping to add or change preset ranges used by the manual backfill trigger
BACKFILL_PRESETS = {
    "20251001_20251031": ("2025-10-01", "2025-10-31"),
    "oct2025": ("2025-10-01", "2025-10-31")
}