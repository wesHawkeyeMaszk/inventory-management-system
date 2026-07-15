from app.services import cache_service


def test_metrics_endpoint_exposes_prometheus_format(client):
    resp = client.get("/metrics")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "flask_http_request_total" in body
    assert "inventory_app_info" in body


def test_response_carries_request_id_header(client):
    resp = client.get("/products")
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) > 0


def test_request_id_is_echoed_back_when_provided(client):
    resp = client.get("/products", headers={"X-Request-ID": "test-trace-123"})
    assert resp.headers["X-Request-ID"] == "test-trace-123"


def test_cache_get_records_hit_and_miss_counters(app, fake_redis):
    with app.app_context():
        counter = app.extensions["cache_result_counter"]

        cache_service.get("does-not-exist")
        miss_count = counter.labels(result="miss")._value.get()

        cache_service.set("k1", {"a": 1})
        cache_service.get("k1")
        hit_count = counter.labels(result="hit")._value.get()

    assert miss_count >= 1
    assert hit_count >= 1
