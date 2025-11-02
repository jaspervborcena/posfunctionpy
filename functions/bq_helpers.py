from config import BQ_FIELD_NAMES
from datetime import datetime

PRODUCT_FIELDS = BQ_FIELD_NAMES.get("products", {})


def clean_payload(obj):
    """Recursively remove None values from a nested dict."""
    if isinstance(obj, dict):
        return {k: clean_payload(v) for k, v in obj.items() if v is not None}
    return obj


def build_product_payload(product_id: str, data: dict) -> dict:
    """Build a BigQuery-ready product payload using canonical field names.

    The returned dict uses the BigQuery column names as keys (matching BQ schema).
    This centralizes naming and keeps payload construction consistent.
    """
    payload = {
        PRODUCT_FIELDS.get("product_id"): product_id,
        PRODUCT_FIELDS.get("barcode_id"): data.get("barcodeId"),
        PRODUCT_FIELDS.get("category"): data.get("category"),
        PRODUCT_FIELDS.get("company_id"): data.get("companyId"),
        PRODUCT_FIELDS.get("created_at"): data.get("createdAt").isoformat() if data.get("createdAt") else None,
        PRODUCT_FIELDS.get("created_by"): data.get("createdBy"),
        PRODUCT_FIELDS.get("description"): data.get("description"),
        PRODUCT_FIELDS.get("discount_type"): data.get("discountType"),
        PRODUCT_FIELDS.get("discount_value"): float(data.get("discountValue", 0)) if data.get("discountValue") is not None else None,
        PRODUCT_FIELDS.get("has_discount"): bool(data.get("hasDiscount", False)),
        PRODUCT_FIELDS.get("image_url"): data.get("imageUrl"),
        PRODUCT_FIELDS.get("is_favorite"): bool(data.get("isFavorite", False)),
        PRODUCT_FIELDS.get("is_vat_applicable"): bool(data.get("isVatApplicable", False)),
        PRODUCT_FIELDS.get("product_code"): data.get("productCode"),
        PRODUCT_FIELDS.get("product_name"): data.get("productName"),
        PRODUCT_FIELDS.get("selling_price"): float(data.get("sellingPrice", 0)) if data.get("sellingPrice") is not None else None,
        PRODUCT_FIELDS.get("sku_id"): data.get("skuId"),
        PRODUCT_FIELDS.get("status"): data.get("status"),
        PRODUCT_FIELDS.get("store_id"): data.get("storeId"),
        PRODUCT_FIELDS.get("total_stock"): int(data.get("totalStock", 0)) if data.get("totalStock") is not None else None,
        PRODUCT_FIELDS.get("uid"): data.get("uid"),
        PRODUCT_FIELDS.get("unit_type"): data.get("unitType"),
        PRODUCT_FIELDS.get("updated_at"): data.get("updatedAt").isoformat() if data.get("updatedAt") else None,
        PRODUCT_FIELDS.get("updated_by"): data.get("updatedBy")
    }

    return clean_payload(payload)