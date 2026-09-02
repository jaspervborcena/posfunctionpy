# Enhanced Cloud Logging Endpoint# App Logging HTTP Endpoint



## OverviewThis document describes the HTTP contract used by the frontend to send structured logs to the Python Cloud Function.

Enhanced cloud function endpoint that accepts log entries from the UI with Firebase auth UID for user verification, using internal service account for Google Cloud Logging operations. This eliminates authentication errors from the UI side.

 Endpoint (prod):

## Key Features  - Cloud Run URL: `https://app-logs-7bpeqovfmq-de.a.run.app`

- **No UI Authentication**: UI only needs to pass Firebase UID, no need for service account keys  - Functions alias: `https://asia-east1-jasperpos-1dfd5.cloudfunctions.net/app_logs`

- **Internal Authentication**: Cloud function uses internal service account for all logging operations

- **Dual Logging**: Writes to both Google Cloud Logging (primary) and Firestore (backup/analytics)## Request Body (LogEntry)

- **User Context Enrichment**: Automatically adds user, company, and store context to logsA JSON object with these fields (required marked with •):

- **Enhanced Security**: Verifies Firebase UID exists and user is active



## EndpointsExample:

- **Cloud Run URL**: `https://app-logs-7bpeqovfmq-de.a.run.app````json

- **Functions alias**: `https://asia-east1-jasperpos-1dfd5.cloudfunctions.net/app_logs`{

  "timestamp": "2025-11-01T10:12:34.567Z",

## Request Format  "level": "info",

```typescript  "severity": "INFO",

{  "message": "Product created",

  "timestamp": "2025-11-06T08:30:00.000Z",  // • Required  "area": "UI",

  "level": "info",                          // • Required ('debug', 'info', 'warn', 'error')  "api": "products",

  "severity": "INFO",                       // • Required ('DEBUG', 'INFO', 'WARNING', 'ERROR')  "collectionPath": "products",

  "message": "Product updated successfully", // • Required  "docId": "abc123",

  "uid": "firebase-user-uid-here",          // • Required: Firebase UID for verification  "status": 200,

    "success": true,

  // Optional context fields  "durationMs": 42,

  "area": "products",  "correlationId": "corr-001",

  "api": "firestore.update",   "companyId": "COMP1",

  "collectionPath": "products",  "storeId": "STORE1",

  "docId": "product-123",  "userId": "USER1",

  "correlationId": "req-456",  "payload": { "op": "create", "id": "abc123" },

  "status": 200,                            // Optional: 200, 400, 500  "labels": { "env": "prod" }

  "success": true,                          // Optional: boolean}

  "durationMs": 250,```

  "payload": { /* sanitized data */ },

  "labels": { "feature": "inventory" },## Response

  "error": { /* error object if applicable */ }

}## Storage

```Logs are written to Firestore collection `appLogs` as-is, with minor sanitization:



## Required Fields## Security and CORS

- `timestamp`: ISO 8601 timestampEnvironment variables (set at deploy time) control behavior:

- `level`: Log level ('debug', 'info', 'warn', 'error')

- `severity`: Severity ('DEBUG', 'INFO', 'WARNING', 'ERROR')  - Comma-separated list of allowed origins, e.g.: `https://app.example.com,https://staging.example.com`

- `message`: Log message string  - When `true`, requests must include header `X-API-Key: <value>`

- `uid`: Firebase user UID for authentication  - The API key value that clients must send when required



## Authentication FlowIf you want to enable API key protection and restrict origins, share your origin(s) and preferred key and we’ll configure them.

1. UI passes Firebase UID in request body

2. Cloud function verifies UID exists in Firebase Auth## PowerShell test

