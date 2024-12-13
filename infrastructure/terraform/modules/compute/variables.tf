# Required project configuration variables
variable "project_id" {
  type        = string
  description = "The GCP project ID where resources will be created"
  
  validation {
    condition     = length(var.project_id) > 0
    error_message = "Project ID must not be empty."
  }
}

variable "region" {
  type        = string
  description = "The GCP region for resource deployment"
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

# Cloud Run service configuration variables
variable "service_name" {
  type        = string
  description = "The name of the Cloud Run service"
  
  validation {
    condition     = length(var.service_name) > 0
    error_message = "Service name must not be empty."
  }
}

variable "container_image" {
  type        = string
  description = "The container image to deploy"
  
  validation {
    condition     = length(var.container_image) > 0
    error_message = "Container image must not be empty."
  }
}

# Autoscaling configuration variables
variable "min_instances" {
  type        = number
  description = "Minimum number of instances"
  default     = 1
  
  validation {
    condition     = var.min_instances >= 1
    error_message = "Minimum instances must be at least 1."
  }
}

variable "max_instances" {
  type        = number
  description = "Maximum number of instances"
  default     = 10
  
  validation {
    condition     = var.max_instances >= var.min_instances
    error_message = "Maximum instances must be greater than or equal to minimum instances."
  }
}

# Resource limits configuration variables
variable "cpu_limit" {
  type        = string
  description = "CPU limit for each instance"
  default     = "2000m"  # 2 vCPU cores
}

variable "memory_limit" {
  type        = string
  description = "Memory limit for each instance"
  default     = "4Gi"    # 4 GB memory
}