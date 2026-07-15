variable "aws_region" {
  description = "AWS region to provision into."
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "EKS cluster name."
  type        = string
  default     = "inventory-eks"
}

variable "cluster_version" {
  description = "Kubernetes version for the EKS control plane."
  type        = string
  default     = "1.29"
}

variable "vpc_cidr" {
  description = "CIDR block for the cluster VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "azs" {
  description = "Availability zones to spread subnets/nodes across - matches the topologySpreadConstraints in k8s/app/deployment.yaml."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "node_instance_types" {
  description = "Instance types for the default managed node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_group_min_size" {
  type    = number
  default = 3
}

variable "node_group_max_size" {
  description = "Ceiling for the managed node group. Should comfortably exceed the app HPA's maxReplicas (10) worth of pods once mongodb/elasticsearch/redis pod capacity is accounted for too."
  type        = number
  default     = 6
}

variable "node_group_desired_size" {
  type    = number
  default = 3
}
