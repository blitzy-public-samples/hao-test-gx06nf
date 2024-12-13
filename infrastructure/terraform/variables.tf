# Core project variables
variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID where resources will be deployed"
  validation {
    condition     = length(var.project_id) > 0
    error_message = "Project ID must not be empty."
  }
}

variable "region" {
  type        = string
  description = "The Google Cloud region for resource deployment"
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

# Database configuration variables
variable "db_instance_tier" {
  type        = string
  description = "The Cloud SQL instance tier (db-custom-2-4096 for production as per spec)"
  validation {
    condition     = can(regex("^db-custom-[0-9]+-[0-9]+$", var.db_instance_tier))
    error_message = "DB instance tier must be in format db-custom-CPU-RAM."
  }
}

# Redis configuration variables
variable "redis_memory_size_gb" {
  type        = number
  description = "Memory size in GB for Redis instance (5GB for production as per spec)"
  validation {
    condition     = var.redis_memory_size_gb >= 1
    error_message = "Redis memory size must be at least 1 GB."
  }
}

# Cloud Run configuration variables
variable "min_instances" {
  type        = number
  description = "Minimum number of Cloud Run instances (1 as per spec)"
  default     = 1
  validation {
    condition     = var.min_instances >= 1
    error_message = "Minimum instances must be at least 1."
  }
}

variable "max_instances" {
  type        = number
  description = "Maximum number of Cloud Run instances (10 as per spec)"
  default     = 10
  validation {
    condition     = var.max_instances >= var.min_instances
    error_message = "Maximum instances must be greater than or equal to minimum instances."
  }
}

variable "instance_cpu" {
  type        = string
  description = "CPU allocation for Cloud Run instances (2 vCPU as per spec)"
  default     = "2000m"
  validation {
    condition     = can(regex("^[0-9]+m$", var.instance_cpu))
    error_message = "CPU must be specified in millicores (e.g., 2000m)."
  }
}

variable "instance_memory" {
  type        = string
  description = "Memory allocation for Cloud Run instances (4GB as per spec)"
  default     = "4Gi"
  validation {
    condition     = can(regex("^[0-9]+Gi$", var.instance_memory))
    error_message = "Memory must be specified in Gi units (e.g., 4Gi)."
  }
}