# Configuration constants for the Firebase Functions project
import os

# Determine environment (dev or prod) based on project ID
# This is automatically set by Firebase Functions runtime
ENVIRONMENT = os.environ.get('GCP_PROJECT', 'jasperpos-1dfd5')
IS_DEV = ENVIRONMENT == 'jasperpos-dev'

# BigQuery Configuration - switches based on environment
if IS_DEV:
    BIGQUERY_PROJECT_ID = "jasperpos-dev"
    BIGQUERY_DATASET_ID = "tovrika_pos_dev"
else:
    BIGQUERY_PROJECT_ID = "jasperpos-1dfd5"
    BIGQUERY_DATASET_ID = "tovrika_pos"

BIGQUERY_LOCATION = "asia-east1"  # Same region as your Firebase Functions

# Firebase Configuration
FIREBASE_REGION = "asia-east1"

# Log current environment for debugging
print(f"🌍 Environment: {'DEV' if IS_DEV else 'PROD'} (Project: {BIGQUERY_PROJECT_ID})")

# BigQuery Table Names
BIGQUERY_ORDERS_TABLE = f"{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET_ID}.orders"
BIGQUERY_ORDER_DETAILS_TABLE = f"{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET_ID}.orderDetails"
# BigQuery products table (matches Firestore `products` collection)
BIGQUERY_PRODUCTS_TABLE = f"{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET_ID}.products"
# BigQuery orders selling tracking table (matches Firestore `ordersSellingTracking` collection)
BIGQUERY_ORDER_SELLING_TRACKING_TABLE = f"{BIGQUERY_PROJECT_ID}.{BIGQUERY_DATASET_ID}.ordersSellingTracking"

# Collection Names (Firestore)
ORDERS_COLLECTION = "orders"
ORDER_DETAILS_COLLECTION = "orderDetails"

# Standardized names / aliases to help find resources quickly
BQ_TABLES = {
    "orders": BIGQUERY_ORDERS_TABLE,
    "orderDetails": BIGQUERY_ORDER_DETAILS_TABLE,
    "products": BIGQUERY_PRODUCTS_TABLE,
    "ordersSellingTracking": BIGQUERY_ORDER_SELLING_TRACKING_TABLE
}

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
        return bigquery.Client(project=BIGQUERY_PROJECT_ID, location=BIGQUERY_LOCATION)
    except ImportError:
        print("WARNING: BigQuery library not available")
        return None


# Backfill presets for products (key -> (start_iso, end_iso))
# Update this mapping to add or change preset ranges used by the manual backfill trigger
BACKFILL_PRESETS = {
    "20251001_20251031": ("2025-10-01", "2025-10-31"),
    "oct2025": ("2025-10-01", "2025-10-31")
}