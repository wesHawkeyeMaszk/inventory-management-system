// k6 load test for demonstrating HPA scale-out on the inventory-app
// Deployment (see k8s/app/hpa.yaml, target: 60% CPU / 80% memory).
//
// Usage:
//   brew install k6                     # or see https://k6.io/docs/get-started/installation/
//   k6 run scripts/load_test.js
//   k6 run -e BASE_URL=http://localhost:8080 scripts/load_test.js
//
// To watch the HPA react while this runs, in another terminal:
//   kubectl get hpa inventory-app-hpa -n inventory -w
//   kubectl get pods -n inventory -w
//
// If running against minikube, port-forward the app service first:
//   kubectl port-forward svc/inventory-app 8080:80 -n inventory
//   k6 run -e BASE_URL=http://localhost:8080 scripts/load_test.js
//
// The traffic mix below deliberately favours read endpoints
// (list/get/search/analytics) that exercise Mongo aggregation and
// Elasticsearch queries, since those are the CPU-bound paths the HPA is
// meant to react to - a pure write-heavy test would mutate the seeded
// data on every iteration instead of representatively loading the app.

import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:5000";

export const options = {
  scenarios: {
    ramp_to_trigger_hpa: {
      executor: "ramping-vus",
      startVUs: 5,
      stages: [
        { duration: "30s", target: 40 },  // ramp up
        { duration: "3m", target: 80 },   // sustain enough load to push CPU past the 60% HPA target
        { duration: "30s", target: 0 },   // ramp down and watch the HPA scale back in
      ],
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<2000"],
  },
};

const SEARCH_TERMS = ["laptop", "coffee", "wool", "wireless", "desk", "wrench", "yoga", "candle"];
const CATEGORIES = ["Electronics", "Clothing", "Books", "Food", "Tools", "Home", "Sports"];

export default function () {
  const roll = Math.random();

  if (roll < 0.4) {
    // Paginated list with sorting - exercises Mongo find().sort().skip().limit()
    const page = 1 + Math.floor(Math.random() * 3);
    const res = http.get(`${BASE_URL}/products?page=${page}&limit=20&sort=price&order=desc`);
    check(res, { "list status 200": (r) => r.status === 200 });
  } else if (roll < 0.75) {
    // Full-text search - exercises Elasticsearch multi_match + Mongo hydration
    const term = SEARCH_TERMS[Math.floor(Math.random() * SEARCH_TERMS.length)];
    const category = CATEGORIES[Math.floor(Math.random() * CATEGORIES.length)];
    const res = http.get(`${BASE_URL}/products/search?query=${term}&category=${category}`);
    check(res, { "search status 200": (r) => r.status === 200 });
  } else {
    // Analytics aggregation - exercises Mongo $group/$avg pipelines
    const res = http.get(`${BASE_URL}/products/analytics`);
    check(res, { "analytics status 200": (r) => r.status === 200 });
  }

  sleep(Math.random() * 0.5);
}
