def _create(client, **overrides):
    product = {
        "product_name": "Widget",
        "product_category": "Tools",
        "price": 10.0,
        "available_quantity": 10,
        "description": "",
    }
    product.update(overrides)
    return client.post("/products", json=product).get_json()


def test_analytics_on_empty_inventory(client):
    resp = client.get("/products/analytics")
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["total_count"] == 0
    assert body["most_popular_category"] is None


def test_analytics_reflects_inventory(client):
    _create(client, product_category="Electronics", price=100.0, available_quantity=5)
    _create(client, product_category="Electronics", price=200.0, available_quantity=50)
    _create(client, product_category="Books", price=10.0, available_quantity=2)

    resp = client.get("/products/analytics")
    body = resp.get_json()

    assert body["total_count"] == 3
    assert body["most_popular_category"] == "Electronics"
    assert body["average_price"] == round((100.0 + 200.0 + 10.0) / 3, 2)
    assert body["low_stock_count"] == 2  # threshold defaults to 10


def test_analytics_groups_categories_case_insensitively(client):
    """Products/search filters by category case-insensitively in
    Elasticsearch (see test_search_category_filter_is_case_insensitive) -
    analytics should agree with that notion of "same category" rather than
    splitting "Electronics" and "electronics" into two buckets."""
    _create(client, product_category="Electronics")
    _create(client, product_category="electronics")
    _create(client, product_category="Books")

    body = client.get("/products/analytics").get_json()

    assert body["most_popular_category"] == "Electronics"
    breakdown = {c["category"]: c["count"] for c in body["category_breakdown"]}
    assert breakdown == {"Electronics": 2, "Books": 1}


def test_analytics_is_cached(client):
    _create(client)
    first = client.get("/products/analytics")
    assert first.headers["X-Cache"] == "MISS"

    second = client.get("/products/analytics")
    assert second.headers["X-Cache"] == "HIT"
