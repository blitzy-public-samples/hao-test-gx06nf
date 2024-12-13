# Production Environment Configuration
# These values are specifically tuned for production deployment based on the technical specifications
# and high availability requirements outlined in section 8.1 and 8.2 of the technical documentation.

# Environment identifier
# Used for resource naming and tagging to clearly identify production resources
environment = "prod"

# Regional Configuration
# US Central region chosen for optimal latency and multiple availability zones
# as specified in section 8.1 of technical specifications
region = "us-central1"

# Database Configuration
# Custom instance with 2 vCPUs and 4GB RAM as specified in section 8.2
# This tier supports the performance requirements outlined in section 2.6
db_instance_tier = "db-custom-2-4096"

# Redis Cache Configuration
# 5GB memory allocation for production caching requirements
# as specified in section 8.2 Cloud Services
redis_memory_size_gb = 5

# Cloud Run Configuration
# High availability settings with minimum 2 instances for production
# Maximum 10 instances for scaling as specified in section 8.1
min_instances = 2
max_instances = 10

# Additional Resource Configuration
# These values ensure the system meets performance requirements
# from section 2.6 of technical specifications
instance_cpu = "2000m"    # 2 vCPU allocation
instance_memory = "4Gi"   # 4GB memory allocation per instance

# Note: project_id is intentionally not set here as it should be
# provided via CI/CD pipeline or command line for security reasons