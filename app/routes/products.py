import logging
import uuid
from flask import Blueprint, jsonify, request
from app.auth import require_api_key
from app.extensions import limiter
from app.models.product import validate_product, validate_product_update
from app.services import mongo_service, es_service, cache_service

logger = logging.getLogger(__name__)

products_bp = Blueprint("products", __name__)

# Allowlist for GET /products?sort=. Passing an arbitrary field straight
# through to Mongo's .sort() would let a caller force an unindexed,
# potentially expensive collection sort on any field name; every field
# listed here has a supporting index (see mongo_service.ensure_indexes).
SORTABLE_FIELDS = {
    "product_name", "product_category", "price", "available_quantity",
    "created_at", "updated_at",
}


@products_bp.route("/products", methods=["GET"])
def list_products():
    """
    List all products with pagination and sorting.
    ---
    tags: [Products]
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
      - name: limit
        in: query
        type: integer
        default: 20
      - name: sort
        in: query
        type: string
        default: product_name
      - name: order
        in: query
        type: string
        enum: [asc, desc]
        default: asc
    responses:
      200:
        description: Paginated product list
    """
    page = max(1, int(request.args.get("page", 1)))
    limit = min(100, max(1, int(request.args.get("limit", 20))))
    sort_by = request.args.get("sort", "product_name")
    order = request.args.get("order", "asc")

    if sort_by not in SORTABLE_FIELDS:
        return jsonify({
            "error": f"sort must be one of: {', '.join(sorted(SORTABLE_FIELDS))}"
        }), 400
    if order not in ("asc", "desc"):
        return jsonify({"error": "order must be 'asc' or 'desc'"}), 400

    cache_key = f"products:list:{page}:{limit}:{sort_by}:{order}"
    cached = cache_service.get(cache_key)
    if cached:
        return jsonify(cached), 200, {"X-Cache": "HIT"}

    result = mongo_service.get_all_products(page=page, limit=limit, sort_by=sort_by, order=order)
    cache_service.set(cache_key, result)
    return jsonify(result), 200, {"X-Cache": "MISS"}


# /products/suggest, /products/search, /products/analytics must come before
# /products/<id> to prevent Flask matching literal segments as the <id> param.

