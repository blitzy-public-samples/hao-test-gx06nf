# Required Terraform version constraint
terraform {
  required_version = ">=1.0.0"
}

variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID where networking resources will be deployed"
  
  validation {
    condition     = length(var.project_id) > 0
    error_message = "Project ID must not be empty."
  }
}

variable "region" {
  type        = string
  description = "The Google Cloud region for networking resources"
  default     = "us-central1"
}

variable "environment" {
  type        = string
  description = "The deployment environment (prod/staging)"
  
  validation {
    condition     = contains(["prod", "staging"], var.environment)
    error_message = "Environment must be either 'prod' or 'staging'."
  }
}

variable "vpc_cidr_range" {
  type        = string
  description = "The CIDR range for the VPC network"
  
  validation {
    condition     = can(cidrhost(var.vpc_cidr_range, 0))
    error_message = "VPC CIDR range must be a valid CIDR notation."
  }
}

variable "subnet_cidr_range" {
  type        = string
  description = "The CIDR range for the subnet within VPC"
  
  validation {
    condition     = can(cidrhost(var.subnet_cidr_range, 0))
    error_message = "Subnet CIDR range must be a valid CIDR notation."
  }
}

variable "enable_private_google_access" {
  type        = bool
  description = "Whether to enable private Google access for the subnet"
  default     = true
}