# UI Integration Guide & Testing Examples

## 🚀 How Your Angular UI Will Use the Enhanced Logging Endpoint

### 1. **Updated LoggerService Implementation**

Here's how to modify your existing Angular LoggerService to use the new Firebase UID authentication:

```typescript
import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { environment } from '../../../environments/environment';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';
export type Severity = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';

export interface LogContext {
  area?: string;
  api?: 'firestore.add' | 'firestore.set' | 'firestore.update' | 'firestore.delete' | string;
  collectionPath?: string;
  docId?: string;
  correlationId?: string;
  userId?: string;
  companyId?: string;
  storeId?: string;
  status?: 200 | 400 | 500;
  success?: boolean;
  durationMs?: number;
  payload?: unknown;
  labels?: Record<string, string>;
}

export interface LogEntry extends LogContext {
  timestamp: string;
  level: LogLevel;
  severity: Severity;
  message: string;
  uid: string;  // ✨ NEW: Firebase UID instead of full auth
  error?: { name?: string; message: string; code?: string; stack?: string };
}

@Injectable({ providedIn: 'root' })
export class LoggerService {
  private minLevel: LogLevel = environment.production ? 'info' : 'debug';
  private remoteEndpoint = (environment as any).cloudLoggingEndpoint as string | undefined;
  private apiKey = (environment as any).cloudLoggingApiKey as string | undefined;

  // ✨ NEW: Inject your AuthService to get current user UID
  constructor(
    private http: HttpClient,
    private authService: AuthService  // Your existing auth service
  ) {}

  debug(message: string, ctx: LogContext = {}) { this.log('debug', message, ctx); }
  info(message: string, ctx: LogContext = {})  { this.log('info', message, ctx); }
  warn(message: string, ctx: LogContext = {})  { this.log('warn', message, ctx); }
  error(message: string, ctx: LogContext = {}, err?: unknown) {
    const errorObj = this.normalizeError(err);
    this.log('error', message, { ...ctx, ...(errorObj ? { error: errorObj } : {}) } as any);
  }

  // Convenience helpers for DB ops
  dbSuccess(message: string, ctx: Omit<LogContext, 'status' | 'success'>) {
    this.info(message, { ...ctx, success: true, status: 200 });
  }
  dbFailure(message: string, ctx: Omit<LogContext, 'status' | 'success'>, err?: unknown) {
    this.error(message, { ...ctx, success: false, status: 400 }, err);
  }

  private log(level: LogLevel, message: string, ctx: LogContext & { error?: any } = {}) {
    if (!this.shouldLog(level)) return;

    // ✨ NEW: Get Firebase UID from authenticated user
    const currentUser = this.authService.currentUser;
    if (!currentUser?.uid) {
      console.warn('Cannot log without authenticated user - Firebase UID required');
      // Still do console logging
      this.consoleSink({ 
        timestamp: new Date().toISOString(),
        level, 
        severity: this.asSeverity(level), 
        message, 
        uid: 'unauthenticated',
        ...ctx 
      } as LogEntry);
      return;
    }

    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      severity: this.asSeverity(level),
      message,
      uid: currentUser.uid,  // ✨ NEW: Just pass Firebase UID
      ...ctx,
      payload: this.sanitize(ctx.payload),
    };

    this.consoleSink(entry);

    if (this.remoteEndpoint) {
      const headers: HttpHeaders = new HttpHeaders({ 'Content-Type': 'application/json' });
      
      // ✨ OPTIONAL: Add API key if configured
      if (this.apiKey) {
        headers.set('X-API-Key', this.apiKey);
      }

      this.http.post(this.remoteEndpoint, entry, { headers }).subscribe({
        next: (response) => {
          console.debug('✅ Remote logging successful', response);
        },
        error: (err) => {
          console.warn('❌ Remote logging failed:', err);
          // Don't throw - logging failures shouldn't break the app
        }
      });
    }
  }

  private consoleSink(entry: LogEntry) {
    const { level, message, ...rest } = entry;
    const fn = level === 'error' ? console.error
      : level === 'warn' ? console.warn
      : level === 'info' ? console.info
      : console.debug;

    fn('[APP]', message, rest);
  }

  private shouldLog(level: LogLevel): boolean {
    const order: Record<LogLevel, number> = { debug: 10, info: 20, warn: 30, error: 40 };
    return order[level] >= order[this.minLevel];
  }

  private asSeverity(level: LogLevel): Severity {
    return level === 'debug' ? 'DEBUG'
      : level === 'info' ? 'INFO'
      : level === 'warn' ? 'WARNING'
      : 'ERROR';
  }

  private sanitize(payload: unknown): unknown {
    if (!payload || typeof payload !== 'object') return payload;
    const redactKeys = ['password', 'token', 'accessToken', 'refreshToken', 'email', 'phone'];
    try {
      const obj = JSON.parse(JSON.stringify(payload));
      if (Array.isArray(obj)) {
        return obj.map((item) => this.sanitize(item));
      }
      const out: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(obj)) {
        out[k] = redactKeys.includes(k) ? '[REDACTED]' : v as unknown;
      }
      return out;
    } catch {
      return undefined;
    }
  }

  private normalizeError(err: unknown) {
    if (!err) return undefined;
    if (err instanceof Error) {
      const code = (err as any).code as string | undefined;
      return { name: err.name, message: err.message, code, stack: err.stack };
    }
    if (typeof err === 'string') return { message: err };
    try { return { message: JSON.stringify(err) }; } catch { return { message: String(err) }; }
  }
}
```

