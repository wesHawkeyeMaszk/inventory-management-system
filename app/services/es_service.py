import logging
from elasticsearch import Elasticsearch
from flask import current_app

logger = logging.getLogger(__name__)

INDEX = "products"

_client = None


def _get_client():
    """Return a process-wide Elasticsearch client, created lazily on first
    use. The client manages its own pooled HTTP connections internally;
    building a new one per request defeats that pooling and adds a
    connection-setup cost to every call.
    """
    global _client
    if _client is None:
        _client = Elasticsearch(current_app.config["ES_URI"], request_timeout=5)
    return _client


def ensure_index():
    """Create the products index with a mapping if it doesn't exist."""
    es = _get_client()
    if not es.indices.exists(index=INDEX):
        es.indices.create(
            index=INDEX,
            mappings={
                "properties": {
                    "product_id": {"type": "keyword"},
                    "product_name": {"type": "text"},
                    "product_category": {"type": "keyword"},
                    "description": {"type": "text"},
                    "price": {"type": "float"},
                }
            },
        )


def index_product(product):
    es = _get_client()
    doc = {
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "product_category": product["product_category"],
        "description": product.get("description", ""),
        "price": product.get("price"),
    }
    es.index(index=INDEX, id=product["product_id"], document=doc)


def delete_product(product_id):
    es = _get_client()
    try:
        es.delete(index=INDEX, id=product_id)
    except Exception as exc:
        # Mongo is authoritative and already deleted; search hydrates
        # results from Mongo, so a stale ES doc is harmless but worth a log.
        logger.warning("Failed to delete product %s from Elasticsearch: %s", product_id, exc)


def suggest_products(q):
    """Return product name suggestions for autocomplete."""
    es = _get_client()
    response = es.search(
        index=INDEX,
        query={
            "match_phrase_prefix": {
                "product_name": {"query": q, "max_expansions": 10}
            }
        },
        source=["product_id", "product_name", "product_category"],
        size=8,
    )
    return [
        {
            "product_id": h["_source"]["product_id"],
            "product_name": h["_source"]["product_name"],
            "product_category": h["_source"]["product_category"],
        }
        for h in response["hits"]["hits"]
    ]


def get_analytics():
    """Total count, category breakdown, and average price computed directly
    from the Elasticsearch index, independent of Mongo's own aggregation in
    mongo_service.get_analytics().

    GET /products/analytics merges this in (see app/routes/analytics.py) so
    the endpoint genuinely aggregates from both stores rather than just
    Mongo, and so a total-count mismatch between the two surfaces directly
    in the API response - the same drift ADR 0001 and scripts/reconcile.py
    already assume is possible, made visible here instead of only caught on
    reconcile's 15-minute schedule.

    product_category is matched as indexed (no case normalization), unlike
    Mongo's $toLower grouping - a real difference, not a bug to hide, since
    it's the same case-sensitivity gap GET /products/search already works
    around with `case_insensitive: true` on its own category filter.
    """
    es = _get_client()
    response = es.search(
        index=INDEX,
        size=0,
        aggs={
            "categories": {"terms": {"field": "product_category", "size": 10}},
            "avg_price": {"avg": {"field": "price"}},
        },
    )
    total = response["hits"]["total"]["value"]
    buckets = response["aggregations"]["categories"]["buckets"]
    avg_price = response["aggregations"]["avg_price"]["value"]
    return {
        "total_count": total,
        "average_price": round(avg_price, 2) if avg_price is not None else 0,
        "category_breakdown": [{"category": b["key"], "count": b["doc_count"]} for b in buckets],
    }


def search_products(query, category=None, min_price=None, max_price=None, page=1, limit=20):
    """Search product name/description, filtered by category and price range,
    with pagination applied in Elasticsearch itself.

    Returns (product_ids, total) where product_ids is the page of matching
    ids in relevance order and total is the full match count.
    """
    es = _get_client()

    filters = []
    if category:
        filters.append({"term": {"product_category": {"value": category, "case_insensitive": True}}})
    if min_price is not None or max_price is not None:
        price_range = {}
        if min_price is not None:
            price_range["gte"] = min_price
        if max_price is not None:
            price_range["lte"] = max_price
        filters.append({"range": {"price": price_range}})

    es_query = {
        "bool": {
            "must": [{
                "multi_match": {
                    "query": query,
                    "fields": ["product_name", "description"],
                    "fuzziness": "AUTO",
                }
            }],
            "filter": filters,
        }
    }

    response = es.search(
        index=INDEX,
        query=es_query,
        from_=(page - 1) * limit,
        size=limit,
    )
    total = response["hits"]["total"]["value"]
    ids = [hit["_source"]["product_id"] for hit in response["hits"]["hits"]]
    return ids, total
