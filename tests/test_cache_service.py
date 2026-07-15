from app.services import cache_service


def test_get_set_roundtrip(app, fake_redis):
    with app.app_context():
        cache_service.set("k1", {"a": 1})
        assert cache_service.get("k1") == {"a": 1}


def test_get_missing_key_returns_none(app):
    with app.app_context():
        assert cache_service.get("does-not-exist") is None


def test_delete_pattern_removes_only_matching_keys(app, fake_redis):
    with app.app_context():
        cache_service.set("products:list:1:20:name:asc", {"x": 1})
        cache_service.set("products:list:2:20:name:asc", {"x": 2})
        cache_service.set("products:abc123", {"x": 3})

        cache_service.delete_pattern("products:list:*")

        assert fake_redis.get("products:list:1:20:name:asc") is None
        assert fake_redis.get("products:list:2:20:name:asc") is None
        assert fake_redis.get("products:abc123") is not None


def test_delete_pattern_uses_scan_not_keys(app, fake_redis, monkeypatch):
    """KEYS blocks the whole Redis server on a large keyspace; delete_pattern
    must use the cursor-based SCAN instead."""
    with app.app_context():
        cache_service.set("products:list:1", {"x": 1})

        def _blocked(*args, **kwargs):
            raise AssertionError("delete_pattern must not call KEYS")

        monkeypatch.setattr(fake_redis, "keys", _blocked)

        cache_service.delete_pattern("products:list:*")  # should not raise
        assert fake_redis.get("products:list:1") is None


def test_delete_pattern_batches_across_many_keys(app, fake_redis):
    with app.app_context():
        for i in range(1200):
            cache_service.set(f"products:list:{i}", {"i": i})

        cache_service.delete_pattern("products:list:*", batch_size=100)

        remaining = list(fake_redis.scan_iter(match="products:list:*"))
        assert remaining == []
