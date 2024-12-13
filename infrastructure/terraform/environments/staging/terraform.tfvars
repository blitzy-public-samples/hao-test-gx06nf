# Project Configuration
project_id = "flask-api-staging"
region     = "us-central1"
environment = "staging"

# Database Configuration
# Using db-f1-micro tier for cost-effective staging environment
# Provides 0.6 GB RAM, shared CPU suitable for testing workloads
db_instance_tier = "db-f1-micro"

# Redis Cache Configuration
# Reduced memory size for staging while maintaining functionality
redis_memory_size_gb = 2

# Cloud Run Scaling Configuration
# Limited instance range for cost control while supporting testing
min_instances = 1
max_instances = 5