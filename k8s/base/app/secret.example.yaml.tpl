# Template only. The .tpl extension is deliberate: kustomize only applies
# files explicitly listed in a kustomization.yaml's `resources:`, and this
# one isn't, but a plain `kubectl apply -f k8s/base/app/` still picks up
# every *.yaml/*.yml/*.json file in a directory regardless of name - a
# secret.example.yaml here would get applied with the placeholder value
# below as a real Secret. Do not rename this to .yaml without removing it
# from both apply paths.
#
# Do not commit real credentials to this file, or any file, ever. In a real
# deployment this Secret is created out-of-band - e.g.:
#   kubectl create secret generic inventory-app-secrets \
#     --namespace inventory \
#     --from-literal=api-key="$(openssl rand -hex 32)"
# or synced from AWS Secrets Manager via External Secrets Operator / the
# Secrets Store CSI Driver on EKS, rather than hand-created at all.
#
# deployment.yaml references this Secret with `optional: true` on the
# secretKeyRef, so the app runs with write-endpoint auth disabled (the
# default - see app/auth.py) until this Secret actually exists.
apiVersion: v1
kind: Secret
metadata:
  name: inventory-app-secrets
  namespace: inventory
type: Opaque
stringData:
  api-key: "REPLACE_ME"
