# Sales Summary, Reconciliation, and Inventory API UI Guide

## Sales Summary Details API

Use this endpoint from the sales summary page to load order details for a store and date range. The endpoint requires a Firebase ID token and verifies that the signed-in user can access the requested store.

| Environment | Base URL |
| --- | --- |
| Dev | `https://asia-east1-jasperpos-dev.cloudfunctions.net` |
| Prod | `https://asia-east1-jasperpos-1dfd5.cloudfunctions.net` |

The compatibility route is `GET /salesSummaryDetailsProxy`. For example:

```text
https://asia-east1-jasperpos-1dfd5.cloudfunctions.net/salesSummaryDetailsProxy?storeId=FryfDq66vnWbLWxken50&from=20261028&to=20261028&page_number=1&page_size=50
```

### Query parameters

| Parameter | Description |
| --- | --- |
| `storeId` | Required store ID the signed-in user is authorized to access. |
| `from` | Required inclusive start date. Use `YYYYMMDD` or `YYYY-MM-DD`. |
| `to` | Required end date. Date-only values include the entire day. |
| `page_number` | Optional, 1-based page number. Defaults to `1`. |
| `page_size` | Optional number of orders per page. Defaults to `100`; maximum is `100`. |

### Angular service example

Configure `environment.apiBaseUrl` to the appropriate base URL in the table above. AngularFire's `Auth` service supplies the current user's Firebase ID token; do not put BigQuery credentials in the UI.

```typescript
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Auth } from '@angular/fire/auth';
import { getIdToken } from 'firebase/auth';
import { firstValueFrom } from 'rxjs';
import { environment } from '../environments/environment';

export interface SalesSummaryDetailsResponse {
  success: boolean;
  store_id: string;
  from: string;
  to: string;
  count: number;
  page_size: number;
  page_number: number;
  has_more: boolean;
  orders: Array<Record<string, unknown>>;
}

@Injectable({ providedIn: 'root' })
export class SalesSummaryDetailsService {
  private readonly endpoint =
    `${environment.apiBaseUrl}/salesSummaryDetailsProxy`;

  constructor(
    private readonly http: HttpClient,
    private readonly auth: Auth
  ) {}

  async getOrders(
    storeId: string,
    from: string,
    to: string,
    pageNumber = 1,
    pageSize = 50
  ): Promise<SalesSummaryDetailsResponse> {
    const user = this.auth.currentUser;
    if (!user) {
      throw new Error('Sign in before loading sales details.');
    }

    const token = await getIdToken(user);
    const params = new HttpParams()
      .set('storeId', storeId)
      .set('from', from)
      .set('to', to)
      .set('page_number', pageNumber)
      .set('page_size', pageSize);

    return firstValueFrom(this.http.get<SalesSummaryDetailsResponse>(
      this.endpoint,
      {
        params,
        headers: { Authorization: `Bearer ${token}` }
      }
    ));
  }
}
```

### Call it from a UI component

Date-only values in `YYYY-MM-DD` format include both selected calendar days. Use `has_more` to decide whether to offer a next-page action.

```typescript
async loadSalesDetails(): Promise<void> {
  this.loading = true;
  this.error = null;

  try {
    const result = await this.salesSummaryDetailsService.getOrders(
      this.selectedStoreId,
      this.fromDate,
      this.toDate,
      this.pageNumber,
      50
    );
    this.orders = result.orders;
    this.hasMore = result.has_more;
  } catch (error) {
    console.error('Sales details request failed.', error);
    this.error = 'Could not load sales details. Please try again.';
  } finally {
    this.loading = false;
  }
}
```

Handle loading, empty (`orders.length === 0`), and error states separately. On the next-page action, increment `pageNumber` and call the service again. The API caps `page_size` at 100.

### Errors

| HTTP status | Meaning | UI handling |
| --- | --- | --- |
| `400` | Required parameter is missing, date is invalid, or pagination values are invalid. | Validate the filters and preserve the user's selection. |
| `401` | Firebase ID token is missing or invalid. | Sign in again, then retry. |
| `403` | User cannot access the requested store. | Show an access-denied message; do not retry automatically. |
| `500` | BigQuery query failed. | Show a retry option without exposing internal details. |

The compatibility route must be deployed to the selected Firebase project before the UI can call it.

---

