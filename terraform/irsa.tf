# Two example IAM-Roles-for-Service-Accounts, showing the pattern rather
# than every role a fully-built-out cluster would need.

# 1. AWS Load Balancer Controller - required to replace the NodePort
#    Service (k8s/app/service.yaml) with a real ALB provisioned from a k8s
#    Ingress resource once this runs on EKS instead of minikube.
module "load_balancer_controller_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.39"

  role_name = "${var.cluster_name}-alb-controller"

  attach_load_balancer_controller_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }
}

# 2. Backup role - scoped read/write to a single S3 bucket, for whatever
# takes on MongoDB/Elasticsearch backups (e.g. Velero, or a scheduled
# mongodump CronJob). Neither k8s/ nor this module currently runs a backup
# job; this role exists so adding one later is an IAM no-op, and to make
# the "there is currently no backup/restore strategy" gap concrete instead
# of just a line in a README.
resource "aws_s3_bucket" "backups" {
  bucket = "${var.cluster_name}-backups"
}

resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

data "aws_iam_policy_document" "backup_bucket_access" {
  statement {
    actions   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:DeleteObject"]
    resources = [aws_s3_bucket.backups.arn, "${aws_s3_bucket.backups.arn}/*"]
  }
}

module "backup_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.39"

  role_name = "${var.cluster_name}-backup"

  role_policy_arns = {
    backup_bucket = aws_iam_policy.backup_bucket_access.arn
  }

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["inventory:backup"]
    }
  }
}

resource "aws_iam_policy" "backup_bucket_access" {
  name   = "${var.cluster_name}-backup-bucket-access"
  policy = data.aws_iam_policy_document.backup_bucket_access.json
}
