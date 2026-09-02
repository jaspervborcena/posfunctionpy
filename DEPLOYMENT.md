# Deployment Guide - Dev & Production Environments

## Overview
This project supports two Firebase environments:
- **Production**: `jasperpos-1dfd5` (tovrika_pos dataset)
- **Development**: `jasperpos-dev` (tovrika_pos_dev dataset)

The code automatically detects which environment it's running in and connects to the correct BigQuery dataset.

## Prerequisites
- Firebase CLI installed (`npm install -g firebase-tools`)
- Authenticated with Firebase (`firebase login`)
- Access to both Firebase projects

## Quick Deployment Commands

### Deploy to Development
```bash
firebase use dev
firebase deploy --only functions
```

### Deploy to Production
```bash
firebase use prod
firebase deploy --only functions
```

### Check Current Environment
```bash
firebase use
```

## Project Configuration

### Firebase Projects
| Alias | Project ID | BigQuery Dataset | Purpose |
|-------|-----------|------------------|---------|
| `dev` | jasperpos-dev | tovrika_pos_dev | Development & testing |
| `prod` | jasperpos-1dfd5 | tovrika_pos | Production |

### Environment Detection
The functions automatically detect which environment they're running in:
- Environment is determined by `GCP_PROJECT` environment variable
- Config switches BigQuery dataset based on project ID
- Logs show current environment on startup: `🌍 Environment: DEV/PROD`

## Branch Strategy

### Main Branches
- `main` - Production stable code
- `dev` - Development branch (current)
- `feature/*` - Feature branches

### Workflow
1. **Development**: Make changes on `dev` branch
2. **Test**: Deploy to dev environment
   ```bash
   git checkout dev
   firebase use dev
   firebase deploy --only functions
   ```
3. **Merge to Prod**: When ready, merge to production branch
   ```bash
   git checkout main
   git merge dev
   firebase use prod
   firebase deploy --only functions
   ```

## BigQuery Setup

### ✅ Confirmed Datasets
Both environments are configured and working:

**Dev Project (jasperpos-dev)**:
- Dataset: `jasperpos-dev.tovrika_pos_dev` ✅
- Location: `asia-east1`
- Tables: orders, orderDetails, products, ordersSellingTracking

**Prod Project (jasperpos-1dfd5)**:
- Dataset: `jasperpos-1dfd5.tovrika_pos` ✅
- Location: `asia-east1`
- Tables: orders, orderDetails, products, ordersSellingTracking

### Automatic Table References
The config automatically switches table references based on environment:

**Dev Environment:**
- `jasperpos-dev.tovrika_pos_dev.orders`
- `jasperpos-dev.tovrika_pos_dev.orderDetails`
- `jasperpos-dev.tovrika_pos_dev.products`
- `jasperpos-dev.tovrika_pos_dev.ordersSellingTracking`

**Prod Environment:**
- `jasperpos-1dfd5.tovrika_pos.orders`
- `jasperpos-1dfd5.tovrika_pos.orderDetails`
- `jasperpos-1dfd5.tovrika_pos.products`
- `jasperpos-1dfd5.tovrika_pos.ordersSellingTracking`

### Schema Consistency
Both dev and prod datasets use **identical schemas** - all table structures, field types, and constraints are the same to ensure consistent behavior across environments.

## Testing Your Deployment

### Verify Environment
After deployment, check logs to confirm correct environment:
```bash
firebase functions:log --only sync_order_to_bigquery
```
Look for: `🌍 Environment: DEV (Project: jasperpos-dev)`

### Test API Endpoints
Dev endpoints will be at different URLs:
```bash
# Development
https://[function-name]-[hash]-de.a.run.app

# Production  
https://[function-name]-[hash]-de.a.run.app
```

## Common Commands

```bash
# Switch to dev environment
firebase use dev

# Switch to prod environment
firebase use prod

# Deploy all functions
firebase deploy --only functions

# Deploy specific function
firebase deploy --only functions:get_products_bq

# View logs
firebase functions:log

# View logs for specific function
firebase functions:log --only get_products_bq

# List all deployed functions
firebase functions:list
```

## Troubleshooting

### Wrong BigQuery Dataset
If functions connect to wrong dataset:
1. Check current Firebase project: `firebase use`
2. Verify environment variable in logs
3. Redeploy to correct project

### Permission Errors
Ensure service account has permissions in both projects:
- BigQuery Data Editor
- BigQuery Job User
- Cloud Functions Invoker

### Function Not Found
If function URL returns 404:
1. Verify function is exported in `functions/main.py`
2. Check deployment logs for errors
3. Ensure function deployed successfully: `firebase functions:list`

## Security Notes

⚠️ **Important**:
- Dev and prod environments are completely isolated
- Each has separate Firestore and BigQuery instances
- API keys are different (see firebaseConfig in web app)
- Test thoroughly in dev before deploying to prod

## Web App Configuration

### Development
```javascript
const firebaseConfig = {
  apiKey: "AIzaSyABpbnPUjr16LnLU8WSJ1BmVvWy0tTmaI4",
  authDomain: "jasperpos-dev.firebaseapp.com",
  projectId: "jasperpos-dev",
  storageBucket: "jasperpos-dev.firebasestorage.app",
  messagingSenderId: "425012486350",
  appId: "1:425012486350:web:6a1289e238eb26fb36709f",
  measurementId: "G-5BLXC1688Z"
};
```

### Production
```javascript
const firebaseConfig = {
  apiKey: "YOUR_PROD_API_KEY",
  authDomain: "jasperpos-1dfd5.firebaseapp.com",
  projectId: "jasperpos-1dfd5",
  storageBucket: "jasperpos-1dfd5.appspot.com",
  // ... other prod config
};
```

## Next Steps

1. **Create Dev BigQuery Dataset**:
   ```bash
   # In Google Cloud Console for jasperpos-dev
   # Create dataset: tovrika_pos_dev
   # Location: asia-east1
   ```

2. **Create Dev Tables**:
   Run all table creation scripts pointing to dev dataset

3. **Test Deployment**:
   ```bash
   firebase use dev
   firebase deploy --only functions
   ```

4. **Verify**:
   - Check function logs for correct environment
   - Test API endpoints
   - Verify BigQuery writes to correct dataset
