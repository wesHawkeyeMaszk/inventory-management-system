from flask import Blueprint, jsonify
from app.services import mongo_service, cache_service

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/products/analytics", methods=["GET"])
def get_analytics():
    """
    Aggregated product analytics.
    ---
    tags: [Analytics]
    responses:
      200:
        description: Analytics data including category breakdown, price stats, and low-stock count
    """
    cached = cache_service.get("products:analytics")
    if cached:
        return jsonify(cached), 200, {"X-Cache": "HIT"}

    data = mongo_service.get_analytics()
    cache_service.set("products:analytics", data)
    return jsonify(data), 200, {"X-Cache": "MISS"}
