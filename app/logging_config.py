import json
import logging
import time
import uuid
from flask import g, request


class _JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if getattr(record, "request_id", None):
            payload["request_id"] = record.request_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


class _RequestIdFilter(logging.Filter):
    """Attaches the current request's correlation id to every log record
    emitted while handling it, so a warning logged deep inside
    mongo_service.py or es_service.py can be tied back to the HTTP request
    that triggered it by grepping a single request_id across log lines -
    the two services otherwise have no shared context to correlate on.
    """

    def filter(self, record):
        try:
            record.request_id = g.request_id
        except RuntimeError:
            record.request_id = None
        return True


class _JsonHandler(logging.StreamHandler):
    """Marker subclass so configure_logging() can find and replace its own
    handler on repeated calls without touching unrelated ones."""


def configure_logging():
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Replace only handlers this module previously installed, so repeated
    # create_app() calls (every test in the suite makes one) don't pile up
    # duplicate handlers or clobber handlers other tooling (e.g. pytest's
    # own log capture) may have attached to the root logger.
    root.handlers = [h for h in root.handlers if not isinstance(h, _JsonHandler)]

    handler = _JsonHandler()
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(_RequestIdFilter())
    root.addHandler(handler)


def request_context_middleware(app):
    """Assigns/propagates X-Request-ID and logs one structured line per
    request. Registered once per app instance from create_app()."""

    @app.before_request
    def _assign_request_id():
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        g.request_start = time.monotonic()

    @app.after_request
    def _log_request(response):
        duration_ms = (time.monotonic() - g.request_start) * 1000 if "request_start" in g else 0.0
        response.headers["X-Request-ID"] = g.get("request_id", "")
        logging.getLogger("app.request").info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response

    return app
