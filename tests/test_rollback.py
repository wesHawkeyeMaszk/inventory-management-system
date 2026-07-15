from app.services import es_service, mongo_service


def test_create_rolls_back_mongo_write_when_es_indexing_fails(client, monkeypatch, sample_product):
    def boom(product):
        raise RuntimeError("es unavailable")

    monkeypatch.setattr(es_service, "index_product", boom)

    resp = client.post("/products", json=sample_product)
    assert resp.status_code == 500

    # No orphaned Mongo doc left behind after the rollback.
    resp = client.get("/products")
    assert resp.get_json()["total"] == 0


def test_update_rolls_back_to_previous_values_when_es_indexing_fails(client, monkeypatch, sample_product, app):
    created = client.post("/products", json=sample_product).get_json()
    product_id = created["product_id"]

    def boom(product):
        raise RuntimeError("es unavailable")

    monkeypatch.setattr(es_service, "index_product", boom)

    resp = client.put(f"/products/{product_id}", json={"price": 1.0})
    assert resp.status_code == 500

    with app.app_context():
        current = mongo_service.get_product(product_id)
    assert current["price"] == sample_product["price"]


def test_bulk_create_rolls_back_only_the_items_that_failed_to_index(client, monkeypatch, sample_product):
    calls = {"n": 0}
    real_index = es_service.index_product

    def flaky_index(product):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("es unavailable")
        return real_index(product)

    monkeypatch.setattr(es_service, "index_product", flaky_index)

    payload = [dict(sample_product, product_name=f"Widget {i}") for i in range(3)]
    resp = client.post("/products/bulk", json=payload)

    assert resp.status_code == 207
    body = resp.get_json()
    assert body["created"] == 2
    assert len(body["errors"]) == 1

    listed = client.get("/products").get_json()
    assert listed["total"] == 2


def test_delete_succeeds_even_if_es_delete_fails(client, monkeypatch, sample_product, fake_es):
    created = client.post("/products", json=sample_product).get_json()
    product_id = created["product_id"]

    def boom(index, id):
        raise RuntimeError("es unavailable")

    # Fail at the ES client level so es_service.delete_product's own
    # try/except (which logs rather than raises) is exercised for real.
    monkeypatch.setattr(fake_es, "delete", boom)

    # Mongo is authoritative; a search-index failure on delete shouldn't
    # block the delete or surface as an error to the caller.
    resp = client.delete(f"/products/{product_id}")
    assert resp.status_code == 200

    resp = client.get(f"/products/{product_id}")
    assert resp.status_code == 404
