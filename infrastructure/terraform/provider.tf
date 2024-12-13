# Configure Terraform and required providers
terraform {
  required_version = ">= 1.0.0"

  required_providers {
    # Primary Google Cloud provider for core infrastructure services
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }

    # Beta provider for preview features and advanced services
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 4.0"
    }
  }
}

# Primary Google Cloud provider configuration
provider "google" {
  # Project and region configuration from variables
  project     = var.project_id
  region      = var.region
  
  # Secure credential management using environment variable
  # Requires GOOGLE_APPLICATION_CREDENTIALS to be set with service account key path
  # Required permissions:
  # - cloudrun.services.create
  # - cloudsql.instances.create
  # - redis.instances.create
  # - iam.serviceAccounts.actAs
  credentials = null  # Uses GOOGLE_APPLICATION_CREDENTIALS environment variable
}

# Google Cloud Beta provider configuration
provider "google-beta" {
  # Project and region configuration from variables
  project     = var.project_id
  region      = var.region
  
  # Secure credential management using environment variable
  # Requires GOOGLE_APPLICATION_CREDENTIALS to be set with service account key path
  # Required permissions:
  # - cloudrun.services.create
  # - cloudsql.instances.create
  # - redis.instances.create
  # - iam.serviceAccounts.actAs
  credentials = null  # Uses GOOGLE_APPLICATION_CREDENTIALS environment variable
}