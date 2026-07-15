terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Illustrative: state should live in a remote backend (S3 + DynamoDB lock
  # table) shared by whoever operates this, not on a laptop. Left
  # unconfigured here since standing up that bucket/table is itself an
  # apply this module doesn't perform.
  # backend "s3" {
  #   bucket         = "inventory-system-tfstate"
  #   key            = "eks/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "inventory-system-tflock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region
}
