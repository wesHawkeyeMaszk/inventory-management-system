def test_health_endpoint_reports_dependency_status(client):
    # health.py connects directly to the configured Mongo/ES/Redis URIs
    # rather than going through the service fakes, so in a sandboxed test
    # environment we only assert on shape, not on a specific up/down state.
    resp = client.get("/health")
    body = resp.get_json()

    assert resp.status_code in (200, 503)
    assert set(body) >= {"mongo", "elasticsearch", "redis", "status"}
    assert body["status"] in ("healthy", "degraded")


def test_liveness_endpoint_does_not_touch_dependencies(client):
    # /health/live must stay up even when Mongo/ES/Redis are unreachable,
    # since it backs the k8s livenessProbe - it should never cause kubelet
    # to restart a pod just because a downstream dependency is degraded.
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "alive"}
