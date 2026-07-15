# Replaces minikube's "build straight into the cluster's docker daemon,
# imagePullPolicy: Never" flow (see k8s/app/deployment.yaml comment) - on
# EKS, nodes pull from a real registry.
resource "aws_ecr_repository" "inventory_app" {
  name                 = "inventory-app"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true # defense-in-depth alongside the Trivy scan already in .github/workflows/security-scan.yml
  }
}

resource "aws_ecr_lifecycle_policy" "inventory_app" {
  repository = aws_ecr_repository.inventory_app.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images after 14 days"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 14
      }
      action = { type = "expire" }
    }]
  })
}