## Reconciliation and Inventory API UI Guide

## Endpoint

`GET /get_recon_summary_bq`

| Environment | Base URL |
| --- | --- |
| Dev | `https://asia-east1-jasperpos-dev.cloudfunctions.net` |
| Prod | `https://asia-east1-jasperpos-1dfd5.cloudfunctions.net` |

The endpoint returns one row per invoice with inventory exceptions, for the requested store and sales `createdAt` range. It compares stock-tracked sales quantities against the sum of stock-tracked `inventoryTracking.quantity` rows matching the same store, invoice, and item code. Invoices with no matching inventory row for a sales item or with a quantity mismatch are returned; invoices with no detected mismatch are omitted. Results are ordered by invoice creation time descending. The endpoint currently returns all matching exceptions and does not paginate; use a reasonable date range in the UI.

The summary includes the invoice date, cashier, sum of tracked line totals, line count, sales and inventory quantity totals, issue counts, issue codes, and severity. Missing inventory is `critical`; a quantity mismatch without missing inventory is `high`. The current schema has no FIFO-skipped field, so FIFO issues are not classified here.
The missing/mismatch counts are counted per distinct invoice/item-code group, while `itemCount` counts sales tracking rows.

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

The comparison uses the equivalent of:

```sql
GROUP BY storeId, invoiceNumber, itemCode
-- Sum stock-tracked sales and inventory quantities, then report missing
-- inventory rows or unequal quantities for each invoice/item.
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
  rows: ReconException[];
}

export interface ReconException {
  invoiceNumber: string;
  createdAt: string;
  cashierName: string | null;
  totalAmount: number;
  itemCount: number;
  salesQty: number;
  inventoryQty: number;
  missingInventoryItemCount: number;
  quantityMismatchItemCount: number;
  hasInventoryIssue: true;
  issues: Array<'NO_INVENTORY' | 'QTY_MISMATCH'>;
  issueType: 'NO_INVENTORY' | 'QTY_MISMATCH' | 'MULTIPLE';
  severity: 'critical' | 'high';
}

export interface ReconInventoryRow {
  inventoryTrackingId: string;
  batchId: string | null;
  eventType: string | null;
  quantity: number | null;
  createdAt: string | null;
  deductedAt: string | null;
  itemCode: string | null;
  productCode: string | null;
  productId: string | null;
  productName: string | null;
  runningBalanceTotalStock: number | null;
  saleLineIndex: number | null;
  saleTrackingId: string | null;
  stockMovement: boolean | null;
}

export interface ReconInvoiceItem {
  invoiceNumber: string;
  itemCode: string | null;
  productName: string | null;
  salesQty: number;
  salesAmount: number;
  salesLineCount: number;
  inventoryQty: number;
  quantityDifference: number;
  issueType: 'NO_INVENTORY' | 'QTY_MISMATCH' | 'OK';
  inventoryRows: ReconInventoryRow[];
}

export interface ReconInvoiceDetailsResponse {
  success: boolean;
  storeId: string;
  invoiceNumber: string;
  count: number;
  items: ReconInvoiceItem[];
}

@Injectable({ providedIn: 'root' })
export class ReconSummaryService {
  private readonly endpoint = `${environment.apiBaseUrl}/get_recon_summary_bq`;
  private readonly detailsEndpoint =
    `${environment.apiBaseUrl}/get_recon_invoice_details_bq`;

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

  async getInvoiceDetails(
    storeId: string,
    invoiceNumber: string
  ): Promise<ReconInvoiceDetailsResponse> {
    const user = this.auth.currentUser;
    if (!user) {
      throw new Error('Sign in before loading reconciliation details.');
    }

    const token = await getIdToken(user);
    const params = new HttpParams()
      .set('storeId', storeId)
      .set('invoiceNumber', invoiceNumber);

    return firstValueFrom(this.http.get<ReconInvoiceDetailsResponse>(
      this.detailsEndpoint,
      {
        params,
        headers: { Authorization: `****** }
      }
    ));
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

## Parent Exception Grid

Render one row for each entry in `rows`. The API request does not change; the grid should use the invoice-level response fields instead of expecting raw tracking rows.

