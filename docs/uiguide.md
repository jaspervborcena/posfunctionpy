# Reconciliation and Inventory API UI Guide

## Endpoint

`GET /get_recon_summary_bq`

| Environment | Base URL |
| --- | --- |
| Dev | `https://asia-east1-jasperpos-dev.cloudfunctions.net` |
| Prod | `https://asia-east1-jasperpos-1dfd5.cloudfunctions.net` |

The endpoint returns every `ordersSellingTracking` row where `isStockTracked` is `true`, for the requested store and `createdAt` range. Results are ordered by `createdAt` descending, then `orderId` ascending. This API currently returns all matching rows and does not paginate; use a reasonable date range in the UI.

## Request

Required query parameters:

| Parameter | Description |
| --- | --- |
| `storeId` | Store whose records the signed-in user is allowed to access. |
| `from` | Inclusive start date or timestamp. |
| `to` | End date or timestamp. |

Accepted date formats include `YYYYMMDD`, `YYYY-MM-DD`, `YYYYMMDDHHMMSS`, and ISO timestamps. Date-only values are interpreted as UTC midnight. If `to` is date-only, the endpoint advances the boundary by one day, so that calendar day is included. Timestamp `to` values are exclusive.

Example for all of October 1 through October 17, 2026:

```text
?storeId=store-123&from=2026-10-01&to=2026-10-17
```

The query uses the equivalent of:

```sql
WHERE storeId = @store_id
  AND isStockTracked = TRUE
  AND createdAt >= @start_timestamp
  AND createdAt < @end_timestamp
ORDER BY createdAt DESC, orderId
```

## Authentication

Send a Firebase ID token in the `Authorization` header:

```http
Authorization: Bearer <Firebase ID token>
```

The function checks the token and verifies that the caller has access to `storeId`. Do not send BigQuery credentials from the UI.

## Angular Example

This example uses AngularFire's `Auth` service. Set `environment.apiBaseUrl` to the environment-specific base URL in the table above.

```typescript
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Auth } from '@angular/fire/auth';
import { getIdToken } from 'firebase/auth';
import { firstValueFrom } from 'rxjs';
import { environment } from '../environments/environment';

export interface ReconSummaryResponse {
  success: boolean;
  store_id: string;
  from: string;
  to: string;
  count: number;
  rows: Array<Record<string, unknown>>;
}

@Injectable({ providedIn: 'root' })
export class ReconSummaryService {
  private readonly endpoint = `${environment.apiBaseUrl}/get_recon_summary_bq`;

  constructor(
    private readonly http: HttpClient,
    private readonly auth: Auth
  ) {}

  async getSummary(
    storeId: string,
    from: string,
    to: string
  ): Promise<ReconSummaryResponse> {
    const user = this.auth.currentUser;
    if (!user) {
      throw new Error('Sign in before loading reconciliation data.');
    }

    const token = await getIdToken(user);
    const params = new HttpParams()
      .set('storeId', storeId)
      .set('from', from)
      .set('to', to);

    return firstValueFrom(this.http.get<ReconSummaryResponse>(this.endpoint, {
      params,
      headers: { Authorization: `Bearer ${token}` }
    }));
  }
}
```

Example call from a component:

```typescript
const result = await this.reconSummaryService.getSummary(
  selectedStoreId,
  '2026-10-01',
  '2026-10-17'
);

this.rows = result.rows;
this.totalRows = result.count;
```

For a date picker that returns calendar dates, pass `YYYY-MM-DD` values directly. For explicit timestamps, include a timezone such as `Z` and make `to` the exclusive boundary, for example `2026-10-18T00:00:00Z` to include dates through October 17 UTC.

## Successful Response

Each row contains the BigQuery columns for that tracking record. Timestamp values are serialized as ISO strings and numeric values are JSON-compatible numbers.

```json
{
  "success": true,
  "store_id": "store-123",
  "from": "2026-10-01",
  "to": "2026-10-17",
  "count": 1,
  "rows": [
    {
      "orderId": "order-456",
      "storeId": "store-123",
      "isStockTracked": true,
      "createdAt": "2026-10-17T12:30:00+00:00"
    }
  ]
}
```

## Errors and UI Handling

| HTTP status | Meaning | UI handling |
| --- | --- | --- |
| `400` | Missing store/date parameter, invalid date, or `from` is later than `to`. | Show a validation message and keep the selected filters. |
| `401` | Firebase token is missing or invalid. | Refresh/sign in, then retry. |
| `403` | User is not authorized for the requested store. | Show an access-denied state; do not retry automatically. |
| `500` | BigQuery query failed. | Show a retry option and log the error without exposing credentials. |

Handle loading, empty, and error states separately. An empty result is a successful response with `count: 0` and `rows: []`.

---

## Inventory Summary API

### Endpoint

`GET /get_inventory_summary_bq`

| Environment | URL |
| --- | --- |
| Dev | `https://asia-east1-jasperpos-dev.cloudfunctions.net/get_inventory_summary_bq` |
| Prod | `https://asia-east1-jasperpos-1dfd5.cloudfunctions.net/get_inventory_summary_bq` |

This authenticated endpoint returns the inventory-tracking records for the requested store and `createdAt` range. It returns all columns from `inventoryTracking`, including product/item identifiers, quantities, stock flags, sale tracking references, prices, and timestamps. Results are ordered newest first. The endpoint currently returns all matching records without pagination, so UI callers should use a suitably narrow date range.

### Request parameters

All three query parameters are required:

