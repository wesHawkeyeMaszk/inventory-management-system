from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING
from flask import current_app
from app.models.product import serialize_product

_client = None
_indexes_ensured = False


def _get_client():
    """Return a process-wide MongoClient, created lazily on first use.

    MongoClient owns its own internal connection pool and is documented by
    PyMongo as safe to share across threads, so one long-lived instance per
    worker process is the intended usage. Constructing a new client per
    request (the previous behaviour here) opens and tears down a fresh
    connection pool on every call, which doesn't hold up under load. Lazy
    creation (rather than a client built at import time) also keeps this
    fork-safe under gunicorn, which forks worker processes after import.
    """
    global _client
    if _client is None:
        kwargs = {"maxPoolSize": 50, "serverSelectionTimeoutMS": 3000}
        # MONGO_URI intentionally carries no credentials (see
        # app/config.py); username/password, if configured, are supplied
        # separately here rather than string-interpolated into the URI, so
        # MONGO_URI stays safe to log without leaking a secret.
        username = current_app.config.get("MONGO_USERNAME")
        password = current_app.config.get("MONGO_PASSWORD")
        if username and password:
            kwargs["username"] = username
            kwargs["password"] = password
            kwargs["authSource"] = "admin"
        _client = MongoClient(current_app.config["MONGO_URI"], **kwargs)
    return _client


def ensure_indexes(db):
    """Create indexes for the products and price_history collections.

    create_index() is idempotent (a no-op if an equivalent index already
    exists), so this is safe to run on every process start rather than
    needing a separate migration step someone has to remember to run.
    """
    products = db["products"]
    products.create_index("product_id", unique=True)
    products.create_index("product_name")
    products.create_index("product_category")
    products.create_index("price")
    products.create_index("available_quantity")
    products.create_index("created_at")
    products.create_index("updated_at")
    # Supports the $group-by-category + price aggregate in get_analytics(),
    # and category+price-range browsing, without a full collection scan.
    products.create_index([("product_category", 1), ("price", 1)])

    db["price_history"].create_index([("product_id", 1), ("changed_at", -1)])


def _get_db():
    global _indexes_ensured
    db = _get_client().get_default_database()
    if not _indexes_ensured:
        ensure_indexes(db)
        _indexes_ensured = True
    return db


def _col():
    return _get_db()["products"]


def _history_col():
    return _get_db()["price_history"]


def _record_history(product_id, field, old_value, new_value):
    _history_col().insert_one({
        "product_id": product_id,
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "changed_at": datetime.now(timezone.utc).isoformat(),
    })


def get_all_products(page=1, limit=20, sort_by="product_name", order="asc"):
    skip = (page - 1) * limit
    direction = ASCENDING if order == "asc" else DESCENDING
    col = _col()
    total = col.count_documents({})
    docs = col.find().sort(sort_by, direction).skip(skip).limit(limit)
    return {
        "products": [serialize_product(d) for d in docs],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, -(-total // limit)),  # ceiling division
    }


def get_product(product_id):
    doc = _col().find_one({"product_id": product_id})
    return serialize_product(doc) if doc else None


def get_products_by_ids(product_ids):
    """Hydrate a list of product_ids in a single query, preserving the
    input order (e.g. Elasticsearch relevance ranking)."""
    if not product_ids:
        return []
    docs = _col().find({"product_id": {"$in": product_ids}})
    by_id = {doc["product_id"]: serialize_product(doc) for doc in docs}
    return [by_id[pid] for pid in product_ids if pid in by_id]


def create_product(data):
    now = datetime.now(timezone.utc).isoformat()
    data["created_at"] = now
    data["updated_at"] = now
    result = _col().insert_one(data)
    data["_id"] = str(result.inserted_id)
    return data


def bulk_create_products(products):
    now = datetime.now(timezone.utc).isoformat()
    for p in products:
        p["created_at"] = now
        p["updated_at"] = now
    result = _col().insert_many(products)
    for p, oid in zip(products, result.inserted_ids):
        p["_id"] = str(oid)
    return products


def update_product(product_id, updates):
    existing = _col().find_one({"product_id": product_id})
    if not existing:
        return None

    for field in ("price", "available_quantity"):
        if field in updates and existing.get(field) != updates[field]:
            _record_history(product_id, field, existing.get(field), updates[field])

    updates = dict(updates)
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = _col().find_one_and_update(
        {"product_id": product_id},
        {"$set": updates},
        return_document=True,
    )
    return serialize_product(result) if result else None


def restore_product(product_id, snapshot):
    """Overwrite a product's fields back to a prior snapshot, bypassing
    history recording. Used to roll back a Mongo write when the
    corresponding Elasticsearch write fails, so the two stores don't drift."""
    fields = {k: v for k, v in snapshot.items() if k not in ("_id", "product_id")}
    _col().find_one_and_update({"product_id": product_id}, {"$set": fields})


def delete_product(product_id):
    result = _col().delete_one({"product_id": product_id})
    return result.deleted_count > 0


def get_product_history(product_id):
    docs = list(_history_col().find(
        {"product_id": product_id},
        {"_id": 0}
    ).sort("changed_at", DESCENDING))
    return docs


def get_analytics():
    col = _col()
    total_count = col.count_documents({})

    # Group by a case-normalized category so "Electronics" and "electronics"
    # count as one category here, matching the case-insensitive category
    # filter GET /products/search already applies in Elasticsearch
    # (es_service.search_products). Grouping on the raw string would let
    # the two stores disagree about what counts as "the same category".
    # $first keeps a human-readable label for display.
    category_pipeline = [
        {"$group": {
            "_id": {"$toLower": "$product_category"},
            "count": {"$sum": 1},
            "display_name": {"$first": "$product_category"},
        }},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    categories = list(col.aggregate(category_pipeline))

    price_pipeline = [
        {"$group": {
            "_id": None,
            "avg_price": {"$avg": "$price"},
            "min_price": {"$min": "$price"},
            "max_price": {"$max": "$price"},
        }}
    ]
    price_result = list(col.aggregate(price_pipeline))
    price_stats = price_result[0] if price_result else {}

    low_stock_threshold = current_app.config["LOW_STOCK_THRESHOLD"]
    low_stock = col.count_documents({"available_quantity": {"$lte": low_stock_threshold}})

    return {
        "total_count": total_count,
        "most_popular_category": categories[0]["display_name"] if categories else None,
        "category_breakdown": [{"category": c["display_name"], "count": c["count"]} for c in categories],
        "average_price": round(price_stats.get("avg_price") or 0, 2),
        "min_price": price_stats.get("min_price") or 0,
        "max_price": price_stats.get("max_price") or 0,
        "low_stock_count": low_stock,
        "low_stock_threshold": low_stock_threshold,
    }
