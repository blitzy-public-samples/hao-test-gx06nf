# Terraform variables for staging environment configuration
# Version: 1.0.0
# Provider Requirements:
# - terraform >= 1.0.0

# Project Configuration
variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID for staging environment deployment"
  default     = "flask-api-staging"

  validation {
    condition     = length(var.project_id) > 0 && can(regex("^[a-z][a-z0-9-]*[a-z0-9]$", var.project_id))
    error_message = "Project ID must be non-empty and match GCP naming conventions."
  }
}

# Regional Configuration
variable "region" {
  type        = string
  description = "The Google Cloud region for staging deployment with reduced latency"
  default     = "us-central1"
}

# Database Configuration
variable "db_instance_tier" {
  type        = string
  description = "The Cloud SQL instance tier optimized for staging workload and cost"
  default     = "db-f1-micro"

  validation {
    condition     = can(regex("^db-.*", var.db_instance_tier))
    error_message = "Database instance tier must be a valid Cloud SQL tier name."
  }
}

# Redis Cache Configuration
variable "redis_memory_size_gb" {
  type        = number
  description = "Memory size in GB for Redis instance in staging environment"
  default     = 2

  validation {
    condition     = var.redis_memory_size_gb >= 1 && var.redis_memory_size_gb <= 4
    error_message = "Redis memory size must be between 1 and 4 GB for staging environment."
  }
}

# Cloud Run Scaling Configuration
variable "min_instances" {
  type        = number
  description = "Minimum number of Cloud Run instances for staging environment"
  default     = 1

  validation {
    condition     = var.min_instances >= 1 && var.min_instances <= 2
    error_message = "Minimum instances must be between 1 and 2 for staging environment."
  }
}

variable "max_instances" {
  type        = number
  description = "Maximum number of Cloud Run instances for staging environment"
  default     = 5

  validation {
    condition     = var.max_instances >= var.min_instances && var.max_instances <= 5
    error_message = "Maximum instances must be between minimum instances and 5 for staging environment."
  }
}