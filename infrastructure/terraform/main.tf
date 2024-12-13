# Configure Terraform and required providers
terraform {
  required_version = ">=1.0.0"
  
  # Configure GCS backend for state management
  backend "gcs" {
    bucket = "${var.project_id}-terraform-state"
    prefix = "terraform/state"
  }

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

# Configure Google Cloud provider
provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Local variables for resource naming and tagging
locals {
  name_prefix = "${var.project_id}-${var.environment}"
  common_labels = {
    environment = var.environment
    managed_by  = "terraform"
    project     = var.project_id
  }
}

# Enable required Google Cloud APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "cloudrun.googleapis.com",
    "sql-component.googleapis.com",
    "redis.googleapis.com",
    "vpcaccess.googleapis.com",
    "servicenetworking.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "monitoring.googleapis.com"
  ])
  
  project = var.project_id
  service = each.key

  disable_dependent_services = true
  disable_on_destroy        = false
}

# Deploy networking infrastructure
module "networking" {
  source = "./modules/networking"
  
  project_id      = var.project_id
  region         = var.region
  environment    = var.environment
  name_prefix    = local.name_prefix
  
  depends_on = [
    google_project_service.required_apis
  ]
}

# Deploy Cloud SQL PostgreSQL database
module "database" {
  source = "./modules/database"
  
  project_id          = var.project_id
  region             = var.region
  environment        = var.environment
  name_prefix        = local.name_prefix
  vpc_id             = module.networking.vpc_id
  private_vpc_connection = module.networking.private_vpc_connection
  instance_tier      = var.db_instance_tier
  
  depends_on = [
    module.networking
  ]
}

# Deploy Redis cache
module "cache" {
  source = "./modules/cache"
  
  project_id          = var.project_id
  region             = var.region
  environment        = var.environment
  name_prefix        = local.name_prefix
  vpc_id             = module.networking.vpc_id
  subnet_ids         = module.networking.subnet_ids
  memory_size_gb     = var.redis_memory_size_gb
  
  depends_on = [
    module.networking
  ]
}

# Deploy Cloud Run service
module "compute" {
  source = "./modules/compute"
  
  project_id       = var.project_id
  region          = var.region
  environment     = var.environment
  name_prefix     = local.name_prefix
  vpc_connector   = module.networking.vpc_connector
  
  min_instances   = var.min_instances
  max_instances   = var.max_instances
  cpu            = var.instance_cpu
  memory         = var.instance_memory
  
  database_connection = module.database.connection_name
  redis_host         = module.cache.redis_host
  redis_port         = module.cache.redis_port
  
  depends_on = [
    module.database,
    module.cache
  ]
}

# Output important values for application configuration
output "api_url" {
  description = "The URL of the deployed Cloud Run service"
  value       = module.compute.service_url
}

output "database_connection" {
  description = "Database connection details"
  value       = module.database.connection_name
  sensitive   = true
}

output "redis_connection" {
  description = "Redis connection details"
  value = {
    host = module.cache.redis_host
    port = module.cache.redis_port
  }
  sensitive = true
}

# Create monitoring workspace
resource "google_monitoring_workspace" "workspace" {
  provider     = google-beta
  project      = var.project_id
  display_name = "${local.name_prefix}-monitoring"
  
  depends_on = [
    google_project_service.required_apis
  ]
}

# Configure monitoring alerts (example for CPU utilization)
resource "google_monitoring_alert_policy" "cpu_utilization" {
  provider     = google-beta
  project      = var.project_id
  display_name = "${local.name_prefix}-cpu-utilization"
  
  conditions {
    display_name = "CPU Utilization > 75%"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/container/cpu/utilization\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.75
    }
  }
  
  notification_channels = []  # Add notification channels as needed
  
  depends_on = [
    google_monitoring_workspace.workspace
  ]
}