| Parameter | Description |
| --- | --- |
| `storeId` | Store the signed-in user is authorized to access. |
| `from` | Inclusive UTC start timestamp in `YYYYMMDDHHMMSS` format. |
| `to` | UTC timestamp in `YYYYMMDDHHMMSS` format. The entire specified second is included. |

For example, to request all of October 1 through October 17, 2026 UTC, send:

```text
?storeId=store-123&from=20261001000000&to=20261017235959
```

The endpoint filters on `createdAt`, and the date values are interpreted as UTC. If the date picker displays local time, convert the selected range to UTC before creating these parameters.

The query applies the equivalent of:

```sql
WHERE storeId = @storeId
  AND createdAt >= @startDate
  AND createdAt < TIMESTAMP_ADD(@endDate, INTERVAL 1 SECOND)
ORDER BY createdAt DESC
```

### Angular service example

This uses Angular `HttpClient` and AngularFire `Auth`. Configure `environment.apiBaseUrl` with the environment-specific base URL in the table above.

```typescript
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Auth } from '@angular/fire/auth';
import { getIdToken } from 'firebase/auth';
import { firstValueFrom } from 'rxjs';
import { environment } from '../environments/environment';

export interface InventoryTrackingRow {
  inventoryTrackingId: string | null;
  batchId: string | null;
  companyId: string | null;
  costPrice: number | null;
  createdAt: string | null;
  createdBy: string | null;
  deductedAt: string | null;
  deductedBy: string | null;
  eventType: string | null;
  invoiceNumber: string | null;
  itemCode: string | null;
  isStockTracked: boolean | null;
  note: string | null;
  orderId: string | null;
  productCode: string | null;
  productId: string | null;
  productName: string | null;
  quantity: number | null;
  refId: string | null;
  runningBalanceTotalStock: number | null;
  saleLineIndex: number | null;
  saleTrackingId: string | null;
  sellingPrice: number | null;
  skuId: string | null;
  stockMovement: boolean | null;
  storeId: string | null;
}

export interface InventorySummaryResponse {
  success: boolean;
  storeId: string;
  from: string;
  to: string;
  count: number;
  inventory: InventoryTrackingRow[];
}

@Injectable({ providedIn: 'root' })
export class InventorySummaryService {
  private readonly endpoint =
    `${environment.apiBaseUrl}/get_inventory_summary_bq`;

  constructor(
    private readonly http: HttpClient,
    private readonly auth: Auth
  ) {}

  async getSummary(
    storeId: string,
    from: string,
    to: string
  ): Promise<InventorySummaryResponse> {
    const user = this.auth.currentUser;
    if (!user) {
      throw new Error('Sign in before loading inventory data.');
    }

    const token = await getIdToken(user);
    const params = new HttpParams()
      .set('storeId', storeId)
      .set('from', from)
      .set('to', to);

    return firstValueFrom(this.http.get<InventorySummaryResponse>(
      this.endpoint,
      {
        params,
        headers: { Authorization: `Bearer ${token}` }
      }
    ));
  }
}
```

### Calling it from a UI component

An HTML date input returns `YYYY-MM-DD`. Convert calendar dates to UTC start/end seconds before calling the service:

```typescript
function toUtcInventoryTimestamp(date: string, endOfDay = false): string {
  const yyyymmdd = date.replace(/-/g, '');
  return `${yyyymmdd}${endOfDay ? '235959' : '000000'}`;
}

async loadInventory(): Promise<void> {
  this.loading = true;
  this.error = null;
  this.rows = [];

  try {
    const result = await this.inventorySummaryService.getSummary(
      this.selectedStoreId,
      toUtcInventoryTimestamp(this.fromDate),
      toUtcInventoryTimestamp(this.toDate, true)
    );
    this.rows = result.inventory;
  } catch (error) {
    console.error('Inventory request failed.', error);
    this.error = 'Could not load inventory. Please try again.';
  } finally {
    this.loading = false;
  }
}
```

Bind `loading` to a spinner, `error` to an error message/retry action, and `rows` to the inventory table. When `rows` is empty after a successful response, show an empty state instead of treating it as an error. For example, display `productName`, `itemCode`, `quantity`, `eventType`, `createdAt`, and `runningBalanceTotalStock` as useful table columns, while retaining the other fields for detail views or exports.

### Successful response

The `inventory` array contains all fields for each matching row. Timestamps are ISO strings, and BigQuery `NUMERIC` values are JSON numbers.

```json
{
  "success": true,
  "storeId": "store-123",
  "from": "20261001000000",
  "to": "20261017235959",
  "count": 1,
  "inventory": [
    {
      "inventoryTrackingId": "tracking-789",
      "storeId": "store-123",
      "productId": "product-456",
      "productName": "Widget",
      "itemCode": "WID-001",
      "quantity": 3,
      "isStockTracked": true,
      "stockMovement": true,
      "sellingPrice": 150.0,
      "createdAt": "2026-10-17T12:30:00+00:00"
    }
  ]
}
```

### Errors

| HTTP status | Meaning | UI handling |
| --- | --- | --- |
| `400` | Missing parameter, malformed timestamp, or `from` is after `to`. | Validate the store/date filters and preserve the user's selection. |
| `401` | Firebase ID token is missing or invalid. | Sign in again, then retry. |
| `403` | User cannot access the requested store. | Show an access-denied message; do not retry automatically. |
| `500` | BigQuery query failed. | Show a retry option; do not expose credentials or internal details. |
