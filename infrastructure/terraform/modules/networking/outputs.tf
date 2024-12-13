# Output the VPC ID for use by other modules
output "vpc_id" {
  value       = google_compute_network.main.id
  description = "The ID of the created VPC network"
}

# Output the VPC name for reference
output "vpc_name" {
  value       = google_compute_network.main.name
  description = "The name of the created VPC network"
}

# Output the subnet ID for use by other modules
output "subnet_id" {
  value       = google_compute_subnetwork.main.id
  description = "The ID of the created subnet"
}

# Output the subnet name for reference
output "subnet_name" {
  value       = google_compute_subnetwork.main.name
  description = "The name of the created subnet"
}

# Output the subnet CIDR range for network planning
output "subnet_cidr" {
  value       = google_compute_subnetwork.main.ip_cidr_range
  description = "The IP CIDR range of the created subnet"
}