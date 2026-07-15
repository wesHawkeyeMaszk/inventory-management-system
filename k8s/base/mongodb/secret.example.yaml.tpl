# Template only - see k8s/base/app/secret.example.yaml.tpl for why this is
# a .tpl and not a .yaml, and why it's not listed in kustomization.yaml.
#
# Do not commit real credentials to this file, or any file, ever. Create
# out-of-band in a real deployment, e.g.:
#   kubectl create secret generic mongodb-credentials \
#     --namespace inventory \
#     --from-literal=username=inventory-app \
#     --from-literal=password="$(openssl rand -hex 32)"
#
# Referenced with optional: true by both mongodb/statefulset.yaml
# (MONGO_INITDB_ROOT_USERNAME/PASSWORD - what Mongo itself authenticates
# against) and app/deployment.yaml (MONGO_USERNAME/MONGO_PASSWORD - what
# the app authenticates as). Same Secret, two consumers, one place to
# rotate the value. Mongo stays unauthenticated (today's default) until
# this Secret exists.
apiVersion: v1
kind: Secret
metadata:
  name: mongodb-credentials
  namespace: inventory
type: Opaque
stringData:
  username: "REPLACE_ME"
  password: "REPLACE_ME"
