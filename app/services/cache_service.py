import json
import redis
from flask import current_app

_client = None

IDEMPOTENCY_TTL = 24 * 60 * 60  # 24h - long enough to cover realistic client retry windows
PENDING = "pending"


def _get_client():
    """Return a process-wide Redis client, created lazily on first use.

    redis-py's client is backed by a connection pool and is safe to reuse
    across requests; recreating it per call (the previous behaviour here)
    opened a fresh TCP connection for every single cache read or write.
    """
    global _client
    if _client is None:
        kwargs = {"socket_connect_timeout": 3, "socket_timeout": 5}
        # REDIS_URI intentionally carries no credentials (see
        # app/config.py) so it's safe to log/inspect; the password, if any,
        # is supplied separately and merged in here by redis-py.
        password = current_app.config.get("REDIS_PASSWORD")
        if password:
            kwargs["password"] = password
        _client = redis.from_url(current_app.config["REDIS_URI"], **kwargs)
    return _client


def _record(result):
    """Best-effort increment of the cache-result counter (see app/main.py).
    Absent in a bare app-context test that skips create_app(), so this is
    itself wrapped in try/except rather than assumed to exist.
    """
    try:
        current_app.extensions["cache_result_counter"].labels(result=result).inc()
    except Exception:
        pass


def get(key):
    try:
        value = _get_client().get(key)
        hit = value is not None
        _record("hit" if hit else "miss")
        return json.loads(value) if hit else None
    except Exception:
        _record("error")
        return None


def set(key, value, ttl=None):
    try:
        ttl = ttl or current_app.config["CACHE_TTL"]
        _get_client().setex(key, ttl, json.dumps(value))
    except Exception:
        pass


def delete(key):
    try:
        _get_client().delete(key)
    except Exception:
        pass


def delete_pattern(pattern, batch_size=500):
    """Delete all keys matching pattern using SCAN instead of KEYS, which
    would otherwise block the Redis event loop on a large keyspace.

    The scan is fully drained before any deletes happen: deleting keys
    while a SCAN cursor is still in flight can trigger a hash-table
    resize on the server, which is free to reorder buckets mid-cursor and
    cause some still-matching keys to be skipped entirely.
    """
    try:
        client = _get_client()
        keys = list(client.scan_iter(match=pattern, count=batch_size))
        for i in range(0, len(keys), batch_size):
            batch = keys[i:i + batch_size]
            client.delete(*batch)
    except Exception:
        pass


def reserve_idempotency_key(key):
    """Atomically claim an Idempotency-Key for a write.

    Returns True if this call is the first to see the key (the caller
    should do the real work). Returns False if a result already exists or
    another request is still processing it (the caller should look the
    result up via get_idempotency_result instead of repeating the write).

    Fails open (returns True) on a Redis outage rather than blocking every
    write on a cache being reachable - this makes idempotency best-effort
    rather than guaranteed under a Redis outage, which is an acceptable
    degrade for a cache-backed (not correctness-critical-store-backed)
    implementation, matching how the rest of this module already treats
    Redis as optional infrastructure.
    """
    try:
        return bool(_get_client().set(
            f"idempotency:{key}", json.dumps(PENDING),
            nx=True, ex=IDEMPOTENCY_TTL,
        ))
    except Exception:
        return True


def get_idempotency_result(key):
    """Returns PENDING if another request is mid-flight for this key,
    {"status": int, "body": ...} if a prior request already completed, or
    None if Redis is unreachable or the key was never reserved."""
    try:
        value = _get_client().get(f"idempotency:{key}")
        return json.loads(value) if value is not None else None
    except Exception:
        return None


def store_idempotency_result(key, status_code, body):
    try:
        _get_client().set(
            f"idempotency:{key}", json.dumps({"status": status_code, "body": body}),
            ex=IDEMPOTENCY_TTL,
        )
    except Exception:
        pass


def release_idempotency_key(key):
    """Delete a reservation so a retry with the same key actually retries
    the operation, rather than being stuck permanently pending or blocked.
    Used when the reserved request turned out not to have any lasting side
    effect worth deduplicating (failed validation, or a failure that was
    itself rolled back) - see app/routes/products.py."""
    delete(f"idempotency:{key}")
