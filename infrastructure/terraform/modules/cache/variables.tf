# Project configuration
variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID where the Redis instance will be deployed"

  validation {
    condition     = length(var.project_id) > 0
    error_message = "Project ID must not be empty."
  }
}

# Region configuration
variable "region" {
  type        = string
  description = "The Google Cloud region for Redis instance deployment"
  default     = "us-central1"
}

# Environment configuration
variable "environment" {
  type        = string
  description = "The deployment environment (prod/staging)"

  validation {
    condition     = contains(["prod", "staging"], var.environment)
    error_message = "Environment must be either 'prod' or 'staging'."
  }
}

# Redis instance configuration
variable "memory_size_gb" {
  type        = number
  description = "Memory size in GB for Redis instance"
  default     = 5 # As per technical specification section 8.2

  validation {
    condition     = var.memory_size_gb >= 1
    error_message = "Memory size must be at least 1 GB."
  }
}

variable "redis_version" {
  type        = string
  description = "Redis version to use for the instance"
  default     = "REDIS_6_X" # As per technical specification section 8.2

  validation {
    condition     = contains(["REDIS_6_X"], var.redis_version)
    error_message = "Redis version must be REDIS_6_X as per specification."
  }
}

variable "tier" {
  type        = string
  description = "Service tier for Redis instance (BASIC or STANDARD_HA)"
  default     = "STANDARD_HA" # High availability mode as per technical specification

  validation {
    condition     = contains(["BASIC", "STANDARD_HA"], var.tier)
    error_message = "Tier must be either BASIC or STANDARD_HA."
  }
}