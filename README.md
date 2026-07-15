# Inventory Management System

A REST API for managing product inventory with full-text search and analytics, built with Flask, MongoDB, Elasticsearch, and deployed on Kubernetes.

---

## Architecture

```
┌─────────────┐     HTTP      ┌──────────────────────────────────────────┐
│   Client    │ ─────────────▶│              Flask REST API               │
└─────────────┘               │  (app/routes/products.py + analytics.py) │
                               └──────────┬─────────────────┬─────────────┘
                                          │                 │
                               ┌──────────▼──────┐ ┌───────▼──────────┐
                               │    MongoDB       │ │  Elasticsearch   │
                               │  (source of      │ │  (full-text      │
                               │   truth, CRUD,   │ │   search,        │
                               │   analytics)     │ │   descriptions)  │
                               └─────────────────┘ └──────────────────┘
```

**Key design decisions:**
- MongoDB is the authoritative store for all product fields.
- Elasticsearch holds a lightweight projection (product_id, name, category, description) for full-text search. Search results hydrate full documents from MongoDB.
- Both stores are updated synchronously on every write so they stay consistent. This has a known limitation under a crash mid-write - see [`docs/adr/0001-mongo-elasticsearch-consistency.md`](docs/adr/0001-mongo-elasticsearch-consistency.md) for the tradeoff and what we'd do instead at scale.
- Routes are registered with `/products/search` and `/products/analytics` before `/products/<id>` to prevent Flask from matching literal path segments as the `<id>` parameter.
- MongoDB/Elasticsearch/Redis clients are created once per process and reused (not per request) - see `app/services/*.py`.
- Elasticsearch's category filter and MongoDB's analytics grouping share the same notion of "the same category" (case-insensitive) - see "Above and beyond" below for why that's called out specifically.

---

## Above and beyond the assignment's minimum

The assignment's four CRUD verbs, search, and analytics endpoint are implemented as specified (see "API Reference" below). Beyond that minimum, this project also includes the following - each chosen because it's the kind of gap that's invisible in a demo but shows up immediately in production:

**Data layer**
- **Indexes, created idempotently on first real connection** (`mongo_service.ensure_indexes`, called lazily from `_get_db()` so it needs no separate migration step someone has to remember to run): a unique index on `product_id`, single-field indexes on every field `GET /products?sort=` can be asked to sort by, and a compound `(product_category, price)` index backing the analytics aggregation. Without these, `get_analytics()`'s `$group` and any non-trivial sort are full collection scans.
- **`GET /products?sort=` is allowlisted** (`SORTABLE_FIELDS` in `app/routes/products.py`) rather than passed straight to Mongo's `.sort()` - an arbitrary field name from a query string would otherwise let a caller force an unindexed sort.
- **Elasticsearch's category filter and MongoDB's analytics grouping agree on case.** `GET /products/search?category=` already matched case-insensitively in Elasticsearch; the analytics `$group` on `product_category` originally didn't, so `"Electronics"` and `"electronics"` would count as two different categories in `/products/analytics` while being treated as the same category by search. Fixed by grouping on `$toLower(product_category)` and keeping a `$first` value for display (`mongo_service.get_analytics`) - see `test_analytics_groups_categories_case_insensitively`.
- **`created_at`/`updated_at` timestamps** on every product, set on create and refreshed on every update.
- **Price/quantity change history** (`price_history` collection, `GET /products/{id}/history`) - not required, but a real inventory system needs to answer "when did this go out of stock" or "when did the price change," not just its current state.

**API design**
- **Server-generated metadata is silently ignored, not rejected, on write.** Any other unrecognized field is a 422. This specifically supports the common "GET a product, edit it locally, PUT the whole thing back" client pattern without penalizing the client for echoing back `product_id`/`created_at`/`_id` - see `test_update_product_ignores_echoed_metadata_fields` vs. `test_update_product_rejects_unknown_fields`.
- **`PUT` validates the same invariants `POST` does.** The original partial-update path coerced `price`/`available_quantity` types but never checked they were non-negative, so `PUT` would silently accept a negative price that `POST` would reject. Both now share `validate_product`/`validate_product_update` in `app/models/product.py`.
- Pagination + sorting on `GET /products`, category/price-range filters on search, bulk create with per-item error reporting (`207 Multi-Status` on partial failure), rate limiting on writes, optional `X-API-Key` auth, Redis-backed response caching with cache-invalidation on write and an `X-Cache: HIT|MISS` header.

