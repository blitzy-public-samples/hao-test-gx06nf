# Production environment Terraform configuration for Flask REST API backend
# Terraform version requirement and backend configuration
terraform {
  required_version = ">=1.0.0"
  
  # GCS backend for production state with versioning
  backend "gcs" {
    bucket = "${var.project_id}-tfstate"
    prefix = "prod"
  }

  # Required providers with strict version constraints
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 4.0"
    }
  }
}

# Production environment local variables
locals {
  environment = "prod"
  common_labels = {
    environment  = "prod"
    managed_by   = "terraform"
    criticality  = "high"
    compliance   = "required"
    last_updated = formatdate("YYYY-MM-DD", timestamp())
  }
}

# Google Cloud provider configuration for production
provider "google" {
  project = var.project_id
  region  = var.region
  
  # Enable user project override for shared VPC and organization policies
  user_project_override = true
}

# Google Cloud Beta provider for preview features
provider "google-beta" {
  project = var.project_id
  region  = var.region
  user_project_override = true
}

# Root module instantiation with production-grade configurations
module "root" {
  source = "../../"

  # Core variables
  project_id = var.project_id
  region     = var.region
  environment = local.environment

  # Database configuration for high performance
  db_tier = var.db_tier
  redis_memory_size_gb = var.redis_memory_size_gb

  # Cloud Run autoscaling for production load
  min_instances = var.min_instances
  max_instances = var.max_instances

  # Common labels for resource management
  labels = local.common_labels

  # Production-specific security features
  enable_vpc_sc        = true  # Enable VPC Service Controls
  enable_cloud_armor   = true  # Enable Cloud Armor protection
  enable_audit_logs    = true  # Enable detailed audit logging
  enable_private_access = true # Enable private Google Access

  # High availability and backup configurations
  backup_retention_days = 30
  high_availability    = true
  maintenance_window = {
    day  = "sunday"
    hour = 2  # 2 AM maintenance window
  }
}

# Production API endpoint output
output "api_url" {
  description = "Production API endpoint URL"
  value       = module.root.cloud_run_url
  sensitive   = false
}

# Production database connection output
output "database_connection" {
  description = "Production database connection string"
  value       = module.root.database_connection
  sensitive   = true
}

# Production Redis connection output
output "redis_connection" {
  description = "Production Redis connection details"
  value = {
    host = module.root.redis_host
    port = module.root.redis_port
  }
  sensitive = true
}

# Production load balancer IP output
output "load_balancer_ip" {
  description = "Production load balancer IP address"
  value       = module.root.load_balancer_ip
  sensitive   = false
}

# Production VPC network details output
output "network_details" {
  description = "Production VPC network configuration"
  value = {
    network_name    = module.root.vpc_network_name
    subnet_name     = module.root.vpc_subnet_name
    ip_range_services = module.root.ip_range_services
  }
  sensitive = false
}

# Production security configuration output
output "security_config" {
  description = "Production security configuration status"
  value = {
    vpc_sc_enabled     = true
    cloud_armor_enabled = true
    private_access     = true
    audit_logs_enabled = true
  }
  sensitive = false
}