| Grid column | Response fields |
| --- | --- |
| Invoice | `invoiceNumber` |
| Date | `createdAt` |
| Cashier | `cashierName` |
| Severity | `severity` |
| Issues | `issues`, `missingInventoryItemCount`, `quantityMismatchItemCount` |
| Tracking ledger | `totalAmount`, `itemCount`, `salesQty`, `inventoryQty` |
| Actions | Open invoice details using `invoiceNumber` |

Example Angular template:

```html
<div class="recon-grid-wrap">
  <table class="recon-grid">
    <thead>
      <tr>
        <th>Invoice</th>
        <th>Date</th>
        <th>Cashier</th>
        <th>Severity</th>
        <th>Issues</th>
        <th>Tracking ledger</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      <tr *ngFor="let row of rows">
        <td>{{ row.invoiceNumber }}</td>
        <td>{{ row.createdAt | date:'short' }}</td>
        <td>{{ row.cashierName || '—' }}</td>
        <td>
          <span class="severity" [ngClass]="'severity--' + row.severity">
            {{ row.severity | titlecase }}
          </span>
        </td>
        <td>
          <span *ngFor="let issue of row.issues" class="issue">
            {{ issueLabel(issue) }} ({{ issueCount(row, issue) }})
          </span>
        </td>
        <td>
          <strong>{{ row.totalAmount | currency:'PHP':'symbol':'1.2-2' }}</strong>
          <div>{{ row.itemCount }} tracking lines · {{ row.salesQty }} sold</div>
          <small>Inventory recorded: {{ row.inventoryQty }}</small>
        </td>
        <td>
          <button type="button" (click)="viewDetails(row.invoiceNumber)">
            View details
          </button>
        </td>
      </tr>
      <tr *ngIf="!loading && !error && rows.length === 0">
        <td colspan="7">No inventory exceptions found for this date range.</td>
      </tr>
    </tbody>
  </table>
</div>
```

Add these helpers to the component to display readable issue labels and per-issue affected item counts:

```typescript
issueLabel(issue: ReconException['issues'][number]): string {
  return issue === 'NO_INVENTORY' ? 'No inventory' : 'Quantity mismatch';
}

issueCount(row: ReconException, issue: ReconException['issues'][number]): number {
  return issue === 'NO_INVENTORY'
    ? row.missingInventoryItemCount
    : row.quantityMismatchItemCount;
}
```

Example styles:

```css
.recon-grid-wrap {
  overflow-x: auto;
}

.recon-grid {
  width: 100%;
  border-collapse: collapse;
}

.recon-grid th,
.recon-grid td {
  border: 1px solid #e6e6e6;
  padding: 10px 12px;
  text-align: left;
  vertical-align: top;
}

.recon-grid th {
  background-color: #f5f5f5;
}

.severity {
  font-weight: 600;
  text-transform: capitalize;
}

.severity--critical {
  color: #b42318;
}

.severity--high {
  color: #b54708;
}

.issue {
  display: block;
}

.recon-grid button {
  border: 0;
  background: none;
  color: #464feb;
  cursor: pointer;
  text-decoration: none;
}
```

## Invoice Child Grid

The **View details** action calls `GET /get_recon_invoice_details_bq` with the same `storeId` and the selected row's `invoiceNumber`. It requires the Firebase ID token and verifies access to the requested store.

| Environment | URL |
| --- | --- |
| Dev | `https://asia-east1-jasperpos-dev.cloudfunctions.net/get_recon_invoice_details_bq` |
| Prod | `https://asia-east1-jasperpos-1dfd5.cloudfunctions.net/get_recon_invoice_details_bq` |

The response contains one item row per sales `itemCode`: product name, sales quantity/amount, inventory quantity, quantity difference (`inventoryQty - salesQty`), an issue code, and the matching stock-tracked inventory rows. A missing inventory match returns `inventoryRows: []` and `issueType: "NO_INVENTORY"`. This detail endpoint currently only returns sales items; inventory-only items are not listed.

Required query parameters:

| Parameter | Description |
| --- | --- |
| `storeId` | Store the signed-in user is authorized to access. |
| `invoiceNumber` | Invoice selected in the parent exception grid. |

Example:

```text
?storeId=store-123&invoiceNumber=INV-456
```

Successful response:

