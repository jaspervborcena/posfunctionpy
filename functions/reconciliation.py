from __future__ import annotations

from typing import Any, Dict, List, Optional

from firebase_functions import https_fn, scheduler_fn
from firebase_admin import firestore


def _to_number(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except Exception:
        return float(default)


def _to_int(val: Any, default: int = 0) -> int:
    try:
        return int(val)
    except Exception:
        return int(default)


def recompute_product_summary(product_id: str) -> None:
    db = firestore.client()

    inv_query = (
        db.collection("productInventory")
        .where("productId", "==", product_id)
    )
    inv_snap = inv_query.get()

    active = []
    for d in inv_snap:
        data = d.to_dict() or {}
        status = data.get("status")
        if status == "active":
            item = {"id": d.id, **data}
            active.append(item)

    total_stock = 0
    for b in active:
        total_stock += _to_int(b.get("quantity", 0))

    # Latest by receivedAt desc
    def _ts_to_dt(ts: Any):
        try:
            return ts.to_datetime() if hasattr(ts, "to_datetime") else ts
        except Exception:
            return ts

    latest = None
    try:
        latest = sorted(active, key=lambda x: _ts_to_dt(x.get("receivedAt")) or 0, reverse=True)[0] if active else None
    except Exception:
        latest = active[0] if active else None

    selling_price = _to_number(latest.get("unitPrice", 0)) if latest else 0

    db.collection("products").document(product_id).set(
        {
            "totalStock": total_stock,
            "sellingPrice": selling_price,
            "lastUpdated": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )


def reconcile_one_tracking(doc: Dict[str, Any]) -> None:
    db = firestore.client()
    inv_col = db.collection("productInventory")
    log_col = db.collection("reconciliationLog")

    t_ref = db.collection("ordersSellingTracking").document(doc["id"])
    transaction = db.transaction()

    @firestore.transactional
    def _tx(tx: firestore.Transaction):
        t_snap = t_ref.get(transaction=tx)
        if not t_snap.exists:
            return
        t_data = t_snap.to_dict() or {}
        status = t_data.get("status")
        if status and status != "pending":
            return

        remaining = _to_int(doc.get("quantity", 0))
        if remaining <= 0:
            tx.update(t_ref, {"status": "reconciled", "reconciledAt": firestore.SERVER_TIMESTAMP})
            return

        # Load active batches oldest first
        batch_query = (
            inv_col.where("productId", "==", doc.get("productId"))
            .where("status", "==", "active")
            .order_by("receivedAt", direction=firestore.Query.ASCENDING)
        ).stream(transaction=tx)

        batches: List[Dict[str, Any]] = []
        for b in batch_query:
            batches.append({"id": b.id, **(b.to_dict() or {})})

        if not batches:
            tx.update(t_ref, {"status": "error", "error": "no-inventory", "reconciledAt": firestore.SERVER_TIMESTAMP})
            return

        deductions: List[Dict[str, Any]] = []
        for b in batches:
            if remaining <= 0:
                break
            avail = _to_int(b.get("quantity", 0))
            if avail <= 0:
                continue
            use = min(remaining, avail)
            new_qty = avail - use
            deductions.append({"batchId": b.get("batchId") or b.get("id"), "quantity": use})
            b_ref = inv_col.document(b["id"])
            update: Dict[str, Any] = {"quantity": new_qty, "updatedAt": firestore.SERVER_TIMESTAMP}
            if new_qty == 0:
                update["status"] = "inactive"
            tx.update(b_ref, update)
            remaining -= use

        log_data = {
            "trackingId": doc.get("id"),
            "companyId": doc.get("companyId"),
            "storeId": doc.get("storeId"),
            "orderId": doc.get("orderId"),
            "productId": doc.get("productId"),
            "quantityProcessed": _to_int(doc.get("quantity", 0)) - max(remaining, 0),
            "batchesUsed": deductions,
            "action": "deduct" if remaining == 0 else "partial",
            "message": "Reconciled successfully" if remaining == 0 else f"Only partially reconciled; remaining {remaining}",
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
        log_ref = log_col.document()
        tx.set(log_ref, log_data)

        tx.update(
            t_ref,
            {
                "status": "reconciled" if remaining == 0 else "error",
                "reconciledAt": firestore.SERVER_TIMESTAMP,
                "remaining": remaining,
            },
        )

    _tx(transaction)


def reconcile_pending(company_id: Optional[str] = None, store_id: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    db = firestore.client()
    q = db.collection("ordersSellingTracking").where("status", "==", "pending")
    if company_id:
        q = q.where("companyId", "==", company_id)
    if store_id:
        q = q.where("storeId", "==", store_id)
    if limit:
        q = q.limit(int(limit))
    snap = q.get()
    docs: List[Dict[str, Any]] = [{"id": d.id, **(d.to_dict() or {})} for d in snap]

    for d in docs:
        try:
            reconcile_one_tracking(d)
            # Recompute summary after each tracking doc
            if d.get("productId"):
                recompute_product_summary(str(d["productId"]))
        except Exception as e:
            print("[reconcilePending] Error", d.get("id"), e)
            try:
                db.collection("ordersSellingTracking").document(d["id"]).set({"status": "error", "error": str(getattr(e, "message", e))}, merge=True)
            except Exception:
                pass

    return {"processed": len(docs)}


@scheduler_fn.on_schedule(schedule="0 2 * * *", timezone="Asia/Manila", region="asia-east1")
def reconcile_daily(event: scheduler_fn.ScheduledEvent) -> None:
    print("[reconcileDaily] Starting scheduled reconciliation job")
    res = reconcile_pending(limit=500)
    print("[reconcileDaily] Completed", res)


@https_fn.on_call(region="asia-east1")
def reconcile_on_demand(req: https_fn.CallableRequest) -> Dict[str, Any]:
    data = req.data or {}
    company_id = data.get("companyId")
    store_id = data.get("storeId")
    limit = data.get("limit")
    if not company_id and not store_id:
        raise https_fn.HttpsError(code=https_fn.FunctionsErrorCode.INVALID_ARGUMENT, message="Provide companyId or storeId to scope reconciliation.")
    res = reconcile_pending(company_id=company_id, store_id=store_id, limit=limit or 200)
    return {"status": "ok", **res}
