# Configuration constants for the Firebase Functions project
import os

def _get_environment():
    """Determine environment (dev or prod) based on project ID"""
    # Allow an explicit override for the target project. This is the
    # preferred way to force dev vs prod at runtime (set via function
    # env var or CI/CD): TARGET_PROJECT
    explicit = os.environ.get('TARGET_PROJECT') or os.environ.get('TARGET')
    if explicit:
        print(f"DEBUG: Using explicit TARGET_PROJECT={explicit}")
        return explicit

    # K_SERVICE is set by Cloud Run/Functions, GCP_PROJECT / GOOGLE_CLOUD_PROJECT are common env vars
    project_id = os.environ.get('GCP_PROJECT') or os.environ.get('GOOGLE_CLOUD_PROJECT')
    # Do NOT fall back to Application Default Credentials for project discovery here.
    # Relying on ADC at runtime can accidentally pick up a service-account.json file
    # that exists in the source tree (for example a prod key) and cause the
    # function to target the wrong project. Prefer explicit env vars only.
    if not project_id:
        project_id = None

    if not project_id:
        # Fail-safe: do not silently point to PROD. Explicitly default but log.
        default = 'jasperpos-1dfd5'
        print(f"WARNING: Unable to determine GCP project from environment or ADC; defaulting to '{default}'")
        project_id = default

    return project_id

def _is_dev():
    """Check if running in dev environment"""
    return _get_environment() == 'jasperpos-dev'

# Lazy-loaded configuration - call these functions instead of accessing constants directly
def get_bigquery_project_id():
    """Get BigQuery project ID based on environment"""
    # If a TARGET_PROJECT env var is set, prefer it explicitly.
    explicit = os.environ.get('TARGET_PROJECT') or os.environ.get('TARGET')
    if explicit:
        return explicit

    return "jasperpos-dev" if _is_dev() else "jasperpos-1dfd5"

def get_bigquery_dataset_id():
    """Get BigQuery dataset ID based on environment"""
    # Allow overriding the dataset independently (useful for test sandboxes)
    explicit_dataset = os.environ.get('TARGET_DATASET') or os.environ.get('TARGET_DATASET_ID')
    if explicit_dataset:
        return explicit_dataset

    return "tovrika_pos_dev" if _is_dev() else "tovrika_pos"

def get_service_account_file():
    """Get service account file path based on environment"""
    return "service-account-dev.json" if _is_dev() else "service-account.json"

# For backward compatibility - avoid evaluating at import time to prevent
# blocking during Firebase CLI code analysis (do not call ADC on import).
# Use the functions `get_bigquery_project_id()` / `get_bigquery_dataset_id()`
# / `get_service_account_file()` at runtime instead.
BIGQUERY_PROJECT_ID = None
BIGQUERY_DATASET_ID = None
SERVICE_ACCOUNT_FILE = None

BIGQUERY_LOCATION = "asia-east1"  # Same region as your Firebase Functions

# Firebase Configuration
FIREBASE_REGION = "asia-east1"

# Log current environment for debugging (only log on first access)
_logged = False
def _log_environment():
    global _logged
    if not _logged:
        env = 'DEV' if _is_dev() else 'PROD'
        # Print detected environment and BigQuery target
        print(f"Environment: {env} (Project: {get_bigquery_project_id()}, Dataset: {get_bigquery_dataset_id()})")

        # Diagnostic: print relevant environment variables that affect project detection
        try:
            gcp_proj = os.environ.get('GCP_PROJECT')
            gcp_cloud_proj = os.environ.get('GOOGLE_CLOUD_PROJECT')
            gadc = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            kservice = os.environ.get('K_SERVICE')
            target_proj = os.environ.get('TARGET_PROJECT') or os.environ.get('TARGET')
            target_ds = os.environ.get('TARGET_DATASET') or os.environ.get('TARGET_DATASET_ID')
            print(f"DEBUG ENV: GCP_PROJECT={gcp_proj}, GOOGLE_CLOUD_PROJECT={gcp_cloud_proj}, GOOGLE_APPLICATION_CREDENTIALS={gadc}, K_SERVICE={kservice}")
            print(f"DEBUG ENV: TARGET_PROJECT={target_proj}, TARGET_DATASET={target_ds}")
        except Exception:
            pass

        # Diagnostic: attempt to discover ADC project and print it
        try:
            import google.auth
            creds_info = google.auth.default()
            # google.auth.default() returns (credentials, project_id)
            adc_proj = creds_info[1] if isinstance(creds_info, tuple) and len(creds_info) > 1 else None
            print(f"DEBUG ADC: google.auth.default() project_id={adc_proj}")
        except Exception as e:
            print(f"DEBUG ADC: google.auth.default() failed: {e}")
        _logged = True

# BigQuery Table Names - dynamically constructed
# Lazy table name getter to avoid performing environment discovery at import time
def get_bigquery_table_name(table: str) -> str:
    """Get fully qualified BigQuery table name at runtime."""
    _log_environment()
    return f"{get_bigquery_project_id()}.{get_bigquery_dataset_id()}.{table}"

# Backwards-compatible placeholders (kept for callers that expect names at import),
# but do not populate them here to avoid triggering ADC during CLI deploy analysis.
BIGQUERY_ORDERS_TABLE = None
BIGQUERY_ORDER_DETAILS_TABLE = None
BIGQUERY_PRODUCTS_TABLE = None
BIGQUERY_ORDER_SELLING_TRACKING_TABLE = None

# Collection Names (Firestore)
ORDERS_COLLECTION = "orders"
ORDER_DETAILS_COLLECTION = "orderDetails"

# Standardized names / aliases to help find resources quickly
def get_bq_tables():
    """Get BigQuery table names for current environment"""
    return {
        "orders": get_bigquery_table_name("orders"),
        "orderDetails": get_bigquery_table_name("orderDetails"),
        "products": get_bigquery_table_name("products"),
        "ordersSellingTracking": get_bigquery_table_name("ordersSellingTracking")
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