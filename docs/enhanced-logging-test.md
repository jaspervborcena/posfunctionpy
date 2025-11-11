# Enhanced Cloud Logging Test

## Test Request Format

This is the new format for the enhanced cloud logging endpoint that uses Firebase UID authentication:

```json
{
  "timestamp": "2025-11-06T08:45:00.000Z",
  "level": "info",
  "severity": "INFO",
  "message": "Test enhanced logging with Firebase UID auth",
  "uid": "actual-firebase-uid-here",
  "area": "testing",
  "api": "manual-test",
  "status": 200,
  "success": true,
  "durationMs": 150,
  "payload": {
    "operation": "test",
    "version": "2.0"
  }
}
```

## Key Changes from Previous Version

1. **Required Field**: `uid` (Firebase UID) instead of Authorization header
2. **Removed Required Fields**: `status` and `success` are now optional
3. **Enhanced Security**: Server-side Firebase UID verification
4. **User Context**: Automatic enrichment with user/company/store data

## Testing Requirements

To test this endpoint, you need:

1. **Valid Firebase UID**: From an actual user in your Firebase Auth
2. **Active User**: User must exist in Firestore `users` collection with `status: 'active'`
3. **API Key**: Optional, depending on your environment configuration

## Test with PowerShell (when you have a real UID)

```powershell
$body = @{
    timestamp = (Get-Date).ToString("o")
    level = "info"
    severity = "INFO"
    message = "Test enhanced logging with Firebase UID auth"
    uid = "your-actual-firebase-uid-here"
    area = "testing"
    api = "manual-test"
    status = 200
    success = $true
    durationMs = 150
    payload = @{
        operation = "test"
        version = "2.0"
    }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri "https://app-logs-7bpeqovfmq-de.a.run.app" -Headers @{ 'Content-Type' = 'application/json'; 'X-API-Key' = 'your-api-key-if-required' } -Body $body
```

## Expected Response

**Success:**
```json
{ "ok": true }
```

**Authentication Error:**
```json
{ 
  "ok": false, 
  "error": "Authentication failed", 
  "message": "Firebase user not found for UID: ..." 
}
```

## What Happens Server-Side

1. Validates required fields (`timestamp`, `level`, `severity`, `message`, `uid`)
2. Verifies Firebase UID exists in Firebase Auth
3. Looks up user in Firestore `users` collection (by document ID or `uid` field)
4. Checks user status is 'active'
5. Extracts user context (email, name, company, store, role)
6. Writes to Firestore `appLogs` collection with enriched user context
7. Prepares for future Cloud Logging integration

## Benefits

- **No UI Authentication Errors**: UI doesn't need service account keys
- **Enhanced Security**: Server-side UID verification with user status checks
- **Automatic Context**: User/company/store data automatically added to logs
- **Dual Storage**: Firestore + future Cloud Logging support
- **Better Analytics**: Structured logs with user context for filtering and analysis

## Next Steps

1. Get a valid Firebase UID from your authentication system
2. Test the endpoint with real user data
3. Update your Angular LoggerService to use the new format
4. Deploy the Cloud Logging integration when the package is properly installed