# Configure Terraform and required providers
terraform {
  required_version = ">=1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">=4.0.0"
    }
  }
}

# Create the VPC network
resource "google_compute_network" "main" {
  name                    = "${var.environment}-vpc"
  project                 = var.project_id
  auto_create_subnetworks = false # Disable auto-subnet creation for better control
  routing_mode            = "REGIONAL"

  lifecycle {
    prevent_destroy = true # Prevent accidental deletion of network
  }
}

# Create the main subnet within the VPC
resource "google_compute_subnetwork" "main" {
  name                     = "${var.environment}-subnet"
  project                 = var.project_id
  region                  = var.region
  network                 = google_compute_network.main.id
  ip_cidr_range           = var.subnet_cidr_range
  private_ip_google_access = var.enable_private_google_access

  # Enable flow logs for network monitoring
  log_config {
    aggregation_interval = "INTERVAL_5_SEC"
    flow_sampling        = 0.5
    metadata            = "INCLUDE_ALL_METADATA"
  }

  lifecycle {
    prevent_destroy = true # Prevent accidental deletion of subnet
  }
}

# Create firewall rule for internal communication
resource "google_compute_firewall" "allow_internal" {
  name    = "${var.environment}-allow-internal"
  project = var.project_id
  network = google_compute_network.main.id

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [var.subnet_cidr_range]
  direction     = "INGRESS"
  priority      = 1000
}

# Create firewall rule for health checks
resource "google_compute_firewall" "allow_health_checks" {
  name    = "${var.environment}-allow-health-checks"
  project = var.project_id
  network = google_compute_network.main.id

  allow {
    protocol = "tcp"
    ports    = ["8000"] # Port for the Flask application
  }

  source_ranges = ["130.211.0.0/22", "35.191.0.0/16"] # Google Cloud health check ranges
  direction     = "INGRESS"
  priority      = 1000
}

# Create firewall rule for Cloud SQL
resource "google_compute_firewall" "allow_sql" {
  name    = "${var.environment}-allow-sql"
  project = var.project_id
  network = google_compute_network.main.id

  allow {
    protocol = "tcp"
    ports    = ["5432"] # PostgreSQL port
  }

  source_ranges = [var.subnet_cidr_range]
  direction     = "INGRESS"
  priority      = 1000
}

# Create firewall rule for Redis
resource "google_compute_firewall" "allow_redis" {
  name    = "${var.environment}-allow-redis"
  project = var.project_id
  network = google_compute_network.main.id

  allow {
    protocol = "tcp"
    ports    = ["6379"] # Redis port
  }

  source_ranges = [var.subnet_cidr_range]
  direction     = "INGRESS"
  priority      = 1000
}

# Export VPC and subnet information for other modules
output "vpc" {
  value = {
    id   = google_compute_network.main.id
    name = google_compute_network.main.name
  }
  description = "The VPC network resource"
}

output "subnet" {
  value = {
    id            = google_compute_subnetwork.main.id
    name          = google_compute_subnetwork.main.name
    ip_cidr_range = google_compute_subnetwork.main.ip_cidr_range
  }
  description = "The subnet resource within the VPC"
}