### 2. **Usage Examples in Your Components**

```typescript
// In your product service
@Injectable()
export class ProductService {
  constructor(
    private firestore: AngularFirestore,
    private logger: LoggerService
  ) {}

  async createProduct(productData: any): Promise<string> {
    const start = Date.now();
    const correlationId = `create-product-${Date.now()}`;
    
    try {
      this.logger.info('Creating new product', {
        area: 'products',
        api: 'firestore.add',
        collectionPath: 'products',
        correlationId,
        payload: { productName: productData.name, category: productData.category }
      });

      const docRef = await this.firestore.collection('products').add(productData);
      
      this.logger.dbSuccess('Product created successfully', {
        area: 'products',
        api: 'firestore.add',
        collectionPath: 'products',
        docId: docRef.id,
        correlationId,
        durationMs: Date.now() - start,
        payload: { productId: docRef.id, productName: productData.name }
      });

      return docRef.id;
    } catch (error) {
      this.logger.dbFailure('Failed to create product', {
        area: 'products',
        api: 'firestore.add',
        collectionPath: 'products',
        correlationId,
        durationMs: Date.now() - start,
        payload: { productName: productData.name }
      }, error);
      throw error;
    }
  }

  async updateProduct(productId: string, updates: any): Promise<void> {
    const start = Date.now();
    const correlationId = `update-product-${productId}-${Date.now()}`;
    
    try {
      this.logger.info('Updating product', {
        area: 'products',
        api: 'firestore.update',
        collectionPath: 'products',
        docId: productId,
        correlationId,
        payload: { updates }
      });

      await this.firestore.collection('products').doc(productId).update(updates);
      
      this.logger.dbSuccess('Product updated successfully', {
        area: 'products',
        api: 'firestore.update',
        collectionPath: 'products',
        docId: productId,
        correlationId,
        durationMs: Date.now() - start,
        payload: { productId, updates }
      });
    } catch (error) {
      this.logger.dbFailure('Failed to update product', {
        area: 'products',
        api: 'firestore.update',
        collectionPath: 'products',
        docId: productId,
        correlationId,
        durationMs: Date.now() - start,
        payload: { productId, updates }
      }, error);
      throw error;
    }
  }
}
```

### 3. **Environment Configuration**

Update your `environment.ts` files:

```typescript
// environment.ts
export const environment = {
  production: false,
  cloudLoggingEndpoint: 'https://app-logs-7bpeqovfmq-de.a.run.app',
  cloudLoggingApiKey: 'your-api-key-if-required'  // Optional
};

// environment.prod.ts
export const environment = {
  production: true,
  cloudLoggingEndpoint: 'https://app-logs-7bpeqovfmq-de.a.run.app',
  cloudLoggingApiKey: 'your-production-api-key'  // Optional
};
```

## 🧪 Sample cURL Commands for Testing

### 1. **Basic Success Log Test**

```bash
curl -X POST https://app-logs-7bpeqovfmq-de.a.run.app \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-if-required" \
  -d '{
    "timestamp": "2025-11-06T09:30:00.000Z",
    "level": "info",
    "severity": "INFO", 
    "message": "Product created successfully via cURL test",
    "uid": "your-actual-firebase-uid-here",
    "area": "products",
    "api": "firestore.add",
    "collectionPath": "products",
    "docId": "product-test-123",
    "correlationId": "curl-test-001",
    "status": 200,
    "success": true,
    "durationMs": 250,
    "payload": {
      "productName": "Test Product",
      "category": "Electronics",
      "price": 99.99
    },
    "labels": {
      "testType": "curl",
      "environment": "development"
    }
  }'
```

### 2. **Error Log Test**

