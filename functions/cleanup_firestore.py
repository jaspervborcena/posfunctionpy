"""
Cleanup script for Firestore collection(s).

This script deletes documents from a given collection path using batched deletes.
It uses the Admin SDK (google-cloud-firestore) and the service account JSON from
GOOGLE_APPLICATION_CREDENTIALS.

Usage (PowerShell):
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\MVP\POSFunctionPy\functions\service-account.json"
python .\functions\cleanup_firestore.py --collection orderDetails --preview

Options:
  --collection (required) collection path to delete (e.g. orderDetails or orders)
  --batch-size (default 500) number of docs per batch delete
  --preview (flag) show how many docs would be deleted and first 10 ids, do not delete

CAUTION: This permanently deletes documents. Run with --preview first.
"""
from google.cloud import firestore
import argparse
import sys


def parse_args():
    p = argparse.ArgumentParser(description="Delete documents from Firestore collection (batched)")
    p.add_argument("--collection", required=True)
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--preview", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    db = firestore.Client()

    col_ref = db.collection(args.collection)
    docs = list(col_ref.limit(10000).stream())
    total = len(docs)

    print(f"Found {total} documents in collection '{args.collection}' (preview limited to 10k)")
    if total == 0:
        print("Nothing to delete")
        return

    if args.preview:
        print("Preview mode - not deleting. First 10 document ids:")
        for d in docs[:10]:
            print(" - ", d.id)
        return

    # proceed to delete in batches
    batch_size = args.batch_size
    i = 0
    while i < total:
        batch = db.batch()
        batch_docs = docs[i:i+batch_size]
        for d in batch_docs:
            batch.delete(d.reference)
        batch.commit()
        print(f"Deleted documents {i+1}..{min(i+batch_size, total)}")
        i += batch_size

    print("Completed deleting documents")


if __name__ == '__main__':
    main()
