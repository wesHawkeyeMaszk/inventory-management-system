from flask import Blueprint, jsonify
from app.services import mongo_service, es_service, cache_service

health_bp = Blueprint("health", __name__)


@health_bp.route("/health/live", methods=["GET"])
def liveness():
    """
    Liveness check - process is up and able to handle a request.
    ---
    tags: [System]
    responses:
      200:
        description: Process is alive
    """
    # Deliberately touches no external dependency. Used for the k8s
    # livenessProbe: if this handler can run, the Flask process itself is
    # fine, so kubelet shouldn't restart the pod over a Mongo/ES/Redis
    # outage it can't fix - that's what the readinessProbe (/health) is for.
    return jsonify({"status": "alive"}), 200


@health_bp.route("/health", methods=["GET"])
def health_check():
    """
    Dependency health check.
    ---
    tags: [System]
    responses:
      200:
        description: All services healthy
      503:
        description: One or more services degraded
    """
    # Reuses each service's shared client (see app/services/*.py) rather
    # than opening a throwaway connection per probe - this endpoint is
    # polled by the k8s readiness/liveness probes every few seconds, so a
    # fresh MongoClient/Elasticsearch/Redis connection per hit would add up.
    status = {}
    ok = True

    try:
        mongo_service._get_client().admin.command("ping")
        status["mongo"] = "ok"
    except Exception as e:
        status["mongo"] = f"error: {e}"
        ok = False

    try:
        es_service._get_client().cluster.health(timeout="1s")
        status["elasticsearch"] = "ok"
    except Exception as e:
        status["elasticsearch"] = f"error: {e}"
        ok = False

    try:
        cache_service._get_client().ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = f"error: {e}"
        ok = False

    status["status"] = "healthy" if ok else "degraded"
    return jsonify(status), 200 if ok else 503
