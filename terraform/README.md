# Terraform: minikube → EKS

This directory is **illustrative infrastructure-as-code**, not part of the
assignment's minikube path and **not applied as part of this submission**.
It exists to answer a question the k8s manifests under `../k8s/` can't
answer on their own: what would actually change to run this on a real,
shared EKS cluster instead of a single-node local one.

Nothing here has been `terraform apply`'d — there's no state file, no
remote backend configured, and no AWS credentials involved in producing
it. Treat it as a design artifact you'd flesh out (state backend, exact
CIDR ranges, node sizing from real usage data) before actually running it
against an AWS account.

## What's here and why

| File | Purpose |
|---|---|
| `vpc.tf` | 3-AZ VPC via `terraform-aws-modules/vpc`, private subnets for nodes/pods, public subnets for the ALB. Multi-AZ is what makes the `topologySpreadConstraints` in `k8s/app/deployment.yaml` meaningful — on minikube's single node they're a no-op. |
| `eks.tf` | EKS cluster via `terraform-aws-modules/eks`, with the `aws-ebs-csi-driver` addon (needed if MongoDB/Elasticsearch stay self-hosted on PVCs — see the note below) and IRSA enabled on the cluster (`enable_irsa = true`). |
| `ecr.tf` | A private ECR repo with scan-on-push, replacing minikube's `imagePullPolicy: Never` + local `docker build` flow. |
| `irsa.tf` | Two example IAM-Roles-for-Service-Accounts: one for the AWS Load Balancer Controller (needed to replace the `NodePort` Service with a real ALB Ingress), one for the app pod itself (example: read-only access to a backup bucket) — showing the pattern rather than every role this cluster would eventually need. |
| `outputs.tf` | `kubectl` / `docker` commands to point at the resulting cluster and registry. |

## What this deliberately does not do

- **Doesn't run MongoDB/Elasticsearch on EKS at all.** The honest
  recommendation (see the main README's "EKS notes" section) is Amazon
  DocumentDB and Amazon OpenSearch Service instead of self-hosted
  StatefulSets — offloading HA, patching, and backups to AWS is the point
  of using managed services, and it's what a platform team would actually
  choose here. The `aws-ebs-csi-driver` addon is included anyway, since
  it's what you'd need if a real MongoDB replica-set deployment (via the
  MongoDB Community Operator) were justified instead — that decision
  depends on requirements this project doesn't have (Mongo-specific
  aggregation features DocumentDB doesn't support, data residency, etc.).
- **Doesn't set up Karpenter or Cluster Autoscaler.** A standard managed
  node group is used instead. Karpenter is the better answer once the HPA
  (`k8s/app/hpa.yaml`) is actually scaling pods under load and node
  capacity becomes the bottleneck — it's worth adding, but it's its own
  IAM role, SQS interruption queue, and Helm release, which is more setup
  than this illustrative module needs to make its point.
- **Doesn't wire up External Secrets Operator.** `irsa.tf` shows the IAM
  side (a role scoped to read from Secrets Manager); actually deploying
  ESO and pointing it at the `API_KEY` used in `k8s/app/deployment.yaml`
  is a Helm release + a couple of CRDs, left as the next step.

## If you actually wanted to run this

```bash
cd terraform
terraform init
terraform plan   # review before ever applying against a real account
terraform apply
aws eks update-kubeconfig --name inventory-eks --region us-east-1
docker build -t <ecr_repository_url>:latest ..
docker push <ecr_repository_url>:latest
# then swap image + imagePullPolicy in k8s/app/deployment.yaml and
# kubectl apply -f k8s/ (minus the imagePullPolicy: Never assumption)
```
