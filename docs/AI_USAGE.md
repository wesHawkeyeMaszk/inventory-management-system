# How AI was used on this project

This project was built with Claude Code throughout - initial implementation,
a structured design review against the assignment requirements, the
resulting hardening pass, and the cleanup at the end. This doc is about
*how*, not just *that*, since that's what the assignment says it's actually
evaluating.

## Review, then fix, then verify - not just "generate code"

The most useful pattern wasn't asking for code, it was asking for a
critical review first: given the finished base implementation, what
would a principal-level reviewer flag in the MongoDB schema, the CRUD
routes, and the overall architecture? That produced a ranked list -
missing indexes, a category-matching inconsistency between MongoDB's
analytics aggregation and Elasticsearch's search filter, an unauthenticated
data layer, no reconciliation path for the documented Mongo/Elasticsearch
consistency tradeoff, and several smaller correctness gaps (a `PUT` that
silently accepted negative prices that `POST` rejected, a non-constant-time
API key comparison).

Only after that review did implementation happen, one item at a time,
each with a test that would fail without the fix.

## Verifying against real infrastructure, not just mocked tests

The test suite runs against in-memory fakes (`mongomock`, `fakeredis`, a
hand-rolled Elasticsearch double) so it's fast enough to run constantly.
But mocked tests passing was treated as necessary, not sufficient: every
fix that touched Mongo, Elasticsearch, Redis, or Kubernetes was also
re-verified against a real `docker-compose` stack, and the Kubernetes
changes specifically (StatefulSet conversion, NetworkPolicy, Secret-gated
auth, the reconciliation CronJob) were deployed to a real minikube
cluster and exercised there.

That discipline caught a real bug the mocked suite structurally could
not have: the first version of the drift-reconciliation `CronJob` didn't
have Mongo credentials wired into its pod spec. It passed the entire
mocked test suite, because nothing in that suite talks to a real,
auth-enforcing Mongo. Running it for real against the newly-authenticated
minikube cluster failed immediately and unambiguously. The fix, and the
fact that it was needed at all, is left in the git history and called
out in `README.md`'s "Known limitations" section rather than quietly
squashed away - it's a more honest demonstration of the verification
process than a clean run would have been.

## Deciding what *not* to build

Asked directly "is there a good reason not to implement the rest of
this," the honest answer was mixed, and that self-audit is preserved in
the conversation history and reflected in the repo: some deferrals held
up (`PUT` keeping partial-update semantics because the assignment's
route spec doesn't imply full-replace; storing `price` as a 64-bit float
rather than `Decimal128` because that's a real cross-cutting migration,
not a contained fix). Others didn't - "no live cluster to verify auth
against" wasn't true once docker-compose was already being used to
verify other changes in the same session, so Mongo/Redis authentication
got implemented and verified rather than left as a documented gap.

The result is `README.md`'s "Above and beyond" and "Known limitations"
sections: a record of what was built and verified, and what was
deliberately left out with a real reason, rather than either an
unreviewed AI-generated feature dump or a hand-wave of "future work."