**Consistency**
- Mongo and Elasticsearch writes are wrapped so the API never returns success for a write that only landed in one store - see the ADR linked above for exactly what this does and doesn't guarantee.
- **`scripts/reconcile.py`, run every 15 minutes as a `CronJob`** (`k8s/base/app/reconcile-cronjob.yaml`), diffs the `product_id` sets in Mongo and Elasticsearch and repairs drift (re-indexes what's missing, deletes what's orphaned). This doesn't remove the crash window the ADR describes - only moving the Elasticsearch write off the request path entirely (Change Streams/Debezium) does that - but it means drift gets found and fixed within one schedule interval instead of sitting undetected indefinitely, for a fraction of the infrastructure. Verified against real, deliberately-injected drift (deleted a doc from each store independently, outside the API) on both docker-compose and a real minikube cluster - see `test`/`--repair` output below.
- **`Idempotency-Key` support on `POST /products`.** A retried create with the same key returns the original response instead of inserting a second product (Redis-backed reservation with a release-on-failure path, so a corrected retry after a 422 or a transient Elasticsearch outage isn't stuck replaying the failure) - see `app/services/cache_service.py`'s `reserve_idempotency_key`/`release_idempotency_key` and `tests/test_idempotency.py`.

**Security**
- Write-endpoint API keys are compared with `hmac.compare_digest` rather than `!=`, so a wrong guess can't be narrowed down via response-time differences (a timing side-channel) - see `app/auth.py`.
- `NetworkPolicy` manifests (`k8s/base/networkpolicy.yaml`) restrict ingress on Mongo/Elasticsearch/Redis to pods labeled `app: inventory-app` only. Verified this is real on a CNI that enforces it (a plain `busybox` pod in-namespace can reach `mongodb:27017` on minikube's default CNI, which doesn't enforce `NetworkPolicy` at all - Calico/Cilium, standard on EKS/GKE, do).
- **Mongo and Redis now support real authentication**, off by default. `mongodb-credentials`/`redis-credentials` `Secret` templates (`k8s/base/mongodb/secret.example.yaml.tpl`, `k8s/base/redis/secret.example.yaml.tpl`) feed `MONGO_INITDB_ROOT_USERNAME/PASSWORD` into Mongo directly, and a shell-conditional `${REDIS_PASSWORD:+--requirepass ...}` into Redis's start command (`k8s/base/redis/deployment.yaml`) - both `optional: true`, so each service stays unauthenticated (today's default) until its Secret exists. The app authenticates via separate `MONGO_USERNAME`/`MONGO_PASSWORD`/`REDIS_PASSWORD` config values passed as connection kwargs (`mongo_service._get_client`, `cache_service._get_client`), not embedded in `MONGO_URI`/`REDIS_URI`, so those two stay safe to put in a plain `ConfigMap`. The rate limiter's Redis-backed storage picks up the same password via Flask-Limiter's `RATELIMIT_STORAGE_OPTIONS`. **Verified end-to-end**, not just wired: docker-compose now runs both services with auth enforced by default (direct unauthenticated `redis-cli ping` returns `NOAUTH Authentication required`; the app connects and operates normally), and the same Secret-driven setup was deployed to a real minikube cluster and confirmed working, including the rate limiter under the authenticated storage backend.

**Observability & operations**
- Prometheus metrics, structured JSON logs correlated by `X-Request-ID` across all three data stores, separate readiness (`/health`) vs. liveness (`/health/live`) probes, a starter Grafana dashboard.
- An HPA autoscaling demo that was actually run against a real minikube cluster, not just asserted to work - see [`docs/load-test-results.md`](docs/load-test-results.md).
- **`gunicorn` runs `gthread` workers with `--threads 4`, not the sync default.** Every request makes blocking network calls to Mongo, Elasticsearch, and Redis; a sync worker is idle-but-occupied for most of a request's wall time, so it can only serve one in-flight request per worker regardless of how much of that time is spent waiting on I/O. This is the cheaper lever to pull before reaching for more replicas.