```json
{
  "success": true,
  "storeId": "store-123",
  "invoiceNumber": "INV-456",
  "count": 1,
  "items": [
    {
      "invoiceNumber": "INV-456",
      "itemCode": "COLA-15",
      "productName": "Coke 1.5L",
      "salesQty": 5,
      "salesAmount": 505.0,
      "salesLineCount": 1,
      "inventoryQty": 3,
      "quantityDifference": -2,
      "issueType": "QTY_MISMATCH",
      "inventoryRows": [
        {
          "inventoryTrackingId": "tracking-789",
          "batchId": "batch-12",
          "eventType": "sale",
          "quantity": 3,
          "createdAt": "2026-10-17T12:30:00+00:00",
          "runningBalanceTotalStock": 7
        }
      ]
    }
  ]
}
```

Add these component members to load the child rows when the parent action is clicked:

```typescript
selectedInvoice: string | null = null;
detailRows: ReconInvoiceItem[] = [];
detailLoading = false;
detailError: string | null = null;

async viewDetails(invoiceNumber: string): Promise<void> {
  this.selectedInvoice = invoiceNumber;
  this.detailRows = [];
  this.detailError = null;
  this.detailLoading = true;

  try {
    const result = await this.reconSummaryService.getInvoiceDetails(
      this.selectedStoreId,
      invoiceNumber
    );
    this.detailRows = result.items;
  } catch (error) {
    console.error('Reconciliation details request failed.', error);
    this.detailError = 'Could not load invoice details. Please try again.';
  } finally {
    this.detailLoading = false;
  }
}
```

Render the selected invoice's item comparison and its actual inventory ledger rows:

```html
<section *ngIf="selectedInvoice as invoice" class="recon-child">
  <h3>Reconciliation details — {{ invoice }}</h3>
  <p *ngIf="detailLoading">Loading invoice details…</p>
  <p *ngIf="detailError" role="alert">{{ detailError }}</p>

  <table *ngIf="!detailLoading && !detailError" class="recon-grid">
    <thead>
      <tr>
        <th>Item</th>
        <th>Sales qty</th>
        <th>Inventory qty</th>
        <th>Difference</th>
        <th>Issue</th>
        <th>Inventory rows</th>
      </tr>
    </thead>
    <tbody>
      <tr *ngFor="let item of detailRows">
        <td>{{ item.productName || item.itemCode || 'Unknown item' }}</td>
        <td>{{ item.salesQty }}</td>
        <td>{{ item.inventoryQty }}</td>
        <td>{{ item.quantityDifference }}</td>
        <td>{{ item.issueType }}</td>
        <td>
          <span *ngIf="item.inventoryRows.length === 0">None found</span>
          <ul *ngIf="item.inventoryRows.length > 0">
            <li *ngFor="let inventory of item.inventoryRows">
              {{ inventory.eventType || 'Movement' }}:
              {{ inventory.quantity }} on
              {{ inventory.createdAt | date:'short' }}
              <span *ngIf="inventory.batchId"> · Batch {{ inventory.batchId }}</span>
              <span *ngIf="inventory.runningBalanceTotalStock !== null">
                · Balance {{ inventory.runningBalanceTotalStock }}
              </span>
            </li>
          </ul>
        </td>
      </tr>
      <tr *ngIf="detailRows.length === 0">
        <td colspan="6">No stock-tracked item details found.</td>
      </tr>
    </tbody>
  </table>
</section>
```

## Successful Response

Each row summarizes one invoice with detected inventory exceptions. `totalAmount` is the sum of the stock-tracked sales-line `total` values, and `itemCount` counts those tracking rows. `inventoryQty` is the sum of all matching stock-tracked inventory quantities for the invoice. Timestamp values are serialized as ISO strings and numeric values are JSON-compatible numbers.

```json
{
  "success": true,
  "store_id": "store-123",
  "from": "2026-10-01",
  "to": "2026-10-17",
  "count": 1,
  "rows": [
    {
      "invoiceNumber": "INV-456",
      "createdAt": "2026-10-17T12:30:00+00:00",
      "cashierName": "Jasper",
      "totalAmount": 505.0,
      "itemCount": 3,
      "salesQty": 3,
      "inventoryQty": 0,
      "missingInventoryItemCount": 3,
      "quantityMismatchItemCount": 0,
      "hasInventoryIssue": true,
      "issues": ["NO_INVENTORY"],
      "issueType": "NO_INVENTORY",
      "severity": "critical"
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
