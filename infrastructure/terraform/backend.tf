# Backend configuration for Terraform state management
# Version: Terraform >= 1.0.0
# Purpose: Configures secure, versioned GCS backend for Terraform state storage

terraform {
  backend "gcs" {
    # Bucket name will be constructed using the project ID variable
    bucket = "${var.project_id}-terraform-state"
    
    # State file location within bucket
    prefix = "terraform/state"
    
    # Geographic location for state storage
    location = "us-central1"
    
    # Use standard storage class for frequent access
    storage_class = "STANDARD"
    
    # Enable versioning for state history and backup
    versioning = true
    
    # Enable state locking to prevent concurrent modifications
    enable_state_locking = true
    
    # Default timeout for state operations (5 minutes)
    timeout_seconds = 300
    
    # Labels for resource organization and tracking
    labels = {
      managed-by = "terraform"
      purpose    = "state-storage"
    }
  }

  # Specify required provider versions
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.0.0"
    }
  }

  # Specify minimum Terraform version
  required_version = ">= 1.0.0"
}

# Note: The following features are automatically enabled through GCP:
# - Customer-managed encryption keys (CMEK) - configured via GCP
# - IAM access controls - managed via project-level permissions
# - Audit logging - enabled via Cloud Audit Logs
# - Object versioning - enabled via bucket configuration
# - Object lifecycle management - configured via GCP console or separate terraform resources