from app.services import cache_service, es_service


def test_create_without_idempotency_key_is_unaffected(client, sample_product):
    resp = client.post("/products", json=sample_product)
    assert resp.status_code == 201


def test_repeated_post_with_same_key_does_not_duplicate(client, sample_product):
    headers = {"Idempotency-Key": "key-1"}

    first = client.post("/products", json=sample_product, headers=headers)
    assert first.status_code == 201
    first_id = first.get_json()["product_id"]

    second = client.post("/products", json=sample_product, headers=headers)
    assert second.status_code == 201
    assert second.get_json()["product_id"] == first_id

    listed = client.get("/products").get_json()
    assert listed["total"] == 1


def test_different_keys_create_separate_products(client, sample_product):
    first = client.post("/products", json=sample_product, headers={"Idempotency-Key": "key-a"})
    second = client.post("/products", json=sample_product, headers={"Idempotency-Key": "key-b"})

    assert first.get_json()["product_id"] != second.get_json()["product_id"]
    assert client.get("/products").get_json()["total"] == 2


def test_concurrent_request_with_same_key_returns_409(client, sample_product):
    # Simulates a second request racing in while the first is still being
    # processed, by reserving the key directly rather than actually racing
    # two real requests against the (single-threaded) test client.
    cache_service.reserve_idempotency_key("key-in-flight")

    resp = client.post("/products", json=sample_product, headers={"Idempotency-Key": "key-in-flight"})
    assert resp.status_code == 409


def test_idempotency_key_released_on_validation_failure(client, sample_product):
    headers = {"Idempotency-Key": "key-retry"}

    bad = client.post("/products", json={"product_name": "Incomplete"}, headers=headers)
    assert bad.status_code == 422

    # A corrected retry with the same key must not be treated as a
    # duplicate of the failed attempt - nothing was actually created.
    good = client.post("/products", json=sample_product, headers=headers)
    assert good.status_code == 201


def test_idempotency_key_released_on_es_failure(client, monkeypatch, sample_product):
    headers = {"Idempotency-Key": "key-es-retry"}
    real_index = es_service.index_product

    def boom(product):
        raise RuntimeError("es unavailable")

    monkeypatch.setattr(es_service, "index_product", boom)
    failed = client.post("/products", json=sample_product, headers=headers)
    assert failed.status_code == 500

    # monkeypatch.undo() would also revert the app fixture's own patches
    # (mongo/es/redis _get_client) since they share one monkeypatch
    # instance; restore just this one attribute instead.
    monkeypatch.setattr(es_service, "index_product", real_index)
    retried = client.post("/products", json=sample_product, headers=headers)
    assert retried.status_code == 201
