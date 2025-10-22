-- Run these commands in the BigQuery console to add missing columns

-- 1. Add orderId column to orders table
ALTER TABLE `jasperpos-1dfd5.tovrika_pos.orders` 
ADD COLUMN IF NOT EXISTS orderId STRING;

-- 2. Add orderDetailsId column to order_details table  
ALTER TABLE `jasperpos-1dfd5.tovrika_pos.order_details`
ADD COLUMN IF NOT EXISTS orderDetailsId STRING;

-- Verify the columns were added:
-- SELECT * FROM `jasperpos-1dfd5.tovrika_pos.orders` LIMIT 1;
-- SELECT * FROM `jasperpos-1dfd5.tovrika_pos.order_details` LIMIT 1;