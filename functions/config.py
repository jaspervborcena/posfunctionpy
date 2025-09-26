# Configuration constants for the Firebase Functions project

# Supabase Configuration  
SUPABASE_URL = "https://etwbbynzpgdsxdxuiasl.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV0d2JieW56cGdkc3hkeHVpYXNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTg1MTY4NTQsImV4cCI6MjA3NDA5Mjg1NH0.vNd1B_xxbOo5JnUkKfgflwikIA9tz2T7ym4mQWlCUJ0"
SUPABASE_SECRET_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImV0d2JieW56cGdkc3hkeHVpYXNsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1ODUxNjg1NCwiZXhwIjoyMDc0MDkyODU0fQ.b9ELJBIQReCvGiUCVPXC0kQgZ_nAaXuTqaVsVZT2LSQ"

# Firebase Configuration
FIREBASE_REGION = "asia-east1"

# Database Table Names
ORDERS_TABLE = "orders"
ORDER_DETAILS_TABLE = "order_details"

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

# Supabase Request Headers Template
def get_supabase_headers():
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }