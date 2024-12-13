# Required Terraform version constraint
terraform {
  required_version = ">=1.0.0"
}

variable "instance_name" {
  type        = string
  description = "Name of the Cloud SQL instance"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]*[a-z0-9]$", var.instance_name))
    error_message = "Instance name must start with a letter, contain only lowercase letters, numbers, and hyphens"
  }
}

variable "region" {
  type        = string
  description = "GCP region for database instance deployment"
  default     = "us-central1"
}

variable "instance_tier" {
  type        = string
  description = "Machine type for database instance"
  default     = "db-custom-2-4096"  # 2 vCPU, 4GB RAM as per technical specs
  validation {
    condition     = can(regex("^db-custom-[0-9]+-[0-9]+$", var.instance_tier))
    error_message = "Instance tier must be a valid Cloud SQL custom machine type"
  }
}

variable "database_version" {
  type        = string
  description = "PostgreSQL version for the database instance"
  default     = "POSTGRES_14"
  validation {
    condition     = can(regex("^POSTGRES_1[4-9]$", var.database_version))
    error_message = "Database version must be PostgreSQL 14 or higher"
  }
}

variable "availability_type" {
  type        = string
  description = "Availability type for the database instance"
  default     = "REGIONAL"  # High availability configuration as per technical specs
  validation {
    condition     = contains(["REGIONAL", "ZONAL"], var.availability_type)
    error_message = "Availability type must be either REGIONAL or ZONAL"
  }
}

variable "database_name" {
  type        = string
  description = "Name of the PostgreSQL database to create"
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]*$", var.database_name))
    error_message = "Database name must start with a letter and contain only alphanumeric characters and underscores"
  }
}

variable "database_user" {
  type        = string
  description = "Username for database access"
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]*$", var.database_user))
    error_message = "Database user must start with a letter and contain only alphanumeric characters and underscores"
  }
}

variable "backup_start_time" {
  type        = string
  description = "Start time for automated backups in UTC (format: HH:MM)"
  default     = "23:00"  # Late night UTC for minimal impact
  validation {
    condition     = can(regex("^([01][0-9]|2[0-3]):[0-5][0-9]$", var.backup_start_time))
    error_message = "Backup start time must be in 24-hour format (HH:MM)"
  }
}

variable "backup_retention_days" {
  type        = number
  description = "Number of days to retain automated backups"
  default     = 7  # One week retention as per technical specs
  validation {
    condition     = var.backup_retention_days >= 7 && var.backup_retention_days <= 365
    error_message = "Backup retention period must be between 7 and 365 days"
  }
}

variable "maintenance_window_day" {
  type        = number
  description = "Day of week for maintenance window (1-7 for Monday-Sunday)"
  default     = 7  # Sunday
  validation {
    condition     = var.maintenance_window_day >= 1 && var.maintenance_window_day <= 7
    error_message = "Maintenance window day must be between 1 (Monday) and 7 (Sunday)"
  }
}

variable "maintenance_window_hour" {
  type        = number
  description = "Hour of day for maintenance window in UTC (0-23)"
  default     = 2  # 2 AM UTC for minimal impact
  validation {
    condition     = var.maintenance_window_hour >= 0 && var.maintenance_window_hour <= 23
    error_message = "Maintenance window hour must be between 0 and 23"
  }
}

variable "ssl_enforcement" {
  type        = bool
  description = "Enforce SSL/TLS for all connections"
  default     = true  # Enforce SSL as per security requirements
}

variable "deletion_protection" {
  type        = bool
  description = "Prevent accidental instance deletion"
  default     = true  # Enable deletion protection for production safety
}

variable "vpc_network" {
  type        = string
  description = "VPC network self-link for private IP configuration"
  validation {
    condition     = can(regex("^projects/[a-z][a-z0-9-]*/global/networks/[a-z][a-z0-9-]*$", var.vpc_network))
    error_message = "VPC network must be a valid self-link format"
  }
}

# Additional variables for database flags and configurations
variable "database_flags" {
  type = list(object({
    name  = string
    value = string
  }))
  description = "Database flags for instance configuration"
  default = [
    {
      name  = "max_connections"
      value = "100"
    },
    {
      name  = "log_min_duration_statement"
      value = "300000"  # Log queries taking more than 300s
    }
  ]
}

variable "disk_size" {
  type        = number
  description = "The size of the database disk in GB"
  default     = 100
  validation {
    condition     = var.disk_size >= 10 && var.disk_size <= 65536
    error_message = "Disk size must be between 10GB and 65536GB"
  }
}

variable "disk_type" {
  type        = string
  description = "The type of disk to use for the database instance"
  default     = "PD_SSD"
  validation {
    condition     = contains(["PD_SSD", "PD_HDD"], var.disk_type)
    error_message = "Disk type must be either PD_SSD or PD_HDD"
  }
}