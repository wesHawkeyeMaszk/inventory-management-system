from app.services import mongo_service


def _create(client, **overrides):
    product = {
        "product_name": "Widget",
        "product_category": "Tools",
        "price": 10.0,
        "available_quantity": 10,
        "description": "a handy widget",
    }
    product.update(overrides)
    return client.post("/products", json=product).get_json()


def test_search_requires_query_param(client):
    resp = client.get("/products/search")
    assert resp.status_code == 400


def test_search_matches_name_and_description(client):
    _create(client, product_name="Laptop Pro", description="15-inch laptop")
    _create(client, product_name="Desk Lamp", description="LED desk lamp")

    resp = client.get("/products/search?query=laptop")
    body = resp.get_json()
    assert body["total"] == 1
    assert body["products"][0]["product_name"] == "Laptop Pro"


def test_search_filters_by_category(client):
    _create(client, product_name="Widget A", product_category="Tools")
    _create(client, product_name="Widget B", product_category="Electronics")

    resp = client.get("/products/search?query=widget&category=Electronics")
    body = resp.get_json()
    assert body["total"] == 1
    assert body["products"][0]["product_category"] == "Electronics"


def test_search_category_filter_is_case_insensitive(client):
    _create(client, product_name="Widget A", product_category="Electronics")

    resp = client.get("/products/search?query=widget&category=electronics")
    assert resp.get_json()["total"] == 1


def test_search_filters_by_price_range(client):
    _create(client, product_name="Cheap Widget", price=5.0)
    _create(client, product_name="Mid Widget", price=50.0)
    _create(client, product_name="Costly Widget", price=500.0)

    resp = client.get("/products/search?query=widget&min_price=10&max_price=100")
    body = resp.get_json()
    assert body["total"] == 1
    assert body["products"][0]["product_name"] == "Mid Widget"


def test_search_pagination(client):
    for i in range(5):
        _create(client, product_name=f"Widget {i}")

    resp = client.get("/products/search?query=widget&page=1&limit=2")
    body = resp.get_json()
    assert body["total"] == 5
    assert len(body["products"]) == 2
    assert body["pages"] == 3

    resp2 = client.get("/products/search?query=widget&page=2&limit=2")
    body2 = resp2.get_json()
    assert len(body2["products"]) == 2
    # Pages shouldn't overlap.
    ids_page1 = {p["product_id"] for p in body["products"]}
    ids_page2 = {p["product_id"] for p in body2["products"]}
    assert ids_page1.isdisjoint(ids_page2)


def test_search_hydrates_with_single_mongo_query(client, monkeypatch):
    for i in range(4):
        _create(client, product_name=f"Widget {i}")

    calls = []
    original = mongo_service.get_products_by_ids

    def spy(ids):
        calls.append(ids)
        return original(ids)

    monkeypatch.setattr(mongo_service, "get_products_by_ids", spy)

    resp = client.get("/products/search?query=widget")
    assert resp.status_code == 200
    assert len(calls) == 1  # one batch hydration call, not one per result


def test_search_no_matches_returns_empty(client):
    _create(client, product_name="Widget")
    resp = client.get("/products/search?query=nonexistent")
    body = resp.get_json()
    assert body["products"] == []
    assert body["total"] == 0


def test_suggest_requires_q_param(client):
    resp = client.get("/products/suggest")
    assert resp.status_code == 400


def test_suggest_returns_matches(client):
    _create(client, product_name="Laptop Pro 15")
    resp = client.get("/products/suggest?q=lap")
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["product_name"] == "Laptop Pro 15"
