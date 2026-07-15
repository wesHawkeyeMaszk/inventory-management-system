"""
Detect (and optionally repair) drift between MongoDB (source of truth) and
Elasticsearch (the search index) for the products collection.

This is the cheap partial mitigation for the crash window documented in
docs/adr/0001-mongo-elasticsearch-consistency.md: a process killed between
the Mongo write and the Elasticsearch write in app/routes/products.py can
leave the two stores permanently out of sync, with nothing today noticing
or repairing it. This script doesn't remove that window - only moving the
Elasticsearch write off the request path (Change Streams / Debezium, per
the ADR) does that - but run periodically (see
k8s/base/app/reconcile-cronjob.yaml) it means drift gets found and fixed
within one schedule interval instead of sitting undetected indefinitely.

Usage:
    python scripts/reconcile.py [--mongo MONGO_URI] [--es ES_URI] [--repair]

Exits non-zero when drift is found and --repair wasn't passed, so a
CronJob running this in report-only mode can be alerted on via its exit
code without needing a separate monitoring integration.
"""
import argparse
import os
import sys

from pymongo import MongoClient
from elasticsearch import Elasticsearch

INDEX = "products"


def _es_doc(product):
    return {
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "product_category": product["product_category"],
        "description": product.get("description", ""),
        "price": product.get("price"),
    }


def reconcile(mongo_uri, es_uri, repair=False, mongo_username=None, mongo_password=None):
    kwargs = {}
    if mongo_username and mongo_password:
        kwargs = {"username": mongo_username, "password": mongo_password, "authSource": "admin"}
    col = MongoClient(mongo_uri, **kwargs).get_default_database()["products"]
    es = Elasticsearch(es_uri)

    mongo_products = {p["product_id"]: p for p in col.find({}, {"_id": 0})}
    mongo_ids = set(mongo_products)

    es_ids = set()
    if es.indices.exists(index=INDEX):
        # size=10000 is a fine cap at this project's catalog scale; a
        # deployment with more products than that would need the scroll
        # or search_after APIs here instead of a single page.
        resp = es.search(index=INDEX, query={"match_all": {}}, source=["product_id"], size=10000)
        es_ids = {h["_source"]["product_id"] for h in resp["hits"]["hits"]}

    missing_in_es = mongo_ids - es_ids  # exists in Mongo, not searchable
    orphaned_in_es = es_ids - mongo_ids  # searchable, but deleted from Mongo

    print(f"Mongo products: {len(mongo_ids)}")
    print(f"Elasticsearch documents: {len(es_ids)}")
    print(f"Missing in Elasticsearch (not searchable): {len(missing_in_es)}")
    print(f"Orphaned in Elasticsearch (stale, product no longer exists): {len(orphaned_in_es)}")

    if not repair:
        if missing_in_es or orphaned_in_es:
            print("Drift found. Re-run with --repair to fix.")
            return 1
        print("In sync.")
        return 0

    for product_id in missing_in_es:
        es.index(index=INDEX, id=product_id, document=_es_doc(mongo_products[product_id]))
        print(f"  repaired: indexed {product_id} into Elasticsearch")

    for product_id in orphaned_in_es:
        es.delete(index=INDEX, id=product_id)
        print(f"  repaired: removed orphaned {product_id} from Elasticsearch")

    print("Repair complete.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mongo", default=os.getenv("MONGO_URI", "mongodb://localhost:27017/inventory"))
    parser.add_argument("--es", default=os.getenv("ES_URI", "http://localhost:9200"))
    parser.add_argument("--mongo-username", default=os.getenv("MONGO_USERNAME"))
    parser.add_argument("--mongo-password", default=os.getenv("MONGO_PASSWORD"))
    parser.add_argument("--repair", action="store_true", help="Fix drift instead of only reporting it")
    args = parser.parse_args()

    try:
        sys.exit(reconcile(
            args.mongo, args.es, repair=args.repair,
            mongo_username=args.mongo_username, mongo_password=args.mongo_password,
        ))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
