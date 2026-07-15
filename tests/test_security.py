"""Rate limiting and API-key auth are disabled in the shared `app` fixture
(see conftest.py) so the rest of the suite isn't affected by a shared
Limiter instance accumulating state across ~60 tests. These tests build
their own isolated app instance to exercise both mechanisms directly.
"""
from app.extensions import limiter


def test_write_endpoints_reject_missing_or_wrong_api_key(app, sample_product):
    app.config.update(API_KEY="secret-key")
    client = app.test_client()

    resp = client.post("/products", json=sample_product)
    assert resp.status_code == 401

    resp = client.post("/products", json=sample_product, headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


def test_write_endpoint_accepts_correct_api_key(app, sample_product):
    app.config.update(API_KEY="secret-key")
    client = app.test_client()

    resp = client.post("/products", json=sample_product, headers={"X-API-Key": "secret-key"})
    assert resp.status_code == 201


def test_read_endpoints_unaffected_by_api_key(app):
    app.config.update(API_KEY="secret-key")
    client = app.test_client()

    resp = client.get("/products")
    assert resp.status_code == 200


def test_create_product_rate_limit_returns_429_after_threshold(app, sample_product):
    # limiter.storage is a process-wide singleton shared across every test
    # app instance (see app/extensions.py); reset it so this test's count
    # isn't affected by whatever ran before it in the suite.
    limiter.reset()
    app.config.update(RATELIMIT_ENABLED=True)
    client = app.test_client()

    statuses = [client.post("/products", json=dict(sample_product, product_name=f"W{i}")).status_code
                for i in range(21)]

    assert statuses.count(201) == 20
    assert statuses[-1] == 429
