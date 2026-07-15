def test_create_and_get_product(client, sample_product):
    resp = client.post("/products", json=sample_product)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["product_name"] == "Mechanical Keyboard"
    product_id = body["product_id"]

    resp = client.get(f"/products/{product_id}")
    assert resp.status_code == 200
    assert resp.get_json()["product_id"] == product_id


def test_get_product_not_found(client):
    resp = client.get("/products/does-not-exist")
    assert resp.status_code == 404


def test_create_product_missing_fields(client):
    resp = client.post("/products", json={"product_name": "Widget"})
    assert resp.status_code == 422
    assert "error" in resp.get_json()


def test_create_product_low_stock_warning(client, sample_product):
    sample_product["available_quantity"] = 3
    resp = client.post("/products", json=sample_product)
    assert resp.status_code == 201
    assert "Low stock" in resp.get_json()["warning"]


def test_create_product_no_warning_when_stock_healthy(client, sample_product):
    sample_product["available_quantity"] = 50
    resp = client.post("/products", json=sample_product)
    assert resp.status_code == 201
    assert "warning" not in resp.get_json()


def test_update_product(client, sample_product):
    created = client.post("/products", json=sample_product).get_json()
    product_id = created["product_id"]

    resp = client.put(f"/products/{product_id}", json={"price": 99.99})
    assert resp.status_code == 200
    assert resp.get_json()["price"] == 99.99

    history = client.get(f"/products/{product_id}/history").get_json()
    assert len(history) == 1
    assert history[0]["field"] == "price"


def test_update_product_not_found(client):
    resp = client.put("/products/does-not-exist", json={"price": 1})
    assert resp.status_code == 404


def test_update_product_invalid_price(client, sample_product):
    created = client.post("/products", json=sample_product).get_json()
    resp = client.put(f"/products/{created['product_id']}", json={"price": "bad"})
    assert resp.status_code == 422


def test_update_product_rejects_negative_price(client, sample_product):
    created = client.post("/products", json=sample_product).get_json()
    resp = client.put(f"/products/{created['product_id']}", json={"price": -5})
    assert resp.status_code == 422


def test_update_product_rejects_negative_quantity(client, sample_product):
    created = client.post("/products", json=sample_product).get_json()
    resp = client.put(f"/products/{created['product_id']}", json={"available_quantity": -1})
    assert resp.status_code == 422


def test_update_product_rejects_unknown_fields(client, sample_product):
    created = client.post("/products", json=sample_product).get_json()
    resp = client.put(f"/products/{created['product_id']}", json={"not_a_real_field": "x"})
    assert resp.status_code == 422


def test_update_product_ignores_echoed_metadata_fields(client, sample_product):
    """A client that GETs a product, edits it locally, and PUTs the whole
    thing back (including server-generated fields like product_id,
    created_at, _id) shouldn't be rejected for echoing those back."""
    created = client.post("/products", json=sample_product).get_json()
    payload = dict(created, price=199.99)

    resp = client.put(f"/products/{created['product_id']}", json=payload)
    assert resp.status_code == 200
    assert resp.get_json()["price"] == 199.99


def test_create_product_rejects_unknown_fields(client, sample_product):
    sample_product["not_a_real_field"] = "x"
    resp = client.post("/products", json=sample_product)
    assert resp.status_code == 422


def test_list_products_rejects_invalid_sort_field(client):
    resp = client.get("/products?sort=__proto__")
    assert resp.status_code == 400


def test_delete_product(client, sample_product):
    created = client.post("/products", json=sample_product).get_json()
    product_id = created["product_id"]

    resp = client.delete(f"/products/{product_id}")
    assert resp.status_code == 200

    resp = client.get(f"/products/{product_id}")
    assert resp.status_code == 404


def test_delete_product_not_found(client):
    resp = client.delete("/products/does-not-exist")
    assert resp.status_code == 404


def test_list_products_pagination(client, sample_product):
    for i in range(5):
        product = dict(sample_product)
        product["product_name"] = f"Widget {i}"
        client.post("/products", json=product)

    resp = client.get("/products?page=1&limit=2")
    body = resp.get_json()
    assert resp.status_code == 200
    assert len(body["products"]) == 2
    assert body["total"] == 5
    assert body["pages"] == 3


def test_list_products_cache_hit_header(client, sample_product):
    client.post("/products", json=sample_product)

    first = client.get("/products")
    assert first.headers["X-Cache"] == "MISS"

    second = client.get("/products")
    assert second.headers["X-Cache"] == "HIT"


def test_create_invalidates_list_cache(client, sample_product):
    client.get("/products")  # warm the cache with an empty list
    client.post("/products", json=sample_product)

    resp = client.get("/products")
    assert resp.headers["X-Cache"] == "MISS"
    assert resp.get_json()["total"] == 1


def test_bulk_create_products(client, sample_product):
    payload = [dict(sample_product, product_name=f"Widget {i}") for i in range(3)]
    resp = client.post("/products/bulk", json=payload)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["created"] == 3
    assert body["errors"] == []


def test_bulk_create_rejects_too_many(client, sample_product):
    payload = [dict(sample_product) for _ in range(501)]
    resp = client.post("/products/bulk", json=payload)
    assert resp.status_code == 400


def test_bulk_create_reports_per_item_validation_errors(client, sample_product):
    payload = [dict(sample_product), {"product_name": "Incomplete"}]
    resp = client.post("/products/bulk", json=payload)
    assert resp.status_code == 422
    assert resp.get_json()["errors"][0]["index"] == 1
