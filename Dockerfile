FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
# Not needed to serve traffic - included so the same image can run
# scripts/reconcile.py as a k8s CronJob (see
# k8s/base/app/reconcile-cronjob.yaml) without a second image to build,
# version, and keep in sync with the app.
COPY scripts/ ./scripts/

EXPOSE 5000

# gthread (not the sync default) matters here: every request makes blocking
# network calls to Mongo, Elasticsearch, and Redis, so a sync worker sits
# idle-but-occupied for most of a request's wall time. Threads let each
# worker process serve several concurrently-waiting requests instead of
# needing a pod per in-flight request; gthread ships in gunicorn itself, so
# unlike gevent this needs no extra dependency.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--worker-class", "gthread", "--threads", "4", "--timeout", "30", "app.main:app"]
