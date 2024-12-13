# Configure Terraform and required providers
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

# Redis instance resource configuration
resource "google_redis_instance" "cache" {
  # Basic instance configuration
  name               = "${var.environment}-redis-cache"
  project            = var.project_id
  region             = var.region
  memory_size_gb     = var.memory_size_gb
  redis_version      = var.redis_version
  tier               = var.tier
  display_name       = "API Cache - ${var.environment}"

  # Enhanced security configuration
  auth_enabled              = true
  transit_encryption_mode   = "SERVER_AUTHENTICATION"
  authorized_network        = "default"
  connect_mode             = "PRIVATE_SERVICE_ACCESS"

  # Maintenance window configuration
  maintenance_policy {
    weekly_maintenance_window {
      day        = "SUNDAY"
      start_time {
        hours   = 2
        minutes = 0
      }
    }
  }

  # Redis configuration parameters
  redis_configs = {
    # LRU eviction policy for memory management
    maxmemory-policy = "allkeys-lru"
    # Enable keyspace notifications for expired keys
    notify-keyspace-events = "Ex"
    # Connection timeout in seconds
    timeout = "3600"
  }

  # Resource labels for management and monitoring
  labels = {
    environment = var.environment
    managed-by  = "terraform"
    service     = "api-cache"
    component   = "caching-layer"
    criticality = "high"
  }

  # Lifecycle management to prevent accidental deletion
  lifecycle {
    prevent_destroy = true
  }
}

# Output values for use by other modules
output "redis_host" {
  description = "The IP address of the Redis instance"
  value       = google_redis_instance.cache.host
}

output "redis_port" {
  description = "The port number of the Redis instance"
  value       = google_redis_instance.cache.port
}

output "redis_id" {
  description = "The unique identifier of the Redis instance"
  value       = google_redis_instance.cache.id
}

output "redis_current_location_id" {
  description = "The current location ID of the Redis instance"
  value       = google_redis_instance.cache.current_location_id
}

output "redis_auth_string" {
  description = "The authentication string for the Redis instance"
  value       = google_redis_instance.cache.auth_string
  sensitive   = true
}