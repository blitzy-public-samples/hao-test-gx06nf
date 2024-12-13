# Configure Terraform and required providers
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# Generate a secure random password for the database user
resource "random_password" "db_password" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
  min_special      = 2
  min_numeric      = 2
  min_upper        = 2
  min_lower        = 2
}

# Create the Cloud SQL instance with PostgreSQL
resource "google_sql_database_instance" "main" {
  name                = var.instance_name
  database_version    = "POSTGRES_14"
  region             = var.region
  deletion_protection = true # Prevent accidental deletion

  settings {
    tier              = "db-custom-2-4096" # 2 vCPU, 4GB RAM as per specs
    availability_type = "REGIONAL" # Enable high availability
    
    disk_size = 100 # GB
    disk_type = "PD_SSD"
    
    # Backup configuration
    backup_configuration {
      enabled                        = true
      start_time                     = "23:00" # 11 PM UTC
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
      retained_backups              = 7
      backup_retention_settings {
        retained_backups = 7
        retention_unit  = "COUNT"
      }
    }

    # Network and security configuration
    ip_configuration {
      ipv4_enabled    = false # Disable public IP
      private_network = var.vpc_network
      require_ssl     = true
      ssl_mode        = "VERIFY_CA"
      
      # Allow only internal VPC access
      authorized_networks {
        name  = "internal"
        value = var.subnet_cidr_range
      }
    }

    # Database flags for security and monitoring
    database_flags {
      name  = "cloudsql.enable_pg_audit"
      value = "on"
    }
    database_flags {
      name  = "log_min_duration_statement"
      value = "300000" # Log queries taking more than 5 minutes
    }
    database_flags {
      name  = "log_checkpoints"
      value = "on"
    }
    database_flags {
      name  = "log_connections"
      value = "on"
    }
    database_flags {
      name  = "log_disconnections"
      value = "on"
    }
    database_flags {
      name  = "log_lock_waits"
      value = "on"
    }
    database_flags {
      name  = "password_encryption"
      value = "scram-sha-256"
    }
    database_flags {
      name  = "ssl"
      value = "on"
    }

    # Maintenance window (Sunday 11 PM UTC)
    maintenance_window {
      day          = 7
      hour         = 23
      update_track = "stable"
    }

    # Enable insights monitoring
    insights_config {
      query_insights_enabled  = true
      query_string_length    = 1024
      record_application_tags = true
      record_client_address  = true
    }
  }

  # Ensure proper deletion order
  depends_on = [
    var.vpc_network
  ]

  lifecycle {
    prevent_destroy = true # Prevent accidental deletion
    ignore_changes = [
      settings[0].backup_configuration[0].point_in_time_recovery_enabled,
    ]
  }
}

# Create the database
resource "google_sql_database" "main" {
  name      = var.database_name
  instance  = google_sql_database_instance.main.name
  charset   = "UTF8"
  collation = "en_US.UTF8"
}

# Create database user
resource "google_sql_user" "main" {
  name     = var.database_user
  instance = google_sql_database_instance.main.name
  password = random_password.db_password.result
  type     = "BUILT_IN"

  # Password policy
  password_policy {
    min_length                  = 16
    complexity                  = "COMPLEXITY_DEFAULT"
    reuse_interval             = 5
    disallow_username_substring = true
    enable_password_policy      = true
  }
}

# Output the database connection information
output "instance_name" {
  value       = google_sql_database_instance.main.name
  description = "The name of the database instance"
}

output "instance_connection_name" {
  value       = google_sql_database_instance.main.connection_name
  description = "The connection name of the database instance"
}

output "database_name" {
  value       = google_sql_database.main.name
  description = "The name of the database"
}

output "private_ip_address" {
  value       = google_sql_database_instance.main.private_ip_address
  description = "The private IP address of the database instance"
}

output "database_user" {
  value       = google_sql_user.main.name
  description = "The database user name"
  sensitive   = true
}

output "database_password" {
  value       = random_password.db_password.result
  description = "The database user password"
  sensitive   = true
}