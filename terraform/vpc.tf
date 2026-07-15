# 3-AZ VPC: private subnets host nodes/pods, public subnets host the ALB
# that replaces the NodePort Service in k8s/app/service.yaml. Multiple AZs
# are what make the pod anti-affinity / topologySpreadConstraints in
# k8s/app/deployment.yaml buy real HA, rather than being a no-op the way
# they are on single-node minikube.
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.8"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr

  azs             = var.azs
  private_subnets = [for i, az in var.azs : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i, az in var.azs : cidrsubnet(var.vpc_cidr, 4, i + 8)]

  enable_nat_gateway   = true
  single_nat_gateway   = true # cost tradeoff for an illustrative module; one NAT GW per AZ removes the single-NAT SPOF in a real deployment
  enable_dns_hostnames = true

  # Required tags for the EKS/AWS Load Balancer Controller to auto-discover
  # subnets when provisioning an ALB from an Ingress resource.
  public_subnet_tags = {
    "kubernetes.io/role/elb"                    = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"           = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}
