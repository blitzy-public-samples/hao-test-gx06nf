# Network Infrastructure Outputs
output "network_info" {
  description = "Network infrastructure details including VPC and subnet information"
  value = {
    vpc_id     = module.networking.vpc_id
    vpc_name   = module.networking.vpc_name
    subnet_id  = module.networking.subnet_id
    subnet_name = module.networking.subnet_name
    subnet_cidr = module.networking.subnet_cidr
  }

  sensitive = false # Network IDs are not sensitive information
}

# Database Connection Outputs
output "database_connection" {
  description = "Database connection information including instance details and credentials"
  value = {
    instance_name    = module.database.instance_name
    connection_name  = module.database.instance_connection_name
    database_name    = module.database.database_name
    private_ip      = module.database.private_ip_address
    credentials = {
      username = module.database.database_user
      password = module.database.database_password
    }
  }

  sensitive = true # Database credentials must be marked as sensitive
}

# Redis Cache Connection Outputs
output "cache_connection" {
  description = "Redis cache connection details including host and port"
  value = {
    host          = module.cache.redis_host
    port          = module.cache.redis_port
    instance_id   = module.cache.redis_id
    location      = module.cache.redis_current_location_id
    auth_string   = module.cache.redis_auth_string
  }

  sensitive = true # Redis authentication details must be marked as sensitive
}

# Cloud Run Service Outputs
output "api_service" {
  description = "Cloud Run service details including URL and service account information"
  value = {
    url = module.compute.cloud_run_service.url
    name = module.compute.cloud_run_service.name
    location = module.compute.cloud_run_service.location
    service_account = {
      email = module.compute.service_account.email
      id    = module.compute.service_account.account_id
      name  = module.compute.service_account.display_name
    }
  }

  sensitive = false # Service URLs and service account emails are public information
}

# Validation for required outputs
locals {
  # Ensure all required connection information is available
  validate_db_connection = (
    module.database.instance_name != "" && 
    module.database.database_name != "" && 
    module.database.database_user != ""
  )
  
  validate_cache_connection = (
    module.cache.redis_host != "" && 
    module.cache.redis_port > 0
  )
  
  validate_service_url = (
    module.compute.cloud_run_service.url != ""
  )
}

# Output validation checks
resource "null_resource" "output_validation" {
  lifecycle {
    precondition {
      condition = local.validate_db_connection
      error_message = "Database connection information is incomplete or invalid."
    }

    precondition {
      condition = local.validate_cache_connection
      error_message = "Redis cache connection information is incomplete or invalid."
    }

    precondition {
      condition = local.validate_service_url
      error_message = "Cloud Run service URL is not available."
    }
  }
}