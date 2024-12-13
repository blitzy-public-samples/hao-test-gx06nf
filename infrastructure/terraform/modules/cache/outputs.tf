# Output variable for Redis instance hostname
output "redis_host" {
  description = "The hostname of the Redis instance for VPC-internal application connections"
  value       = google_redis_instance.cache.host
}

# Output variable for Redis instance port
output "redis_port" {
  description = "The port number of the Redis instance for application configuration"
  value       = google_redis_instance.cache.port
}

# Output variable for Redis instance ID
output "redis_instance_id" {
  description = "The unique identifier of the Redis instance for monitoring and metrics collection"
  value       = google_redis_instance.cache.id
}

# Output variable for Redis authentication string
output "redis_auth_string" {
  description = "The authentication string for Redis instance connection (sensitive)"
  value       = google_redis_instance.cache.auth_string
  sensitive   = true
}

# Output variable for Redis instance location
output "redis_current_location_id" {
  description = "The current location ID of the Redis instance for geo-redundancy monitoring"
  value       = google_redis_instance.cache.current_location_id
}

# Output variable for Redis instance connection name
output "redis_connection_name" {
  description = "The full connection name of the Redis instance in format: projects/PROJECT_ID/locations/REGION/instances/INSTANCE_ID"
  value       = google_redis_instance.cache.id
}

# Output variable for Redis instance state
output "redis_state" {
  description = "The current state of the Redis instance for operational monitoring"
  value       = google_redis_instance.cache.state
}