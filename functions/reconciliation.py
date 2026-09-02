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
    # Function removed - no longer using productInventory
    print(f"[recompute_product_summary] Skipped recomputation for product {product_id} - productInventory integration disabled")
    pass


def reconcile_one_tracking(doc: Dict[str, Any]) -> None:
    db = firestore.client()
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

        # productInventory integration removed - mark as reconciled without inventory deduction
        print(f"[reconcile_one_tracking] Skipping inventory deduction for tracking {doc.get('id')} - productInventory integration disabled")
        
        log_data = {
            "trackingId": doc.get("id"),
            "companyId": doc.get("companyId"),
            "storeId": doc.get("storeId"),
            "orderId": doc.get("orderId"),
            "productId": doc.get("productId"),
            "quantityProcessed": _to_int(doc.get("quantity", 0)),
            "batchesUsed": [],
            "action": "skipped",
            "message": "Reconciled without inventory deduction - productInventory integration disabled",
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
        log_ref = log_col.document()
        tx.set(log_ref, log_data)

        tx.update(
            t_ref,
            {
                "status": "reconciled",
                "reconciledAt": firestore.SERVER_TIMESTAMP,
                "remaining": 0,
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
            # Recompute summary after each tracking doc - disabled productInventory integration
            print(f"[reconcile_pending] Skipping product summary recomputation for product {d.get('productId')} - productInventory integration disabled")
        except Exception as e:
            print("[reconcilePending] Error", d.get("id"), e)
            try:
                db.collection("ordersSellingTracking").document(d["id"]).set({"status": "error", "error": str(getattr(e, "message", e))}, merge=True)
            except Exception:
                pass

    return {"processed": len(docs)}


# NOTE: The scheduled `reconcile_daily` job was removed as part of
# the feature cleanup. If scheduled reconciliation is reintroduced
# in the future, add a new @scheduler_fn.on_schedule-decorated function
# here with appropriate auth and limits.
