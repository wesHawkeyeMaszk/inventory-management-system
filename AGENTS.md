# Agent guidance for this repo

Quick orientation for an AI coding agent working in this codebase. This
file is deliberately short and tool-agnostic (see `CLAUDE.md` for the
Claude Code entry point) - it doesn't duplicate `README.md`, which has
the full architecture, setup, and API reference.

## Fast feedback loop

The test suite runs against in-memory fakes, not live services - no
Docker required:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q        # ~3.5s, 83+ tests
flake8 app/ scripts/ tests/ --max-line-length=120 --extend-ignore=E203,W503
```

`tests/fakes.py` already has a `FakeElasticsearch`; `tests/conftest.py`
wires `mongomock` and `fakeredis` into every test via monkeypatched
`_get_db`/`_get_client` functions in each `app/services/*.py` module.
Use these instead of reaching for `unittest.mock` on Mongo/ES/Redis calls
- the fakes implement enough real query semantics to catch actual bugs,
not just verify a call happened.

Frontend: `cd frontend && npm run lint && npm run format:check && npm run build`.

## Before treating something as a bug, check `docs/adr/`

Some things that look like oversights are documented, deliberate
tradeoffs. In particular, `docs/adr/0001-mongo-elasticsearch-consistency.md`
explains why Mongo/Elasticsearch writes are synchronous and coupled in
the request path, and what its known failure window is - don't "fix"
this into something else without reading that first. If you make a
similarly deliberate tradeoff, write it up the same way rather than
leaving it as an unexplained choice.

## Verification discipline

Mocked tests passing is necessary, not sufficient - treat it that way
before calling non-trivial infra changes done. This codebase has a
documented case of a mocked test suite missing a real bug (a k8s CronJob
shipped without the credentials it needed, only caught by running it
against a live, auth-enabled Mongo on minikube) - see the "Known
limitations" section of `README.md` for the full story. For changes that
touch Mongo/Elasticsearch/Redis auth, indexes, or Kubernetes manifests,
verify against `docker-compose up` and/or a real cluster
(`kubectl kustomize k8s/overlays/dev` at minimum to confirm the manifests
render) before considering the change verified.

## Conventions worth knowing

- **Secrets**: `k8s/base/**/secret.example.yaml.tpl` files are templates
  only, deliberately excluded from `kustomization.yaml` `resources:` so
  `kubectl apply -k` never applies a placeholder credential. Real
  deployments create the Secret out-of-band. Every credential-gated
  feature (`API_KEY`, Mongo/Redis auth) uses `optional: true` on its
  `secretKeyRef` so the feature is off, not broken, when the Secret is
  absent.
- **Two living README sections**: "Above and beyond the assignment's
  minimum" and "Known limitations / what we'd do at production scale."
  If you add or remove meaningful scope, update whichever section
  applies rather than letting them drift from what's actually true.
- **Commit messages**: this repo uses `semantic-release` with
  Conventional Commits (`feat:`, `fix:`, `chore:`, etc. - see
  `.releaserc.json`) to drive `CHANGELOG.md` and version tags on `main`.
