# BigQuery Table Creation Scripts

# Your existing tables:

"""
-- Orders table (already created)
CREATE TABLE `jasperpos-1dfd5.tovrika_pos.orders` (
  assignedCashierEmail STRING,
  assignedCashierId STRING,
  assignedCashierName STRING,
  atpOrOcn STRING,
  birPermitNo STRING,
  cashSale BOOL,
  companyAddress STRING,
  companyEmail STRING,
  companyId STRING,
  companyName STRING,
  companyPhone STRING,
  companyTaxId STRING,
  createdAt TIMESTAMP,
  createdBy STRING,
  customerInfo STRUCT<
    address STRING,
    customerId STRING,
    fullName STRING,
    tin STRING
  >,
  date TIMESTAMP,
  discountAmount FLOAT64,
  grossAmount FLOAT64,
  inclusiveSerialNumber STRING,
  invoiceNumber STRING,
  message STRING,
  netAmount FLOAT64,
  payments STRUCT<
    amountTendered FLOAT64,
    changeAmount FLOAT64,
    paymentDescription STRING
  >,
  status STRING,
  storeId STRING,
  totalAmount FLOAT64,
  uid STRING,
  updatedAt TIMESTAMP,
  updatedBy STRING,
  vatAmount FLOAT64,
  vatExemptAmount FLOAT64,
  vatableSales FLOAT64,
  zeroRatedSales FLOAT64,
  orderId STRING  -- Added for Firestore document ID
);
"""

"""
-- Order Details table (already created)
-- OLD order_details table has been removed - using orderDetails (camelCase) instead

# If you need to add the new fields to existing tables:
"""
-- Add orderId field to orders table if not exists
ALTER TABLE `jasperpos-1dfd5.tovrika_pos.orders` 
ADD COLUMN IF NOT EXISTS orderId STRING;
"""