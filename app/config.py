import os


class Config:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/inventory")
    ES_URI = os.getenv("ES_URI", "http://localhost:9200")
    REDIS_URI = os.getenv("REDIS_URI", "redis://localhost:6379/0")
    DEBUG = os.getenv("FLASK_ENV", "production") == "development"
    CACHE_TTL = int(os.getenv("CACHE_TTL", "30"))
    LOW_STOCK_THRESHOLD = int(os.getenv("LOW_STOCK_THRESHOLD", "10"))

    # Unset by default -> mongo_service/cache_service connect with no auth,
    # exactly matching Mongo's/Redis's own out-of-the-box behaviour. Kept as
    # separate username/password values rather than embedded in MONGO_URI /
    # REDIS_URI above so those two stay safe to log or put in a ConfigMap,
    # and so enabling auth is "add a Secret", not "hand-edit a connection
    # string". Set via a k8s Secret in any real deployment - see
    # k8s/base/mongodb/secret.example.yaml.tpl and
    # k8s/base/redis/secret.example.yaml.tpl.
    MONGO_USERNAME = os.getenv("MONGO_USERNAME")
    MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

    # Unset by default -> write-endpoint auth (app/auth.py) is a no-op for
    # local dev/tests. Set via a k8s Secret in any real deployment.
    API_KEY = os.getenv("API_KEY")

    # Deliberately NOT REDIS_URI by default: falling back to in-memory
    # storage means the app never fails to start just because Redis is
    # unreachable (e.g. in CI, which runs no Redis service). A real
    # multi-replica deployment must point this at Redis - in-memory
    # storage is per-process, so each pod would enforce its own separate
    # limit instead of a shared one. See k8s/app/configmap.yaml.
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
