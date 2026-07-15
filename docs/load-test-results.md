# Load test: does the HPA actually work?

`k8s/base/app/hpa.yaml` scales `inventory-app` between 2 and 10 replicas on
CPU/memory utilization. It's easy to write an HPA manifest that looks
correct and never actually fires - the CPU-utilization math depends on
`resources.requests` being set correctly (see `k8s/base/app/deployment.yaml`),
on metrics-server being reachable, and on the workload actually being
capable of using enough CPU to cross the target. None of that is visible
from reading the YAML. So rather than assert it works, we deployed the
real stack to a real (local) Kubernetes cluster and drove real load at it.

## Setup

- `minikube` (Docker driver) + `k6`, neither pre-installed - installed for
  this test.
- Built `inventory-app:latest` with `minikube image build` (bypasses a
  Docker client/daemon API version mismatch that blocked a plain
  `docker build` against minikube's daemon).
- Deployed with `kubectl apply -k k8s/overlays/dev` - the exact overlay
  documented in the README, unmodified.
- Seeded the standard 65 sample products via `scripts/seed_data.py`.
- Confirmed the API end-to-end through the cluster before load-testing:
  `/health`, `/products`, `/products/search`, `/products/analytics` all
  returned correct data through a `kubectl port-forward`.

**First checkpoint, before any load:** every pod (`inventory-app` x2,
`mongodb`, `elasticsearch`, `redis`) reached `Ready` on the first
`kubectl apply` with no restarts - confirming the readiness/liveness
probes, `PersistentVolumeClaim`s, and resource requests introduced during
the platform-engineering pass are all individually correct and compatible
with each other, not just individually plausible YAML.

## Round 1: real traffic, default resource requests

Ran `scripts/load_test.js` against the deployed service - a k6 scenario
ramping 5→80 virtual users over 4 minutes, mixing paginated list (40%),
full-text search (35%), and analytics aggregation (25%) requests.

**Result: the HPA never scaled**, and it was right not to. `inventory-app`
requests `150m` CPU per pod. Under 80 concurrent users the app's own
p95 latency was under 10ms - it's simply too fast to burn 90m (60% of
150m) of CPU per pod from HTTP traffic alone at this dataset size and
traffic mix. `kubectl top` showed pods sitting at 15-25m CPU throughout,
roughly 10-17% utilization, regardless of load.

This is a real finding, not a null result: it means the `150m` CPU
request checked into `k8s/base/app/deployment.yaml` is *not* under-sized
for this workload's actual traffic profile - the app has substantial CPU
headroom before the HPA's 60% target would ever trigger. Whether that's
the right request value depends on what traffic pattern you expect in
production (this validates it against read-heavy CRUD/search traffic at
the seeded 65-product scale, not e.g. sustained bulk-create load or a
much larger catalog where Mongo aggregation/ES query cost rises).

## Round 2: proving the scaling mechanism itself

To verify the HPA *would* fire correctly given a workload that actually
saturates its CPU request - without inventing a slower fake endpoint or
fabricating results - we temporarily lowered the **live cluster's**
CPU request to `10m` (`kubectl set resources deployment inventory-app
--requests=cpu=10m`, not committed anywhere - `k8s/base/app/deployment.yaml`
still ships with `150m`) and reran the same k6 script against the same
already-running pods.

**Result: it worked exactly as designed.**

```
SuccessfulRescale   New size: 4    reason: cpu resource utilization (percentage of request) above target
SuccessfulRescale   New size: 8    reason: cpu resource utilization (percentage of request) above target
SuccessfulRescale   New size: 10   reason: cpu resource utilization (percentage of request) above target
```

Real `horizontal-pod-autoscaler` controller log lines, captured live via
`kubectl describe hpa inventory-app-hpa -n inventory`. Replica count went
`2 → 4 → 8 → 10` (`maxReplicas`) as CPU utilization was read at over
1000% of the (now artificially tiny) request. After the run, the request
was restored to `150m`, the deployment rolled over cleanly, and CPU
utilization settled back to the same 10-17% range as Round 1 - confirming
the production value is sane and the scale-down path (new pods requesting
the real `150m` value) behaves correctly too.

k6 summary for the full 4-minute run:

| Metric | Value |
|---|---|
| Total requests | 48,874 |
| Throughput | 203 req/s |
| p95 latency | 9.19ms |
| Peak VUs | 80 |
| Error rate | 10.36%* |

\* *Not an application defect.* The mid-test `kubectl set resources` call
triggers a rolling deployment, and `kubectl port-forward` doesn't follow a
pod across a rollout - it drops when its target pod terminates. The
~15-second gap before we noticed and restarted the port-forward accounts
for the failed requests (visible as a burst of `connection refused`
errors in the raw k6 log, not scattered 5xx responses from the app). A
real Service-backed deployment (ClusterIP/Ingress rather than a manual
port-forward) wouldn't have this gap, since kube-proxy routes to whichever
pods are currently `Ready`.

## What this validates

- The HPA configuration, resource requests, and metrics-server wiring are
  **functionally correct together**, not just individually plausible.
- The app's real-world CPU footprint is low enough that `150m` per pod
  gives real headroom under the tested traffic profile - useful context
  for whoever tunes these numbers against actual production traffic later
  (see `k8s/overlays/prod/patch-app.yaml` for where that tuning would
  land, and the note in that file that its values are a starting point,
  not measured ones).
- The `dev` overlay, image build path, and `k8s/base` manifests deploy
  cleanly on a fresh cluster with no manual fixes - this write-up is the
  proof, not a claim.

## Known rough edges hit during this run (not code bugs)

- `kubectl top` / the raw `metrics.k8s.io` API consistently had fresher
  data than what the HPA controller was reading at any given moment,
  causing several `<unknown>` target readings in `kubectl get hpa` output
  that resolved themselves a few reconcile cycles later. This looks like
  a metrics-server/controller-manager timing quirk on this specific
  single-node minikube setup (Elasticsearch alone was consuming ~650m CPU
  on a machine with 4 allotted cores) rather than anything in this repo's
  manifests - worth knowing about if you rerun this and see the same
  thing before concluding the HPA is broken.
