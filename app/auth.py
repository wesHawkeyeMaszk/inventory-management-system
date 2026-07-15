import hmac
from functools import wraps
from flask import current_app, jsonify, request


def require_api_key(fn):
    """Gate a mutating endpoint behind an X-API-Key header.

    If API_KEY isn't configured (the default - see app/config.py), this is
    a no-op: local dev and the test suite stay frictionless. Setting API_KEY
    (via a k8s Secret, never the plaintext ConfigMap - see
    k8s/app/secret.example.yaml) turns on enforcement for every route
    wrapped with this decorator.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        configured_key = current_app.config.get("API_KEY")
        if not configured_key:
            return fn(*args, **kwargs)

        # Constant-time comparison: a plain != short-circuits on the first
        # mismatched byte, which leaks how many leading characters of the
        # guess were correct via response-time differences (a timing
        # side-channel) when an attacker can send enough requests to measure it.
        provided_key = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(provided_key, configured_key):
            return jsonify({"error": "Missing or invalid X-API-Key header"}), 401

        return fn(*args, **kwargs)

    return wrapper