```bash
curl -X POST https://app-logs-7bpeqovfmq-de.a.run.app \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-if-required" \
  -d '{
    "timestamp": "2025-11-06T09:31:00.000Z",
    "level": "error",
    "severity": "ERROR",
    "message": "Failed to update product - validation error",
    "uid": "your-actual-firebase-uid-here", 
    "area": "products",
    "api": "firestore.update",
    "collectionPath": "products",
    "docId": "product-456",
    "correlationId": "curl-error-test-002",
    "status": 400,
    "success": false,
    "durationMs": 150,
    "payload": {
      "productId": "product-456",
      "attemptedUpdates": {
        "price": -10
      }
    },
    "error": {
      "name": "ValidationError", 
      "message": "Price cannot be negative",
      "code": "INVALID_PRICE"
    },
    "labels": {
      "testType": "curl-error",
      "errorCategory": "validation"
    }
  }'
```

### 3. **Complex Business Operation Test**

```bash
curl -X POST https://app-logs-7bpeqovfmq-de.a.run.app \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-if-required" \
  -d '{
    "timestamp": "2025-11-06T09:32:00.000Z",
    "level": "info",
    "severity": "INFO",
    "message": "Order processing completed",
    "uid": "your-actual-firebase-uid-here",
    "area": "orders", 
    "api": "business.process-order",
    "collectionPath": "orders",
    "docId": "order-789",
    "correlationId": "order-process-003",
    "status": 200,
    "success": true,
    "durationMs": 1250,
    "payload": {
      "orderId": "order-789",
      "customerId": "customer-123",
      "items": [
        {"productId": "prod-1", "quantity": 2, "price": 29.99},
        {"productId": "prod-2", "quantity": 1, "price": 19.99}
      ],
      "totalAmount": 79.97,
      "paymentMethod": "credit_card",
      "shippingAddress": {
        "street": "123 Main St",
        "city": "Anytown", 
        "zipCode": "12345"
      }
    },
    "labels": {
      "testType": "curl-business",
      "orderType": "online",
      "paymentMethod": "credit_card"
    }
  }'
```

### 4. **PowerShell Test (Windows)**

```powershell
$body = @{
    timestamp = (Get-Date).ToString("o")
    level = "info"
    severity = "INFO"
    message = "PowerShell test of enhanced logging"
    uid = "your-actual-firebase-uid-here"
    area = "testing"
    api = "powershell.test" 
    correlationId = "ps-test-004"
    status = 200
    success = $true
    durationMs = 100
    payload = @{
        testFramework = "PowerShell"
        version = "7.0"
        testData = @{
            nested = "object"
            array = @(1, 2, 3)
        }
    }
    labels = @{
        testType = "powershell"
        environment = "local"
    }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method Post -Uri "https://app-logs-7bpeqovfmq-de.a.run.app" -Headers @{ 
    'Content-Type' = 'application/json'
    'X-API-Key' = 'your-api-key-if-required' 
} -Body $body
```

## 📋 **Expected Responses**

### ✅ **Success Response**
```json
{
  "ok": true
}
```

### ❌ **Authentication Error Response**
```json
{
  "ok": false,
  "error": "Authentication failed", 
  "message": "Firebase user not found for UID: invalid-uid"
}
```

### ❌ **Validation Error Response**
```json
{
  "ok": false,
  "error": "Missing required field: uid"
}
```

## 🔍 **What Happens When You Send a Log**

1. **Request Validation**: Checks for required fields (`timestamp`, `level`, `severity`, `message`, `uid`)
2. **Firebase UID Verification**: Validates UID exists in Firebase Auth
3. **User Lookup**: Finds user in Firestore `users` collection 
4. **Status Check**: Ensures user status is `'active'`
5. **Context Enrichment**: Adds comprehensive user data to log
6. **Dual Storage**: Writes to Firestore `appLogs` + Cloud Logging (when available)
7. **Server Logging**: Detailed console output for debugging

## 🎯 **Key Benefits for Your UI**

1. **No Authentication Errors**: Just pass Firebase UID, no service account keys needed
2. **Automatic User Context**: User info automatically added to every log
3. **Complete Payload Preservation**: Everything you send is preserved for analysis
4. **Enhanced Security**: Server-side verification ensures only valid users can log
5. **Better Analytics**: Rich context for filtering and analysis in logs
6. **Debugging Support**: Detailed server-side logging for troubleshooting

## 🚀 **Ready to Use**

The enhanced logging endpoint is deployed and ready! Just update your LoggerService with the Firebase UID approach and start getting comprehensive user identification with every log entry.

**Endpoint**: `https://app-logs-7bpeqovfmq-de.a.run.app`