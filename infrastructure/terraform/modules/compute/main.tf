# Required providers configuration
terraform {
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

# Input variables
variable "project_id" {
  description = "The GCP project ID where resources will be created"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Project ID must be a valid GCP project ID."
  }
}

variable "region" {
  description = "The GCP region for resource deployment"
  type        = string

  validation {
    condition     = can(regex("^[a-z]+-[a-z]+-[1-9][0-9]*$", var.region))
    error_message = "Region must be a valid GCP region."
  }
}

variable "environment" {
  description = "The deployment environment (prod/staging)"
  type        = string

  validation {
    condition     = contains(["prod", "staging"], var.environment)
    error_message = "Environment must be either 'prod' or 'staging'."
  }
}

variable "service_name" {
  description = "The name of the Cloud Run service"
  type        = string

  validation {
    condition     = can(regex("^[a-z][-a-z0-9]*[a-z0-9]$", var.service_name))
    error_message = "Service name must match pattern ^[a-z][-a-z0-9]*[a-z0-9]$"
  }
}

variable "container_image" {
  description = "The container image to deploy"
  type        = string

  validation {
    condition     = length(var.container_image) > 0
    error_message = "Container image URL must not be empty."
  }
}

variable "min_instances" {
  description = "Minimum number of instances for autoscaling"
  type        = number
  default     = 1

  validation {
    condition     = var.min_instances >= 0
    error_message = "Minimum instances must be greater than or equal to 0."
  }
}

variable "max_instances" {
  description = "Maximum number of instances for autoscaling"
  type        = number
  default     = 10

  validation {
    condition     = var.max_instances > 0
    error_message = "Maximum instances must be greater than 0."
  }
}

variable "cpu_limit" {
  description = "CPU limit for each instance in millicores"
  type        = string
  default     = "2000m"

  validation {
    condition     = can(regex("^[0-9]+m$", var.cpu_limit))
    error_message = "CPU limit must be specified in millicores (e.g., '2000m')."
  }
}

variable "memory_limit" {
  description = "Memory limit for each instance"
  type        = string
  default     = "4Gi"

  validation {
    condition     = can(regex("^[0-9]+(Mi|Gi)$", var.memory_limit))
    error_message = "Memory limit must be specified in Mi or Gi (e.g., '4Gi')."
  }
}

# Service Account for Cloud Run
resource "google_service_account" "main" {
  account_id   = "${var.service_name}-sa-${var.environment}"
  display_name = "Service Account for ${var.service_name} Cloud Run Service - ${var.environment}"
  project      = var.project_id
  description  = "Service account for ${var.service_name} Cloud Run service in ${var.environment} environment"
}

# Cloud Run Service
resource "google_cloud_run_service" "main" {
  name     = "${var.service_name}-${var.environment}"
  location = var.region
  project  = var.project_id

  template {
    spec {
      service_account_name = google_service_account.main.email
      containers {
        image = var.container_image
        
        resources {
          limits = {
            cpu    = var.cpu_limit
            memory = var.memory_limit
          }
        }

        ports {
          container_port = 8000
        }

        # Environment-specific container configurations
        dynamic "env" {
          for_each = var.environment == "prod" ? [1] : []
          content {
            name  = "ENVIRONMENT"
            value = "production"
          }
        }
      }
    }

    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale"      = var.min_instances
        "autoscaling.knative.dev/maxScale"      = var.max_instances
        "run.googleapis.com/client-name"        = "terraform"
        "run.googleapis.com/cpu-throttling"     = "false"
        "run.googleapis.com/startup-cpu-boost"  = "true"
      }

      labels = {
        environment = var.environment
        managed-by  = "terraform"
        service     = var.service_name
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  autogenerate_revision_name = true

  lifecycle {
    prevent_destroy = var.environment == "prod"
  }
}

# Outputs
output "service_account" {
  description = "The service account created for the Cloud Run service"
  value = {
    email        = google_service_account.main.email
    account_id   = google_service_account.main.account_id
    display_name = google_service_account.main.display_name
  }
}

output "cloud_run_service" {
  description = "The Cloud Run service configuration"
  value = {
    name     = google_cloud_run_service.main.name
    location = google_cloud_run_service.main.location
    url      = google_cloud_run_service.main.status[0].url
  }
}