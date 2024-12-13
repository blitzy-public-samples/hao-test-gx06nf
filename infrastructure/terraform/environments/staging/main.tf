# Terraform configuration for staging environment
# Version: 1.0.0
# Provider Requirements:
# - terraform >= 1.0.0
# - google ~> 4.0
# - google-beta ~> 4.0

terraform {
  required_version = ">=1.0.0"
  
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

  backend "gcs" {
    bucket = "flask-api-staging-tfstate"
    prefix = "terraform/state"
  }
}

# Provider Configuration
provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Local Variables
locals {
  environment = "staging"
  labels = {
    environment = local.environment
    managed_by  = "terraform"
    project     = var.project_id
  }
}

# Network Infrastructure
module "networking" {
  source = "../../modules/networking"

  project_id  = var.project_id
  environment = local.environment
  region      = var.region

  # Staging-specific network configuration
  network_name = "staging-vpc"
  subnet_cidr  = "10.10.0.0/20"
}

# Database Infrastructure
module "database" {
  source = "../../modules/database"

  project_id      = var.project_id
  environment     = local.environment
  region         = var.region
  network_id     = module.networking.vpc_id

  # Staging-specific database configuration
  instance_tier   = var.db_instance_tier
  database_name   = "flask_api_staging"
  user_name       = "flask_api_user"
  
  backup_configuration = {
    enabled                        = true
    start_time                    = "02:00"
    point_in_time_recovery_enabled = false
    retention_days                = 7
  }

  depends_on = [module.networking]
}

# Redis Cache Infrastructure
module "cache" {
  source = "../../modules/cache"

  project_id         = var.project_id
  environment        = local.environment
  region            = var.region
  network_id        = module.networking.vpc_id
  
  # Staging-specific Redis configuration
  memory_size_gb     = var.redis_memory_size_gb
  redis_version      = "REDIS_6_X"
  authorized_network = module.networking.vpc_id

  depends_on = [module.networking]
}

# Compute Infrastructure (Cloud Run)
module "compute" {
  source = "../../modules/compute"

  project_id     = var.project_id
  environment    = local.environment
  region        = var.region
  
  # Staging-specific Cloud Run configuration
  service_name   = "flask-api-staging"
  container_image = "gcr.io/${var.project_id}/api:latest"
  
  scaling_configuration = {
    min_instances = var.min_instances
    max_instances = var.max_instances
  }

  resources = {
    cpu    = "2"
    memory = "4Gi"
  }

  environment_variables = {
    ENVIRONMENT        = local.environment
    DATABASE_HOST     = module.database.connection_name
    REDIS_HOST        = module.cache.redis_host
    REDIS_PORT        = module.cache.redis_port
  }

  depends_on = [
    module.networking,
    module.database,
    module.cache
  ]
}

# Outputs
output "api_url" {
  description = "The URL of the deployed Cloud Run service in staging"
  value       = module.compute.service_url
}

output "database_connection" {
  description = "The connection string for the staging database"
  value       = module.database.connection_name
  sensitive   = true
}

output "redis_connection" {
  description = "Redis connection details for staging environment"
  value = {
    host = module.cache.redis_host
    port = module.cache.redis_port
  }
  sensitive = true
}