**Kubernetes**
- Kustomize base + dev/staging/prod overlays (not one flat manifest directory), pod anti-affinity + topology spread constraints, a PodDisruptionBudget, and an illustrative (not applied) Terraform path to EKS.
- **MongoDB and Elasticsearch run as `StatefulSet`s on headless `Service`s, not `Deployment`s on a plain PVC.** A `Deployment` doesn't give a stateful workload the stable per-pod identity a rolling update - or a future multi-member replica set/cluster - needs; a `StatefulSet` does, even at a single replica. Verified on a real minikube cluster: `kubectl get pvc` shows the auto-provisioned, correctly-named `mongo-storage-mongodb-0` / `es-storage-elasticsearch-0` volumes from each `volumeClaimTemplates`, both `Bound`.

**Testing**
- 83 tests, all running against in-memory fakes (`mongomock`, `fakeredis`, a hand-rolled Elasticsearch double) - no Docker services required to run the suite. Every fix in this section shipped with a test that would fail without it, and every one of them was additionally re-verified against a real docker-compose stack (real Mongo, real Elasticsearch, real Redis) and, for the Kubernetes-specific changes, a real minikube cluster - before being called done. Mocked tests passing was treated as necessary, not sufficient; a live run once caught a real bug the mocked suite couldn't (see below).

---

## Known limitations / what we'd do at production scale

An earlier pass through this project turned up more gaps than were worth fixing in the same breath - some were fixed (see "Above and beyond" above; a few had weaker justifications for skipping than first stated, on reflection, and got done once actually checked against a live stack). What's left below has a real, considered reason to stay out of scope rather than being deferred by default:

- **MongoDB and Elasticsearch are still single-node**, just on the right primitive now (`StatefulSet`, not `Deployment`) - no automatic failover, no multi-member replica set/cluster. Getting there needs the MongoDB Community/Enterprise Operator and ECK, which bring their own CRDs and operational surface; not justified to hand-roll and ship untested for a take-home-sized dataset. There's also still no backup/snapshot story for either data store.
- **No optimistic concurrency control on `PUT`.** Two concurrent updates to the same product silently last-write-wins; there's no version field or `If-Match` check. Livable at low write concurrency (product catalog edits aren't a hot path); would need addressing before supporting frequent concurrent writers.
- **`price` is stored as a 64-bit float, not `Decimal128`.** Binary floating point can't represent most decimal cents exactly. Not a contained fix - it touches the JSON encoder (no native Decimal128 JSON representation), the Elasticsearch mapping, the analytics `$avg`/`$min`/`$max` pipeline, and the frontend's number parsing all at once, which is a real migration rather than a patch.
- **`PUT` implements partial-update (PATCH) semantics under the PUT verb.** Strict REST says `PUT` should replace the full resource; omitted fields here are left untouched rather than cleared. Kept as-is deliberately: the assignment specifies `PUT /products/{id}` - "Update an existing product" - with no full-replace semantics implied, and changing the actual behavior here trades a real, specified contract for a theoretical one.
- **Skip/limit pagination**, not cursor-based - `.skip(n)` still scans and discards `n` documents server-side, which degrades at large offsets. Fine at catalog scale; keyset pagination (`_id > last_seen`) is the real answer at scale, but it's an API contract change (`page`/`limit` → a cursor token) the assignment doesn't ask for.
- **No distributed tracing.** Metrics and request-ID-correlated logs cover two of the three observability pillars; OpenTelemetry spans per downstream call (Mongo/ES/Redis) would show a slow request's time-in-each-dependency. Needs new infrastructure (a collector + Jaeger/Tempo) with nothing to look at without deploying that too - the next thing to reach for after this project, not part of it.

