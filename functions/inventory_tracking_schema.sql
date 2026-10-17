CREATE TABLE IF NOT EXISTS `jasperpos-1dfd5.tovrika_pos.inventoryTracking` (
  inventoryTrackingId STRING,
  batchId STRING,
  companyId STRING,
  costPrice NUMERIC,
  createdAt TIMESTAMP,
  createdBy STRING,
  deductedAt TIMESTAMP,
  deductedBy STRING,
  eventType STRING,
  invoiceNumber STRING,
  note STRING,
  orderId STRING,
  productCode STRING,
  productId STRING,
  productName STRING,
  quantity INT64,
  refId STRING,
  runningBalanceTotalStock INT64,
  skuId STRING,
  storeId STRING
)
PARTITION BY DATE(createdAt)
CLUSTER BY storeId, productId;

CREATE TABLE IF NOT EXISTS `jasperpos-dev.tovrika_pos_dev.inventoryTracking` (
  inventoryTrackingId STRING,
  batchId STRING,
  companyId STRING,
  costPrice NUMERIC,
  createdAt TIMESTAMP,
  createdBy STRING,
  deductedAt TIMESTAMP,
  deductedBy STRING,
  eventType STRING,
  invoiceNumber STRING,
  note STRING,
  orderId STRING,
  productCode STRING,
  productId STRING,
  productName STRING,
  quantity INT64,
  refId STRING,
  runningBalanceTotalStock INT64,
  skuId STRING,
  storeId STRING
)
PARTITION BY DATE(createdAt)
CLUSTER BY storeId, productId;