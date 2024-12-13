# Output for Cloud Run service URL
output "service_url" {
  description = "The HTTPS URL where the Cloud Run service can be accessed"
  value       = google_cloud_run_service.main.status[0].url
}

# Output for Cloud Run service name
output "service_name" {
  description = "The name of the deployed Cloud Run service"
  value       = google_cloud_run_service.main.name
}

# Output for service account email
output "service_account_email" {
  description = "The email address of the service account used by the Cloud Run service"
  value       = google_service_account.main.email
}

# Output for service account ID
output "service_account_id" {
  description = "The account ID of the service account used by the Cloud Run service"
  value       = google_service_account.main.account_id
}

# Output for Cloud Run service status
output "service_status" {
  description = "The current status of the Cloud Run service including conditions and observed generation"
  value       = google_cloud_run_service.main.status[0]
}