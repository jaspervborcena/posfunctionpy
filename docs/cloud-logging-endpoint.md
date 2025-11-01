# App Logging HTTP Endpoint

This document describes the HTTP contract used by the frontend to send structured logs to the Python Cloud Function.

 Endpoint (prod):
  - Cloud Run URL: `https://app-logs-7bpeqovfmq-de.a.run.app`
  - Functions alias: `https://asia-east1-jasperpos-1dfd5.cloudfunctions.net/app_logs`

## Request Body (LogEntry)
A JSON object with these fields (required marked with •):


Example:
```json
{
  "timestamp": "2025-11-01T10:12:34.567Z",
  "level": "info",
  "severity": "INFO",
  "message": "Product created",
  "area": "UI",
  "api": "products",
  "collectionPath": "products",
  "docId": "abc123",
  "status": 200,
  "success": true,
  "durationMs": 42,
  "correlationId": "corr-001",
  "companyId": "COMP1",
  "storeId": "STORE1",
  "userId": "USER1",
  "payload": { "op": "create", "id": "abc123" },
  "labels": { "env": "prod" }
}
```

## Response

## Storage
Logs are written to Firestore collection `appLogs` as-is, with minor sanitization:

## Security and CORS
Environment variables (set at deploy time) control behavior:

  - Comma-separated list of allowed origins, e.g.: `https://app.example.com,https://staging.example.com`
  - When `true`, requests must include header `X-API-Key: <value>`
  - The API key value that clients must send when required

If you want to enable API key protection and restrict origins, share your origin(s) and preferred key and we’ll configure them.

## PowerShell test
```powershell
$body = @{ 
  timestamp = (Get-Date).ToString("o"); level = "info"; severity = "INFO"; message = "UI test log";
  area = "UI"; api = "products"; collectionPath = "products"; docId = "abc123";
  status = 200; success = $true; durationMs = 42; correlationId = "corr-001";
  companyId = "COMP1"; storeId = "STORE1"; userId = "USER1";
  payload = @{ op = "create"; id = "abc123" }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri "https://app-logs-7bpeqovfmq-de.a.run.app" -Headers @{ 'X-API-Key' = '<YOUR-KEY>' } -ContentType "application/json" -Body $body
```

## Python function sketch (implemented)
The deployed function is defined in `functions/app_logs.py` and already matches this contract. It performs JSON validation, optional API key check, CORS, and writes to Firestore.
