from flask import Flask
from flask_cors import CORS
from flasgger import Swagger
from prometheus_client import CollectorRegistry, Counter
from prometheus_flask_exporter import PrometheusMetrics
from app.config import Config
from app.routes.products import products_bp
from app.routes.analytics import analytics_bp
from app.routes.health import health_bp
from app.routes.game import game_bp
from app.logging_config import configure_logging, request_context_middleware
from app.extensions import limiter

SWAGGER_CONFIG = {
    "title": "Inventory Management API",
    "version": "1.0.0",
    "description": "REST API for managing product inventory with full-text search and analytics.",
    "uiversion": 3,
}


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    configure_logging()
    request_context_middleware(app)

    CORS(app)
    Swagger(app, template={"info": SWAGGER_CONFIG})

    # Exposes GET /metrics in Prometheus text format: request counts and
    # latency histograms by endpoint/method/status out of the box, plus a
    # custom cache-hit/miss counter used by services/cache_service.py.
    # /health* and /metrics are excluded from their own request metrics so
    # kubelet's probe traffic doesn't skew the app's real request stats.
    #
    # A fresh CollectorRegistry is created per create_app() call rather than
    # relying on prometheus_client's process-global default registry:
    # gunicorn only calls create_app() once per worker so this is a no-op
    # in production, but the test suite calls create_app() once per test,
    # and registering the same metric name twice against the global
    # registry raises ValueError("Duplicated timeseries...").
    registry = CollectorRegistry()
    metrics = PrometheusMetrics(app, registry=registry, excluded_paths=["/health", "/health/live", "/metrics"])
    metrics.info("inventory_app_info", "Inventory Management API", version="1.0.0")

    app.extensions["cache_result_counter"] = Counter(
        "inventory_cache_result_total",
        "Cache lookups by result (hit, miss, or error)",
        ["result"],
        registry=registry,
    )

    if app.config.get("REDIS_PASSWORD"):
        # Flask-Limiter reads RATELIMIT_STORAGE_OPTIONS and forwards it to
        # redis.from_url(RATELIMIT_STORAGE_URI, **options) - same
        # separate-credential approach as mongo_service/cache_service, so
        # the password never has to be embedded in RATELIMIT_STORAGE_URI
        # itself.
        app.config["RATELIMIT_STORAGE_OPTIONS"] = {"password": app.config["REDIS_PASSWORD"]}
    limiter.init_app(app)

    app.register_blueprint(products_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(game_bp)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