@products_bp.route("/products/suggest", methods=["GET"])
def suggest_products():
    """
    Autocomplete / typeahead suggestions.
    ---
    tags: [Search]
    parameters:
      - name: q
        in: query
        type: string
        required: true
    responses:
      200:
        description: List of product name suggestions
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter is required"}), 400
    suggestions = es_service.suggest_products(q)
    return jsonify(suggestions), 200


@products_bp.route("/products/search", methods=["GET"])
def search_products():
    """
    Full-text search across product names and descriptions.
    ---
    tags: [Search]
    parameters:
      - name: query
        in: query
        type: string
        required: true
      - name: category
        in: query
        type: string
      - name: min_price
        in: query
        type: number
      - name: max_price
        in: query
        type: number
      - name: page
        in: query
        type: integer
        default: 1
      - name: limit
        in: query
        type: integer
        default: 20
    responses:
      200:
        description: Matching products
    """
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"error": "query parameter is required"}), 400

    category = request.args.get("category")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    page = max(1, int(request.args.get("page", 1)))
    limit = min(100, max(1, int(request.args.get("limit", 20))))

    # Filtering and pagination happen in Elasticsearch; Mongo is hit once
    # with a single $in query to hydrate just the current page of results.
    product_ids, total = es_service.search_products(
        query, category=category, min_price=min_price, max_price=max_price,
        page=page, limit=limit,
    )
    products = mongo_service.get_products_by_ids(product_ids)

    return jsonify({
        "products": products,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, -(-total // limit)),
    }), 200


@products_bp.route("/products/bulk", methods=["POST"])
@limiter.limit("5 per minute")
@require_api_key
def bulk_create_products():
    """
    Bulk create products.
    ---
    tags: [Products]
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: array
    responses:
      201:
        description: Created products
    """
    data = request.get_json(silent=True)
    if not isinstance(data, list) or not data:
        return jsonify({"error": "Request body must be a non-empty JSON array"}), 400
    if len(data) > 500:
        return jsonify({"error": "Maximum 500 products per bulk request"}), 400

    validated = []
    errors = []
    for i, item in enumerate(data):
        cleaned, err = validate_product(item)
        if err:
            errors.append({"index": i, "error": err})
        else:
            cleaned["product_id"] = str(uuid.uuid4())
            validated.append(cleaned)

    if errors:
        return jsonify({"errors": errors}), 422

    products = mongo_service.bulk_create_products(validated)

    indexed = []
    index_errors = []
    for p in products:
        try:
            es_service.index_product(p)
            indexed.append(p)
        except Exception as exc:
            logger.warning("Failed to index product %s during bulk create: %s", p["product_id"], exc)
            mongo_service.delete_product(p["product_id"])
            index_errors.append({"product_id": p["product_id"], "error": "failed to index in search"})

    cache_service.delete_pattern("products:list:*")

    status = 201 if not index_errors else 207
    return jsonify({
        "created": len(indexed),
        "products": indexed,
        "errors": index_errors,
    }), status


@products_bp.route("/products/<product_id>/history", methods=["GET"])
def get_product_history(product_id):
    """
    Get price and quantity change history for a product.
    ---
    tags: [Products]
    parameters:
      - name: product_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: Change history
    """
    history = mongo_service.get_product_history(product_id)
    return jsonify(history), 200


@products_bp.route("/products/<product_id>", methods=["GET"])
def get_product(product_id):
    """
    Get a single product by ID.
    ---
    tags: [Products]
    parameters:
      - name: product_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: Product
      404:
        description: Not found
    """
    cache_key = f"products:{product_id}"
    cached = cache_service.get(cache_key)
    if cached:
        return jsonify(cached), 200, {"X-Cache": "HIT"}

    product = mongo_service.get_product(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    cache_service.set(cache_key, product)
    return jsonify(product), 200, {"X-Cache": "MISS"}


@products_bp.route("/products", methods=["POST"])
@limiter.limit("20 per minute")
@require_api_key
def create_product():
    """
    Create a new product.
    ---
    tags: [Products]
    parameters:
      - name: Idempotency-Key
        in: header
        type: string
        required: false
        description: >
          Optional client-supplied key. A retried POST with the same key
          returns the original response instead of creating a second
          product, so a lost-response retry (client timed out, request
          actually succeeded) can't create a duplicate.
      - name: body
        in: body
        required: true
        schema:
          required: [product_name, product_category, price, available_quantity]
          properties:
            product_name: {type: string}
            product_category: {type: string}
            price: {type: number}
            available_quantity: {type: integer}
            description: {type: string}
    responses:
      201:
        description: Created product
      409:
        description: A request with this Idempotency-Key is already being processed
    """
    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        if not cache_service.reserve_idempotency_key(idempotency_key):
            existing = cache_service.get_idempotency_result(idempotency_key)
            if existing and existing != cache_service.PENDING:
                return jsonify(existing["body"]), existing["status"]
            return jsonify({"error": "A request with this Idempotency-Key is already being processed"}), 409

    def _release_and_return(body, status):
        # Only successful creates are worth deduplicating for the TTL
        # window; releasing on every other path means a corrected retry
        # (bad payload fixed, or a transient ES outage cleared) with the
        # same key actually retries instead of being stuck replaying a
        # stale failure for up to IDEMPOTENCY_TTL.
        if idempotency_key:
            cache_service.release_idempotency_key(idempotency_key)
        return jsonify(body), status

    data = request.get_json(silent=True)
    if not data:
        return _release_and_return({"error": "Request body must be JSON"}, 400)

    data, err = validate_product(data)
    if err:
        return _release_and_return({"error": err}, 422)

    data["product_id"] = str(uuid.uuid4())
    product = mongo_service.create_product(data)

    try:
        es_service.index_product(product)
    except Exception as exc:
        logger.warning("Failed to index product %s, rolling back Mongo write: %s", product["product_id"], exc)
        mongo_service.delete_product(product["product_id"])
        return _release_and_return({"error": "Failed to index product in search; write rolled back"}, 500)

    cache_service.delete_pattern("products:list:*")

    threshold = product.get("available_quantity", 0)
    response = dict(product)
    if threshold <= 10:
        response["warning"] = f"Low stock: only {threshold} units available"

    if idempotency_key:
        cache_service.store_idempotency_result(idempotency_key, 201, response)

    return jsonify(response), 201


@products_bp.route("/products/<product_id>", methods=["PUT"])
@limiter.limit("20 per minute")
@require_api_key
def update_product(product_id):
    """
    Update an existing product.
    ---
    tags: [Products]
    parameters:
      - name: product_id
        in: path
        type: string
        required: true
      - name: body
        in: body
        required: true
        schema:
          properties:
            product_name: {type: string}
            product_category: {type: string}
            price: {type: number}
            available_quantity: {type: integer}
            description: {type: string}
    responses:
      200:
        description: Updated product
      404:
        description: Not found
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    cleaned, err = validate_product_update(data)
    if err:
        return jsonify({"error": err}), 422

    previous = mongo_service.get_product(product_id)
    updated = mongo_service.update_product(product_id, cleaned)
    if not updated:
        return jsonify({"error": "Product not found"}), 404

    try:
        es_service.index_product(updated)
    except Exception as exc:
        logger.warning("Failed to index product %s, rolling back Mongo update: %s", product_id, exc)
        mongo_service.restore_product(product_id, previous)
        return jsonify({"error": "Failed to index product in search; update rolled back"}), 500

    cache_service.delete(f"products:{product_id}")
    cache_service.delete_pattern("products:list:*")

    response = dict(updated)
    qty = updated.get("available_quantity", 0)
    if qty <= 10:
        response["warning"] = f"Low stock alert: only {qty} units remaining"

    return jsonify(response), 200


@products_bp.route("/products/<product_id>", methods=["DELETE"])
@limiter.limit("20 per minute")
@require_api_key
def delete_product(product_id):
    """
    Delete a product.
    ---
    tags: [Products]
    parameters:
      - name: product_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: Deleted
      404:
        description: Not found
    """
    deleted = mongo_service.delete_product(product_id)
    if not deleted:
        return jsonify({"error": "Product not found"}), 404

    es_service.delete_product(product_id)
    cache_service.delete(f"products:{product_id}")
    cache_service.delete_pattern("products:list:*")
    return jsonify({"message": "Product deleted"}), 200
