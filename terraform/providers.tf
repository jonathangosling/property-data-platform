terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # Values supplied via -backend-config flags in CI and locally.
    # Uses the shared state bucket (key: property-data-platform/terraform.tfstate).
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "property-data-platform"
      Repo      = "jonathangosling/property-data-platform"
      ManagedBy = "terraform"
    }
  }
}