3. Cloud function looks up user data in Firestore `users` collection```powershell

4. Cloud function checks user status is 'active'$body = @{ 

5. Cloud function extracts user context (company, store, role)  timestamp = (Get-Date).ToString("o"); level = "info"; severity = "INFO"; message = "UI test log";

6. Cloud function uses internal service account for logging operations  area = "UI"; api = "products"; collectionPath = "products"; docId = "abc123";

  status = 200; success = $true; durationMs = 42; correlationId = "corr-001";

## Enhanced Logging Features  companyId = "COMP1"; storeId = "STORE1"; userId = "USER1";

  payload = @{ op = "create"; id = "abc123" }

### User Context Enrichment} | ConvertTo-Json -Depth 5

Automatically adds user context to all logs:

```jsonInvoke-RestMethod -Method Post -Uri "https://app-logs-7bpeqovfmq-de.a.run.app" -Headers @{ 'X-API-Key' = '<YOUR-KEY>' } -ContentType "application/json" -Body $body

{```

  "user": {

    "userId": "firebase-uid",## Python function sketch (implemented)

    "userEmail": "user@example.com", The deployed function is defined in `functions/app_logs.py` and already matches this contract. It performs JSON validation, optional API key check, CORS, and writes to Firestore.

    "userName": "John Doe",
    "companyId": "company-123",
    "storeId": "store-456", 
    "roleId": "manager"
  }
}
```

### Dual Storage
- **Primary**: Google Cloud Logging with structured data and labels
- **Secondary**: Firestore `appLogs` collection for analytics and backup

### Data Sanitization
- Truncates large messages (>2000 chars)
- Limits payload size (>20KB gets truncated)
- Removes sensitive fields during sanitization

## Response Format
```json
// Success
{ "ok": true }

// Error
{ "ok": false, "error": "error message" }
```

## UI Integration
Update your Angular LoggerService to use the new format:

```typescript
private log(level: LogLevel, message: string, ctx: LogContext & { error?: any } = {}) {
  if (!this.shouldLog(level)) return;

  // Get Firebase UID (you'll need to inject AuthService)
  const currentUser = this.authService.currentUser; // Implement this
  if (!currentUser?.uid) {
    console.warn('Cannot log without authenticated user');
    return;
  }

  const entry = {
    timestamp: new Date().toISOString(),
    level,
    severity: this.asSeverity(level),
    message,
    uid: currentUser.uid,  // Pass Firebase UID instead of full auth
    ...ctx,
    payload: this.sanitize(ctx.payload),
  };

  this.consoleSink(entry);

  if (this.remoteEndpoint) {
    const headers: HttpHeaders = new HttpHeaders({ 'Content-Type': 'application/json' })
      .set('X-API-Key', this.apiKey || '');
    this.http.post(this.remoteEndpoint, entry, { headers }).subscribe({
      next: () => {},
      error: (err) => console.warn('Remote logging failed:', err)
    });
  }
}
```

## Environment Variables
- `CLOUD_LOGGING_ALLOWED_ORIGINS`: CORS origins (default: "*")
- `CLOUD_LOGGING_REQUIRE_API_KEY`: Enable API key validation (default: false)
- `CLOUD_LOGGING_API_KEY`: API key for validation

## Error Handling
- **401**: Invalid/inactive Firebase UID or user not found
- **400**: Malformed request or missing required fields
- **500**: Server-side logging system failures
- Always logs errors server-side for debugging

## Google Cloud Logging Structure
Logs appear in Cloud Logging with:
- **Resource Type**: `cloud_function`
- **Function Name**: `app_logs`
- **Severity**: Mapped from log level
- **Labels**: Include userId, storeId, companyId for filtering
- **Structured Payload**: Full context and user information

## Testing
```powershell
$body = @{
  timestamp = (Get-Date).ToString("o")
  level = "info"
  severity = "INFO"
  message = "Test log from PowerShell"
  uid = "your-firebase-uid-here"
  area = "testing"
  api = "manual-test"
  status = 200
  success = $true
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri "https://app-logs-7bpeqovfmq-de.a.run.app" -Headers @{ 'X-API-Key' = 'your-api-key' } -ContentType "application/json" -Body $body
```

## Benefits Over Previous Version
1. **No Authentication Errors**: UI doesn't handle service account keys
2. **Better Security**: Server-side UID verification with user status checking
3. **Enhanced Context**: Automatic user/company/store context enrichment
4. **Dual Storage**: Primary Cloud Logging + backup Firestore
5. **Better Monitoring**: Structured logs with labels for filtering
6. **Scalability**: Uses Firebase internal service account with proper IAM