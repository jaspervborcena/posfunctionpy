# Deployment Guide: Dev & Prod Environments

## Environment Overview

| Environment | Firebase Project | BigQuery Dataset | Service Account File |
|-------------|------------------|------------------|---------------------|
| **DEV** | jasperpos-dev | tovrika_pos_dev | service-account-dev.json |
| **PROD** | jasperpos-1dfd5 | tovrika_pos | service-account.json |

## Prerequisites

1. ✅ Firebase CLI installed: `npm install -g firebase-tools`
2. ✅ Authenticated with Firebase: `firebase login`
3. ✅ Both service account files in `functions/` directory
4. ✅ Python 3.12 installed

## Deploy to DEV

```powershell
# 1. Switch to dev project
firebase use dev

# 2. Verify you're on the correct project
firebase projects:list

# Should show: jasperpos-dev (current)

# 3. Deploy functions
firebase deploy --only functions

# 4. (Optional) Deploy specific function only
firebase deploy --only functions:sales_summary_by_store
```

### What Happens in DEV Deployment:
- Functions deployed to `jasperpos-dev` project
- Environment variable `GCP_PROJECT=jasperpos-dev` automatically set
- `config.py` detects dev environment
- Uses `service-account-dev.json`
- BigQuery queries target `jasperpos-dev.tovrika_pos_dev.*`

## Deploy to PROD

```powershell
# 1. Switch to prod project
firebase use prod

# 2. Verify you're on the correct project
firebase projects:list

# Should show: jasperpos-1dfd5 (current)

# 3. Deploy functions
firebase deploy --only functions

# 4. (Optional) Deploy specific function only
firebase deploy --only functions:sales_summary_by_store
```

### What Happens in PROD Deployment:
- Functions deployed to `jasperpos-1dfd5` project
- Environment variable `GCP_PROJECT=jasperpos-1dfd5` automatically set
- `config.py` detects prod environment
- Uses `service-account.json`
- BigQuery queries target `jasperpos-1dfd5.tovrika_pos.*`

## Angular App Configuration

### DEV Angular App
Located at: (your dev hosting URL)

```typescript
// environment.dev.ts
export const environment = {
  production: false,
  firebaseConfig: {
    apiKey: "YOUR_DEV_API_KEY",
    authDomain: "jasperpos-dev.firebaseapp.com",
    projectId: "jasperpos-dev",
    storageBucket: "jasperpos-dev.appspot.com",
    messagingSenderId: "YOUR_DEV_SENDER_ID",
    appId: "YOUR_DEV_APP_ID"
  },
  apiBaseUrl: "https://asia-east1-jasperpos-dev.cloudfunctions.net"
};
```

### PROD Angular App
Located at: (your prod hosting URL)

```typescript
// environment.prod.ts
export const environment = {
  production: true,
  firebaseConfig: {
    apiKey: "YOUR_PROD_API_KEY",
    authDomain: "jasperpos-1dfd5.firebaseapp.com",
    projectId: "jasperpos-1dfd5",
    storageBucket: "jasperpos-1dfd5.appspot.com",
    messagingSenderId: "YOUR_PROD_SENDER_ID",
    appId: "YOUR_PROD_APP_ID"
  },
  apiBaseUrl: "https://asia-east1-jasperpos-1dfd5.cloudfunctions.net"
};
```

## Verification After Deployment

### 1. Check Function Logs
```powershell
# DEV logs
firebase use dev
firebase functions:log

# PROD logs
firebase use prod
firebase functions:log
```

### 2. Test Authentication Flow

```powershell
# Get a Firebase ID token from your Angular app (check DevTools console)
# Then test with curl:

# DEV
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://asia-east1-jasperpos-dev.cloudfunctions.net/sales_summary_by_store?storeId=YOUR_STORE"

# PROD
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://asia-east1-jasperpos-1dfd5.cloudfunctions.net/sales_summary_by_store?storeId=YOUR_STORE"
```

### 3. Verify Environment Detection

Check function logs after deployment - you should see:
```
Environment: DEV (Project: jasperpos-dev, Dataset: tovrika_pos_dev)
```
or
```
Environment: PROD (Project: jasperpos-1dfd5, Dataset: tovrika_pos)
```

## Important Notes

### ⚠️ Service Account Files
- **Both files MUST exist in `functions/` directory before deployment**
- `.gcloudignore` is configured to include both files
- Never commit these files to git (`.gitignore` excludes them)

### 🔒 Authentication Flow
1. **User authenticates** with Firebase Auth in Angular app
2. **Angular HTTP interceptor** adds `Authorization: Bearer <token>` header
3. **Cloud Functions** verify token with Firebase Admin SDK
4. **Cloud Functions** use service account to query BigQuery/Firestore

### 🔄 Firestore Triggers
- Triggers run automatically on Firestore changes
- No user authentication required
- Service account handles all operations
- Environment detected automatically based on deployment project

### 📊 BigQuery Access
- **Users never directly access BigQuery**
- All access is through Cloud Functions
- Service account has BigQuery permissions
- Environment-specific datasets selected automatically

## Troubleshooting

### Issue: "Missing Authorization header" errors

**Cause**: Angular app not sending Firebase ID token

**Solution**: 
1. Implement HTTP interceptor (see `docs/angular-auth-interceptor-setup.md`)
2. Verify user is logged in before making API calls
3. Check DevTools Network tab for Authorization header

### Issue: "User not found in system"

**Cause**: User document doesn't exist in Firestore `users` collection

**Solution**:
1. Create user document in Firestore after Firebase Auth signup
2. Ensure document structure includes:
   - `uid`: Firebase UID
   - `status`: "active"
   - `permissions`: Array/Object with store access

### Issue: "Permission denied" in BigQuery

**Cause**: Service account doesn't have BigQuery permissions

**Solution**:
```powershell
# Grant BigQuery permissions to service account
gcloud projects add-iam-policy-binding jasperpos-dev \
  --member="serviceAccount:425012486350-compute@developer.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding jasperpos-dev \
  --member="serviceAccount:425012486350-compute@developer.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
```

### Issue: Wrong dataset being queried

**Cause**: Environment detection not working

**Solution**:
1. Check function logs for environment detection message
2. Verify `GCP_PROJECT` environment variable in Cloud Console
3. Redeploy to correct project using `firebase use dev` or `firebase use prod`

## Deployment Checklist

### Before Deploying to DEV
- [ ] `firebase use dev`
- [ ] `service-account-dev.json` exists in `functions/`
- [ ] Test files excluded in `.gcloudignore`
- [ ] Run `firebase deploy --only functions`

### Before Deploying to PROD
- [ ] `firebase use prod`
- [ ] `service-account.json` exists in `functions/`
- [ ] All changes tested in DEV first
- [ ] Backup important data
- [ ] Run `firebase deploy --only functions`

### After Any Deployment
- [ ] Check function logs for environment message
- [ ] Test authentication with curl or Postman
- [ ] Verify Angular app can make authenticated requests
- [ ] Check BigQuery for expected data

## Quick Commands Reference

```powershell
# List available projects
firebase projects:list

# Check current project
firebase use

# Switch to dev
firebase use dev

# Switch to prod
firebase use prod

# Deploy all functions
firebase deploy --only functions

# Deploy single function
firebase deploy --only functions:sales_summary_by_store

# View logs
firebase functions:log

# View logs for specific function
firebase functions:log --only sales_summary_by_store

# Tail logs in real-time
firebase functions:log --only sales_summary_by_store --tail
```
