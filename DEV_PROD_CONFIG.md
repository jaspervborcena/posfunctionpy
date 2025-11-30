# Dev/Prod Configuration Summary

## ✅ Configuration Status

### Environment Detection
**Location**: `functions/config.py`

**How it works**:
```python
# Automatically detects environment from GCP_PROJECT environment variable
# Set automatically by Firebase/Cloud Functions during deployment

if GCP_PROJECT == "jasperpos-dev":
    → Use tovrika_pos_dev dataset
    → Use service-account-dev.json
else:
    → Use tovrika_pos dataset  
    → Use service-account.json
```

### Files Reviewed & Verified

| File | Status | Notes |
|------|--------|-------|
| `config.py` | ✅ Correct | Dynamic environment detection working |
| `auth_middleware.py` | ✅ Correct | No project-specific code, uses Firebase Admin SDK |
| `bigquery_api_endpoints.py` | ✅ Correct | Uses `config.py` functions |
| `bigquery_triggers.py` | ✅ Correct | Uses `config.py` functions |
| `product_inventory_api.py` | ✅ Fixed | Updated to use dynamic config |
| `products_api.py` | ✅ Correct | Firestore only, no project-specific code |
| `main.py` | ✅ Correct | Just imports, no project-specific code |
| `.firebaserc` | ✅ Correct | Has dev and prod project aliases |
| `.gcloudignore` | ✅ Correct | Includes both service account files |

## 🔧 Changes Made

### 1. Fixed `product_inventory_api.py`
**Before**:
```python
BIGQUERY_PRODUCT_INVENTORY_TABLE = "jasperpos-1dfd5.tovrika_pos.productInventory"
```

**After**:
```python
def _get_product_inventory_table():
    """Get fully qualified BigQuery table name for product inventory"""
    return f"{get_bigquery_project_id()}.{get_bigquery_dataset_id()}.productInventory"
```

## 📋 Deployment Process

### Dev Deployment
```powershell
firebase use dev
firebase deploy --only functions
```
**Result**: Functions deployed to `jasperpos-dev`, uses `tovrika_pos_dev`

### Prod Deployment
```powershell
firebase use prod
firebase deploy --only functions
```
**Result**: Functions deployed to `jasperpos-1dfd5`, uses `tovrika_pos`

## 🔐 Authentication Flow (HTTP Endpoints)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User logs in via Angular (Firebase Auth)                 │
│    → Gets Firebase ID token                                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 2. Angular HTTP Interceptor                                  │
│    → Adds: Authorization: Bearer <token>                     │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 3. Cloud Function (@require_auth decorator)                  │
│    → Verifies token with Firebase Admin SDK                  │
│    → Checks user in Firestore users collection               │
│    → Validates status = "active"                             │
│    → Checks store permissions                                │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 4. Service Account Operations                                │
│    → Query BigQuery with service account                     │
│    → Read/Write Firestore with service account               │
│    → Return data to user                                     │
└─────────────────────────────────────────────────────────────┘
```

## 🤖 Trigger Flow (Background Functions)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Firestore Document Change                                 │
│    → onCreate / onUpdate / onDelete                           │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 2. Trigger Function (Automatic)                              │
│    → No user authentication required                         │
│    → Service account auto-configured                         │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 3. Service Account Operations                                │
│    → Read Firestore document data                            │
│    → INSERT/UPDATE BigQuery                                  │
│    → Log operations                                          │
└─────────────────────────────────────────────────────────────┘
```

## 🎯 Key Points

### ✅ What's Correct
1. **Environment auto-detection** based on deployment project
2. **Service accounts** properly configured for each environment
3. **Authentication** uses Firebase ID tokens from users
4. **Authorization** uses service accounts for backend operations
5. **Separate deployments** to dev and prod projects
6. **No hardcoded** project IDs in deployed code

### ⚠️ Important Notes
1. **Users never directly access BigQuery** - only through Cloud Functions
2. **Service accounts** have BigQuery and Firestore permissions
3. **Angular app must match** the Firebase project (dev app → dev project, prod app → prod project)
4. **HTTP interceptor required** in Angular to send auth tokens
5. **Triggers don't need** user authentication - they're server-to-server

### 🔒 Security Model
- **User Authentication**: Firebase ID tokens (verified by Cloud Functions)
- **Backend Operations**: Service accounts (never exposed to users)
- **Store Access Control**: Checked via Firestore user permissions
- **BigQuery Access**: Service account only, users can't access directly

## 📝 Next Steps

1. ✅ **Implement Angular HTTP Interceptor**
   - See: `docs/angular-auth-interceptor-setup.md`
   - Automatically adds `Authorization: Bearer <token>` to all API requests

2. ✅ **Deploy to Dev First**
   ```powershell
   firebase use dev
   firebase deploy --only functions
   ```

3. ✅ **Test Authentication**
   - User logs in → gets token
   - Make API call → check Network tab for Authorization header
   - Verify Cloud Functions logs show successful auth

4. ✅ **Deploy to Prod**
   ```powershell
   firebase use prod
   firebase deploy --only functions
   ```

## 🐛 Troubleshooting

### "Missing Authorization header"
**Solution**: Implement HTTP interceptor in Angular

### "User not found in system"
**Solution**: Create user document in Firestore with uid, status, permissions

### Wrong dataset being queried
**Solution**: Check `firebase use` command, verify correct project

### Service account permission errors
**Solution**: Grant BigQuery roles to service account

## 📚 Documentation Files

- `DEPLOYMENT_GUIDE.md` - Detailed deployment instructions
- `docs/angular-auth-interceptor-setup.md` - Angular HTTP interceptor setup
- `DEPLOYMENT.md` - Original deployment documentation
- This file - Configuration summary

---

**Status**: ✅ Ready for deployment to both dev and prod environments
