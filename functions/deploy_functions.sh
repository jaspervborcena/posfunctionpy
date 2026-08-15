# Deploy Cloud Functions to DEV and PROD environments
# Usage: bash deploy_functions.sh

# Set your function names here (comma-separated if multiple)
FUNCTION_NAMES="paypal_create_order,paypal_capture_order"

# Set your GCP project IDs
deV_PROJECT="jasperpos-dev"
PROD_PROJECT="jasperpos-1dfd5"

# Set your PayPal credentials here or use a secure method to inject them
# (For real deployments, use secret manager or CI/CD environment variables)
# Replace the placeholders below with your actual credentials
PAYPAL_CLIENT_ID_SANDBOX="your_sandbox_client_id"
PAYPAL_CLIENT_SECRET_SANDBOX="your_sandbox_client_secret"
PAYPAL_CLIENT_ID_LIVE="your_live_client_id"
PAYPAL_CLIENT_SECRET_LIVE="your_live_client_secret"

# Deploy to DEV (sandbox)
echo "Deploying to DEV ($deV_PROJECT)..."
gcloud functions deploy $FUNCTION_NAMES \
  --project=$deV_PROJECT \
  --set-env-vars=PAYPAL_CLIENT_ID_SANDBOX=$PAYPAL_CLIENT_ID_SANDBOX,PAYPAL_CLIENT_SECRET_SANDBOX=$PAYPAL_CLIENT_SECRET_SANDBOX \
  --runtime=python310 --trigger-http --allow-unauthenticated

echo "DEV deployment complete."

# Deploy to PROD (live)
echo "Deploying to PROD ($PROD_PROJECT)..."
gcloud functions deploy $FUNCTION_NAMES \
  --project=$PROD_PROJECT \
  --set-env-vars=PAYPAL_CLIENT_ID_LIVE=$PAYPAL_CLIENT_ID_LIVE,PAYPAL_CLIENT_SECRET_LIVE=$PAYPAL_CLIENT_SECRET_LIVE \
  --runtime=python310 --trigger-http --allow-unauthenticated

echo "PROD deployment complete."
