module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Needed for the IAM-Roles-for-Service-Accounts pattern in irsa.tf - lets
  # a k8s ServiceAccount assume a scoped IAM role instead of the whole node
  # sharing one broad instance-profile role.
  enable_irsa = true

  cluster_addons = {
    coredns    = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni    = { most_recent = true }
    # Only needed if a stateful store (e.g. a real MongoDB replica set via
    # the MongoDB Community Operator) runs self-hosted on EKS instead of a
    # managed service - see terraform/README.md for why DocumentDB /
    # OpenSearch Service is the default recommendation instead.
    aws-ebs-csi-driver = { most_recent = true }
  }

  eks_managed_node_groups = {
    default = {
      instance_types = var.node_instance_types
      min_size       = var.node_group_min_size
      max_size       = var.node_group_max_size
      desired_size   = var.node_group_desired_size

      # Standard managed node group here rather than Karpenter - see
      # terraform/README.md "What this deliberately does not do".
      subnet_ids = module.vpc.private_subnets
    }
  }

  tags = {
    Project = "inventory-management-system"
  }
}
