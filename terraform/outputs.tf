output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "ecr_repository_url" {
  value = aws_ecr_repository.inventory_app.repository_url
}

output "configure_kubectl" {
  description = "Run this to point kubectl at the new cluster."
  value       = "aws eks update-kubeconfig --name ${var.cluster_name} --region ${var.aws_region}"
}

output "docker_push_commands" {
  description = "Build and push the app image to ECR instead of building it into minikube's local daemon."
  value = join("\n", [
    "aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${aws_ecr_repository.inventory_app.repository_url}",
    "docker build -t ${aws_ecr_repository.inventory_app.repository_url}:latest ..",
    "docker push ${aws_ecr_repository.inventory_app.repository_url}:latest",
  ])
}
