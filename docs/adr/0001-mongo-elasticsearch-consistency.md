# ADR 0001: Synchronous dual-write between MongoDB and Elasticsearch

## Status
Accepted, with a known limitation documented below.

## Context

Every product write (create, update, delete) needs to land in two systems:
MongoDB, the source of truth for product data, and Elasticsearch, which
holds a search-optimized projection (`product_id`, `product_name`,
`product_category`, `description`, `price`) used by `GET
/products/search`. The two stores need to stay close enough in sync that a
search result always resolves to a real, current product when hydrated
from Mongo.

## Decision

Writes happen synchronously, in-request, in `app/routes/products.py`:

1. Write to MongoDB first (it's the authoritative store).
2. Index the same document into Elasticsearch.
3. If step 2 fails, roll the Mongo write back (delete on create, restore
   the previous snapshot on update) and return a 500 to the caller.

This means a client never observes a product that exists in Mongo but not
in Elasticsearch (or vice versa) as a *result of a request the API told
them succeeded* — the API only returns 2xx once both stores agree.

## Consequences

**What this buys us:** strong-enough consistency for a single-writer,
single-instance system, with no extra infrastructure (no message broker,
no CDC pipeline) and a failure mode that's easy to reason about — the two
stores are wrong relative to each other only when this specific write was
already reported as failed to the caller.

**What it doesn't cover — the crash window:** if the process is killed
between the Mongo write and the Elasticsearch write (pod eviction, OOM
kill, node failure), or if the rollback call in step 3 itself fails, Mongo
and Elasticsearch are left permanently divergent with **no reconciliation
mechanism**. Nothing today notices or repairs this. At the current scale
(a take-home-sized dataset, one writer at a time) the odds of hitting this
window are low and the blast radius is one product. It would not be an
acceptable risk at production scale with a continuous write volume.

**What it doesn't extend to — multiple writers:** the rollback path has no
distributed coordination. Two app replicas racing to update the same
product (both write to Mongo, both attempt to index, one ES call fails)
have no shared lock, so the "roll back to the pre-write snapshot" step in
one replica can stomp a concurrent, successful write from the other. This
is livable at low write concurrency (product catalog updates are not a
hot path) but wouldn't hold up if writes became frequent or multi-writer.

## What we'd do differently at scale

The standard fix for coupling two independent stores' write paths is to
stop coupling them: decouple the Elasticsearch write from the request path
entirely and drive it from a durable log of what changed in Mongo.

- **MongoDB Change Streams** (or **Debezium** tailing the oplog) watch the
  `products` collection and emit an event on every insert/update/delete.
- An indexer consumer (or a Debezium Elasticsearch sink connector) applies
  those events to the Elasticsearch index asynchronously.
- The API's write path becomes: write to Mongo, return 2xx. No synchronous
  second write, no rollback logic, no crash window between two writes —
  there's only ever one write in the request path.
- Consistency becomes *eventual* instead of "checked at write time": a
  search might lag a write by up to the consumer's processing latency
  (typically sub-second), which is an acceptable tradeoff for a product
  catalog (nobody expects a just-created product to be full-text
  searchable within the same HTTP request).
- This also naturally survives process crashes: the oplog/Debezium offset
  is durable, so a crashed indexer resumes exactly where it left off
  instead of leaving a silently missed write.

We didn't build this here because it adds real infrastructure (Kafka or a
change-stream consumer process, its own deployment/monitoring) that isn't
justified at this project's scale — but it's the first thing to reach for
if this system needed to support real write throughput or multiple app
replicas writing concurrently.
