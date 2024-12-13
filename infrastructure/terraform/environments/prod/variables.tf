# Production environment-specific variables for GCP infrastructure deployment
# Terraform version requirement: >= 1.0.0

# Environment identifier variable with strict production enforcement
variable "environment" {
  type        = string
  description = "Production environment identifier - strictly enforced to be 'prod'"
  default     = "prod"
  validation {
    condition     = var.environment == "prod"
    error_message = "Environment must be 'prod' for production environment to ensure proper resource configuration"
  }
}

# Database instance configuration for high-performance production workload
variable "db_instance_tier" {
  type        = string
  description = "Cloud SQL instance tier for production - configured for 5,000 transactions/s with 2 vCPU and 4GB RAM"
  default     = "db-custom-2-4096"
  validation {
    condition     = can(regex("^db-custom-[0-9]+-[0-9]+$", var.db_instance_tier))
    error_message = "Instance tier must be a valid Cloud SQL custom machine type for production workload"
  }
}

# Redis cache configuration for high-throughput caching
variable "redis_memory_size_gb" {
  type        = number
  description = "Memory size in GB for Redis instance in production - minimum 5GB to support 100,000 ops/s"
  default     = 5
  validation {
    condition     = var.redis_memory_size_gb >= 5
    error_message = "Production Redis memory size must be at least 5 GB to handle cache operation requirements"
  }
}

# Cloud Run instance scaling configuration for production load
variable "min_instances" {
  type        = number
  description = "Minimum number of Cloud Run instances for production - ensures high availability with at least 2 instances"
  default     = 2
  validation {
    condition     = var.min_instances >= 2
    error_message = "Production environment must have at least 2 minimum instances for high availability"
  }
}

variable "max_instances" {
  type        = number
  description = "Maximum number of Cloud Run instances for production - supports up to 10 instances for 10,000 req/s throughput"
  default     = 10
  validation {
    condition     = var.max_instances >= var.min_instances && var.max_instances <= 10
    error_message = "Maximum instances must be between min_instances and 10 to maintain cost control while meeting performance requirements"
  }
}

# Instance resource allocation variables for production performance
variable "instance_cpu" {
  type        = string
  description = "CPU allocation for Cloud Run instances in production - 2 vCPU to handle 1,000 req/s per instance"
  default     = "2000m"
  validation {
    condition     = can(regex("^2000m$", var.instance_cpu))
    error_message = "Production CPU allocation must be exactly 2000m (2 vCPU) to meet performance requirements"
  }
}

variable "instance_memory" {
  type        = string
  description = "Memory allocation for Cloud Run instances in production - 4GB for optimal performance"
  default     = "4Gi"
  validation {
    condition     = can(regex("^4Gi$", var.instance_memory))
    error_message = "Production memory allocation must be exactly 4Gi to meet performance requirements"
  }
}

# Reference to core project variables
variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID for production environment"
  validation {
    condition     = length(var.project_id) > 0
    error_message = "Project ID must not be empty for production deployment"
  }
}

variable "region" {
  type        = string
  description = "The Google Cloud region for production deployment"
  default     = "us-central1"
  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]$", var.region))
    error_message = "Region must be a valid Google Cloud region identifier"
  }
}