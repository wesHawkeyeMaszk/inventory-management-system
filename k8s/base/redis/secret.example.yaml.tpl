# Template only - see k8s/base/app/secret.example.yaml.tpl for why this is
# a .tpl and not a .yaml, and why it's not listed in kustomization.yaml.
#
# Do not commit real credentials to this file, or any file, ever. Create
# out-of-band in a real deployment, e.g.:
#   kubectl create secret generic redis-credentials \
#     --namespace inventory \
#     --from-literal=password="$(openssl rand -hex 32)"
#
# Referenced with optional: true by both redis/deployment.yaml (turns on
# `redis-server --requirepass` via a shell-conditional command - see the
# comment there) and app/deployment.yaml (REDIS_PASSWORD - what the app
# and the rate limiter's Redis-backed storage authenticate as). Same
# Secret, three consumers, one place to rotate the value. Redis stays
# unauthenticated (today's default) until this Secret exists.
apiVersion: v1
kind: Secret
metadata:
  name: redis-credentials
  namespace: inventory
type: Opaque
stringData:
  password: "REPLACE_ME"