**A live test caught a real bug a mocked one didn't:** the first version of the reconcile `CronJob` above shipped without Mongo credentials wired into its pod spec - the mocked test suite has nothing that would ever catch that, since it never talks to a real, auth-enforcing Mongo. Running it for real on minikube against the newly-authenticated cluster failed immediately with `Command find requires authentication`, which is exactly the kind of gap "tests pass" hides and "actually run it" doesn't. Fixed by giving `scripts/reconcile.py` the same separate-credential support `mongo_service.py` already had, and wiring the same `mongodb-credentials` Secret into the CronJob's env. Left in as a reminder that mocked-test coverage and "verified working" are not the same claim.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Docker + Docker Compose | ≥ 24 |
| Python | 3.11+ |
| minikube | latest |
| kubectl | latest |
| [k6](https://k6.io/docs/get-started/installation/) | optional, for `scripts/load_test.js` |
| [terraform](https://developer.hashicorp.com/terraform/install) | optional, for `terraform/` (illustrative EKS path, not required for the minikube flow below) |

---

## Local Development (docker-compose)

```bash
cd inventory-system

# Start all services (MongoDB, Elasticsearch, Redis, Flask app)
docker-compose up --build -d

# Wait ~30s for Elasticsearch to initialise, then seed sample data.
# Mongo/Redis run with auth enforced by default in this compose file (a
# fixed dev-only password, see docker-compose.yml) - seed_data.py needs
# the matching credentials to connect.
pip3 install pymongo elasticsearch
python3 scripts/seed_data.py --mongo-username admin --mongo-password devpassword

# The API is now available at http://localhost:5000
```

Using a different `MONGO_ROOT_PASSWORD`/`REDIS_PASSWORD` (via a shell export or `.env` file)? Pass the same value to `seed_data.py --mongo-password` above.

---

## Kubernetes Deployment (minikube)

The manifests under `k8s/` are organized as a [Kustomize](https://kustomize.io/)
base + overlays (see "Environments" below) rather than one flat directory -
`k8s/overlays/dev` is the minikube target and reproduces exactly what a
flat `kubectl apply -f k8s/` across the old `namespace.yaml`, `app/`,
`mongodb/`, `elasticsearch/`, `redis/` directories used to do, just applied
in one step and with kustomize resolving the ordering/dependencies.

```bash
# 1. Start minikube
minikube start

# 2. Point Docker daemon to minikube's registry
eval $(minikube docker-env)

# 3. Build the app image inside minikube
docker build -t inventory-app:latest .

# 4. Apply the dev overlay (namespace + app + mongodb + elasticsearch + redis)
kubectl apply -k k8s/overlays/dev

# 5. Wait for pods to be ready
kubectl get pods -n inventory -w

# 6. Seed data (target the NodePort service)
APP_URL=$(minikube service inventory-app -n inventory --url)
python3 scripts/seed_data.py \
  --mongo mongodb://$(minikube ip):$(kubectl get svc mongodb -n inventory -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo 27017)/inventory \
  --es http://$(minikube ip):$(kubectl get svc elasticsearch -n inventory -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo 9200)

# Simpler alternative: port-forward the services and run seed against localhost
kubectl port-forward svc/mongodb 27017:27017 -n inventory &
kubectl port-forward svc/elasticsearch 9200:9200 -n inventory &
python3 scripts/seed_data.py
```

### Environments (Kustomize overlays)

```
k8s/
├── base/                # the actual resources: Deployments, Services, PVCs, HPA, PDB, ConfigMap
└── overlays/
    ├── dev/              # minikube - imagePullPolicy: Never, locally-built image
    ├── staging/          # registry-pulled image, 2 replicas
    └── prod/             # 3 replicas, higher resource limits, HPA maxReplicas: 20
```

Each overlay patches only what actually differs (image, replica count,
resource sizing) rather than duplicating the full manifest set - see
`k8s/overlays/*/kustomization.yaml`. `staging`/`prod` reference a
placeholder ECR image (`ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/inventory-app`)
that only resolves once the cluster is actually running on AWS - see
"Path to EKS" below.

```bash
kubectl apply -k k8s/overlays/staging   # or prod
```

### Autoscaling demo (HPA)

`k8s/base/app/hpa.yaml` scales `inventory-app` between 2 and 10 replicas on
CPU/memory utilization. To see it react, drive load at the deployed
service with the included k6 script and watch replicas climb:

```bash
kubectl port-forward svc/inventory-app 8080:80 -n inventory &
k6 run -e BASE_URL=http://localhost:8080 scripts/load_test.js

# in another terminal:
kubectl get hpa inventory-app-hpa -n inventory -w
kubectl get pods -n inventory -w
```

We actually ran this against a real minikube cluster rather than just
asserting it works - see
[`docs/load-test-results.md`](docs/load-test-results.md) for what that
run showed (including a real `2 → 4 → 8 → 10` scale-out with the HPA's
own controller log lines), what didn't scale under normal traffic and
why, and a rough edge or two hit along the way.

---

## Running Tests

Tests run against in-memory fakes (mongomock, fakeredis, and a lightweight
Elasticsearch double), so no Docker services are required.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

---

## Observability

- **`GET /health`** - checks Mongo/Elasticsearch/Redis connectivity, returns 503 if any are down. Backs the k8s readiness probe: a pod that can't reach its dependencies stops receiving traffic.
- **`GET /health/live`** - touches no dependency, always 200 if the process is up. Backs the k8s liveness probe, deliberately kept separate from `/health` so a downstream Mongo/ES/Redis outage doesn't cause kubelet to restart otherwise-healthy app pods.
- **`GET /metrics`** - Prometheus text format via `prometheus-flask-exporter`: request rate/latency/error histograms per endpoint, plus a custom `inventory_cache_result_total{result="hit|miss|error"}` counter from `app/services/cache_service.py`. `k8s/base/app/service.yaml` carries the `prometheus.io/scrape` annotations a plain Prometheus needs to find it.
- **`monitoring/grafana-dashboard.json`** - a starter dashboard (request rate, p95 latency, error rate, cache hit ratio, and - if kube-state-metrics is installed - HPA current/desired replicas and per-pod CPU vs. the HPA's target) wired to those metrics.
- **Structured logs** - every response carries an `X-Request-ID` header (generated, or echoed back if the caller supplies one), and every log line - including ones logged deep inside `mongo_service.py`/`es_service.py` - carries that same `request_id`, so a single request can be traced across all three data stores by grepping one ID. See `app/logging_config.py`.

## Security

- **Rate limiting** (`Flask-Limiter`, `app/extensions.py`) - write endpoints are capped (20/min for create/update/delete, 5/min for bulk create). Backed by Redis (`RATELIMIT_STORAGE_URI`) in any real deployment so the limit is shared across replicas, not enforced separately per-pod; defaults to in-memory so local dev/CI never depend on Redis being reachable.
- **API-key auth** (`app/auth.py`) - unset by default (local dev/tests stay frictionless), enabled by setting `API_KEY`. In `k8s/base/app/deployment.yaml` this is wired to a Secret (`k8s/base/app/secret.example.yaml.tpl` is the template - **not applied by default**) via `secretKeyRef` with `optional: true`, so the app runs fine with auth off until that Secret is actually created. When set, mutating requests need an `X-API-Key` header matching it; `GET` endpoints are never gated. The comparison uses `hmac.compare_digest`, not `!=`, so a wrong key can't be narrowed down via response-time differences.
- **`NetworkPolicy`** (`k8s/base/networkpolicy.yaml`) - ingress to Mongo, Elasticsearch, and Redis is restricted to pods labeled `app: inventory-app` only. Effective on any CNI that enforces `NetworkPolicy` (Calico, Cilium - standard on EKS/GKE); confirmed inert (not broken) on minikube's default CNI, which doesn't enforce it at all.
- **Mongo/Redis authentication** - off by default (matching each service's own out-of-the-box behavior), on once `mongodb-credentials`/`redis-credentials` Secrets exist (`k8s/base/mongodb/secret.example.yaml.tpl`, `k8s/base/redis/secret.example.yaml.tpl`). docker-compose runs both with auth enforced unconditionally for local dev (`MONGO_ROOT_PASSWORD`/`REDIS_PASSWORD`, defaulted for zero-setup `docker compose up`, overridable via env). See "Above and beyond" above for exactly how the optional-Secret wiring works and how it was verified.

```bash
curl -X POST $BASE/products -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" -d '...'
```

---

## API Reference

### List all products
```
GET /products
```

### Get a product
```
GET /products/{product_id}
```

### Create a product
```
POST /products
Content-Type: application/json

{
  "product_name": "Mechanical Keyboard",
  "product_category": "Electronics",
  "price": 149.99,
  "available_quantity": 30,
  "description": "TKL mechanical keyboard with Cherry MX switches and RGB backlight."
}
```

### Update a product
```
PUT /products/{product_id}
Content-Type: application/json

{
  "price": 129.99,
  "available_quantity": 25
}
```

### Delete a product
```
DELETE /products/{product_id}
```

`POST`/`PUT`/`DELETE` (and bulk create) are rate-limited and, if `API_KEY`
is configured, require an `X-API-Key` header - see "Security" above.

### Full-text search
```
GET /products/search?query=wireless+headphones
GET /products/search?query=coffee
```
Searches `product_name` and `description` in Elasticsearch (fuzzy matching enabled), then hydrates full documents from MongoDB.

### Analytics
```
GET /products/analytics
```
Returns:
```json
{
  "total_count": 12,
  "most_popular_category": "Electronics",
  "average_price": 81.65
}
```

---

## curl Examples

```bash
BASE=http://localhost:5000

# List all
curl $BASE/products

# Create
curl -X POST $BASE/products \
  -H "Content-Type: application/json" \
  -d '{"product_name":"Widget","product_category":"Tools","price":9.99,"available_quantity":100,"description":"A handy widget for everyday use."}'

# Search
curl "$BASE/products/search?query=laptop"

# Analytics
curl $BASE/products/analytics
```

---

## Path to EKS

The `k8s/` manifests target minikube by default (the `dev` overlay), but
nothing about the app itself is minikube-specific. `terraform/` is an
illustrative (not applied) module showing what actually changes to run
this on a shared EKS cluster instead of a single local node - a 3-AZ VPC,
an EKS cluster with IRSA enabled, ECR in place of building straight into
the cluster's docker daemon, and example IAM-Roles-for-Service-Accounts
for the AWS Load Balancer Controller and a backup job. See
[`terraform/README.md`](terraform/README.md) for what it covers, what it
deliberately leaves out (Karpenter, a managed MongoDB/Elasticsearch
replacement, External Secrets Operator), and why.

---

## Project Structure

```
inventory-system/
├── app/
│   ├── config.py             # Env-based configuration
│   ├── main.py               # Flask app factory
│   ├── auth.py                # X-API-Key enforcement for write endpoints
│   ├── extensions.py          # Shared Flask-Limiter instance
│   ├── logging_config.py      # Structured JSON logs + request-ID propagation
│   ├── models/product.py     # Validation and serialization helpers
│   ├── routes/
│   │   ├── products.py       # CRUD + search endpoints
│   │   ├── analytics.py      # Analytics endpoint
│   │   └── health.py          # /health (readiness) + /health/live (liveness)
│   └── services/
│       ├── mongo_service.py  # MongoDB CRUD + aggregation + index management
│       ├── es_service.py     # Elasticsearch indexing + search
│       └── cache_service.py   # Redis cache wrapper, hit/miss metrics, idempotency-key store
├── k8s/
│   ├── base/                  # StatefulSets (Mongo/ES), Deployments, Services, HPA, PDB,
│   │                          # NetworkPolicy, ConfigMap, reconcile CronJob, Secret templates
│   └── overlays/               # dev (minikube) / staging / prod - see "Environments" above
├── terraform/                  # Illustrative EKS + ECR + IRSA - not applied, see terraform/README.md
├── docs/
│   ├── adr/                     # Architecture decision records
│   └── load-test-results.md    # Real minikube run of the HPA demo below - what scaled, what didn't, why
├── monitoring/                 # Starter Grafana dashboard for the /metrics endpoint
├── scripts/
│   ├── seed_data.py           # Sample data loader
│   ├── reconcile.py            # Mongo/Elasticsearch drift detector + repairer (see "Above and beyond")
│   └── load_test.js            # k6 script for the HPA scaling demo
├── docker-compose.yml         # Local dev stack
├── Dockerfile
└── requirements.txt
```
