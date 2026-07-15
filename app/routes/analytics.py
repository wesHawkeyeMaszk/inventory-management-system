from flask import Blueprint, jsonify
from app.services import mongo_service, es_service, cache_service

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/products/analytics", methods=["GET"])
def get_analytics():
    """
    Aggregated product analytics.
    ---
    tags: [Analytics]
    responses:
      200:
        description: Analytics data including category breakdown, price stats, low-stock count, and an Elasticsearch-derived cross-check
    """
    cached = cache_service.get("products:analytics")
    if cached:
        return jsonify(cached), 200, {"X-Cache": "HIT"}

    # Mongo is authoritative (it's the only store with available_quantity,
    # so low-stock counts and the primary total/category/price figures come
    # from there). Elasticsearch's independently-computed total/category/
    # price numbers are folded in under "elasticsearch" as a genuine second
    # aggregation, not a copy of Mongo's - see es_service.get_analytics.
    data = mongo_service.get_analytics()
    es_data = es_service.get_analytics()
    data["elasticsearch"] = {
        **es_data,
        "consistent_with_mongo": es_data["total_count"] == data["total_count"],
    }

    cache_service.set("products:analytics", data)
    return jsonify(data), 200, {"X-Cache": "MISS"}
