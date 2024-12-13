# Output the Cloud SQL instance name
output "instance_name" {
  description = "Fully qualified name of the Cloud SQL PostgreSQL instance for infrastructure reference"
  value       = google_sql_database_instance.main.name
}

# Output the Cloud SQL connection name
output "connection_name" {
  description = "Cloud SQL instance connection name used by client libraries and proxy connections"
  value       = google_sql_database_instance.main.connection_name
}

# Output the database name
output "database_name" {
  description = "Name of the created PostgreSQL database for application configuration"
  value       = google_sql_database.main.name
}

# Output the database user name
output "database_user" {
  description = "PostgreSQL database user name for authentication configuration"
  value       = var.database_user
}

# Output the database password (marked as sensitive)
output "database_password" {
  description = "Securely generated password for database user authentication (sensitive value)"
  value       = random_password.db_password.result
  sensitive   = true
}

# Output the private IP address
output "private_ip_address" {
  description = "Private IP address for VPC network access to the PostgreSQL instance"
  value       = google_sql_database_instance.main.private_ip_address
}