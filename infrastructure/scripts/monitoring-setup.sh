#!/bin/bash

# Monitoring Stack Setup Script
# Version: 1.0.0
# Description: Sets up and configures complete monitoring stack for the specification management API system
# Required tools: docker-ce >= 20.10, docker-compose >= 1.29

# Global variables
PROMETHEUS_VERSION="v2.45.0"
GRAFANA_VERSION="9.5.0"
FLUENTD_VERSION="v1.16"
ALERTMANAGER_VERSION="v0.25.0"
MONITORING_NAMESPACE="monitoring"

# Base directories
BASE_DIR="/opt/${MONITORING_NAMESPACE}"
CONFIG_DIR="${BASE_DIR}/config"
DATA_DIR="${BASE_DIR}/data"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    shift
    local message=$@
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    case $level in
        "INFO")
            echo -e "${GREEN}[INFO]${NC} ${timestamp} - $message"
            ;;
        "WARN")
            echo -e "${YELLOW}[WARN]${NC} ${timestamp} - $message"
            ;;
        "ERROR")
            echo -e "${RED}[ERROR]${NC} ${timestamp} - $message"
            ;;
    esac
}

# Check prerequisites for monitoring stack setup
check_prerequisites() {
    log "INFO" "Checking prerequisites..."
    
    # Check if script is run as root
    if [[ $EUID -ne 0 ]]; then
        log "ERROR" "This script must be run as root"
        return 1
    }

    # Check Docker installation
    if ! command -v docker &> /dev/null; then
        log "ERROR" "Docker is not installed"
        return 1
    fi

    # Check Docker Compose installation
    if ! command -v docker-compose &> /dev/null; then
        log "ERROR" "Docker Compose is not installed"
        return 1
    }

    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        log "ERROR" "Docker daemon is not running"
        return 1
    }

    # Check required ports availability
    local ports=(9090 3000 24231 9093)
    for port in "${ports[@]}"; do
        if netstat -tuln | grep -q ":$port "; then
            log "ERROR" "Port $port is already in use"
            return 1
        fi
    done

    # Check system resources
    local available_memory=$(free -g | awk '/^Mem:/{print $7}')
    if [[ $available_memory -lt 4 ]]; then
        log "ERROR" "Insufficient memory. Required: 4GB, Available: ${available_memory}GB"
        return 1
    }

    local available_disk=$(df -BG "${BASE_DIR}" | awk 'NR==2 {print $4}' | sed 's/G//')
    if [[ $available_disk -lt 10 ]]; then
        log "ERROR" "Insufficient disk space. Required: 10GB, Available: ${available_disk}GB"
        return 1
    }

    # Create required directories
    mkdir -p "${CONFIG_DIR}"/{prometheus,grafana,fluentd,alertmanager}
    mkdir -p "${DATA_DIR}"/{prometheus,grafana,fluentd,alertmanager}

    log "INFO" "Prerequisites check completed successfully"
    return 0
}

# Setup Prometheus monitoring server
setup_prometheus() {
    log "INFO" "Setting up Prometheus..."

    # Create Prometheus configuration
    cat > "${CONFIG_DIR}/prometheus/prometheus.yml" <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    monitor: 'specification-api-monitor'

rule_files:
  - "rules/*.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'specification-api'
    metrics_path: '/metrics'
    scrape_interval: 5s
    static_configs:
      - targets: ['api:8000']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: 'specification-api'

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
EOF

    # Create recording rules for response time metrics
    mkdir -p "${CONFIG_DIR}/prometheus/rules"
    cat > "${CONFIG_DIR}/prometheus/rules/recording_rules.yml" <<EOF
groups:
  - name: response_time_rules
    rules:
      - record: api:request_duration_seconds:p95
        expr: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
      - record: api:request_duration_seconds:p99
        expr: histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
EOF

    # Start Prometheus container
    docker run -d \
        --name prometheus \
        --network ${MONITORING_NAMESPACE} \
        -p 9090:9090 \
        -v "${CONFIG_DIR}/prometheus:/etc/prometheus" \
        -v "${DATA_DIR}/prometheus:/prometheus" \
        prom/prometheus:${PROMETHEUS_VERSION} \
        --config.file=/etc/prometheus/prometheus.yml \
        --storage.tsdb.path=/prometheus \
        --storage.tsdb.retention.time=15d \
        --web.enable-admin-api

    if [[ $? -ne 0 ]]; then
        log "ERROR" "Failed to start Prometheus container"
        return 1
    fi

    log "INFO" "Prometheus setup completed successfully"
    return 0
}

# Setup Grafana visualization platform
setup_grafana() {
    log "INFO" "Setting up Grafana..."

    # Create Grafana datasource configuration
    cat > "${CONFIG_DIR}/grafana/datasources.yml" <<EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: "15s"
EOF

    # Create Grafana dashboard configuration
    mkdir -p "${CONFIG_DIR}/grafana/dashboards"
    cat > "${CONFIG_DIR}/grafana/dashboards/api_monitoring.json" <<EOF
{
  "dashboard": {
    "title": "API Monitoring Dashboard",
    "panels": [
      {
        "title": "API Response Time (95th Percentile)",
        "type": "graph",
        "datasource": "Prometheus",
        "targets": [
          {
            "expr": "api:request_duration_seconds:p95",
            "legendFormat": "P95"
          }
        ]
      },
      {
        "title": "System Availability",
        "type": "gauge",
        "datasource": "Prometheus",
        "targets": [
          {
            "expr": "avg_over_time(up{job=\"specification-api\"}[24h]) * 100"
          }
        ]
      },
      {
        "title": "Authentication Success Rate",
        "type": "gauge",
        "datasource": "Prometheus",
        "targets": [
          {
            "expr": "sum(rate(auth_success_total[5m])) / sum(rate(auth_attempts_total[5m])) * 100"
          }
        ]
      }
    ]
  }
}
EOF

    # Start Grafana container
    docker run -d \
        --name grafana \
        --network ${MONITORING_NAMESPACE} \
        -p 3000:3000 \
        -v "${CONFIG_DIR}/grafana:/etc/grafana" \
        -v "${DATA_DIR}/grafana:/var/lib/grafana" \
        -e "GF_SECURITY_ADMIN_PASSWORD=admin" \
        -e "GF_USERS_ALLOW_SIGN_UP=false" \
        grafana/grafana:${GRAFANA_VERSION}

    if [[ $? -ne 0 ]]; then
        log "ERROR" "Failed to start Grafana container"
        return 1
    fi

    log "INFO" "Grafana setup completed successfully"
    return 0
}

# Setup Fluentd log aggregator
setup_fluentd() {
    log "INFO" "Setting up Fluentd..."

    # Create Fluentd configuration
    cat > "${CONFIG_DIR}/fluentd/fluent.conf" <<EOF
<source>
  @type forward
  port 24224
  bind 0.0.0.0
</source>

<source>
  @type monitor_agent
  bind 0.0.0.0
  port 24231
</source>

<match api.**>
  @type elasticsearch
  host elasticsearch
  port 9200
  logstash_format true
  logstash_prefix api-logs
  flush_interval 5s
</match>

<filter api.**>
  @type parser
  key_name log
  <parse>
    @type json
    time_key timestamp
    time_format %Y-%m-%dT%H:%M:%S.%NZ
  </parse>
</filter>
EOF

    # Start Fluentd container
    docker run -d \
        --name fluentd \
        --network ${MONITORING_NAMESPACE} \
        -p 24224:24224 \
        -p 24224:24224/udp \
        -p 24231:24231 \
        -v "${CONFIG_DIR}/fluentd:/fluentd/etc" \
        -v "${DATA_DIR}/fluentd:/fluentd/log" \
        fluent/fluentd:${FLUENTD_VERSION}

    if [[ $? -ne 0 ]]; then
        log "ERROR" "Failed to start Fluentd container"
        return 1
    fi

    log "INFO" "Fluentd setup completed successfully"
    return 0
}

# Setup Alertmanager
setup_alertmanager() {
    log "INFO" "Setting up Alertmanager..."

    # Create Alertmanager configuration
    cat > "${CONFIG_DIR}/alertmanager/alertmanager.yml" <<EOF
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'job']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default-receiver'

receivers:
- name: 'default-receiver'
  email_configs:
  - to: 'admin@example.com'
    from: 'alertmanager@example.com'
    smarthost: 'smtp.example.com:587'
    auth_username: 'alertmanager'
    auth_password: 'password'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'job']
EOF

    # Start Alertmanager container
    docker run -d \
        --name alertmanager \
        --network ${MONITORING_NAMESPACE} \
        -p 9093:9093 \
        -v "${CONFIG_DIR}/alertmanager:/etc/alertmanager" \
        -v "${DATA_DIR}/alertmanager:/alertmanager" \
        prom/alertmanager:${ALERTMANAGER_VERSION} \
        --config.file=/etc/alertmanager/alertmanager.yml \
        --storage.path=/alertmanager

    if [[ $? -ne 0 ]]; then
        log "ERROR" "Failed to start Alertmanager container"
        return 1
    fi

    log "INFO" "Alertmanager setup completed successfully"
    return 0
}

# Verify monitoring stack
verify_monitoring_stack() {
    log "INFO" "Verifying monitoring stack..."
    local failed=0

    # Check if all containers are running
    local containers=("prometheus" "grafana" "fluentd" "alertmanager")
    for container in "${containers[@]}"; do
        if ! docker ps | grep -q $container; then
            log "ERROR" "Container $container is not running"
            failed=1
        fi
    done

    # Verify Prometheus endpoint
    if ! curl -s "http://localhost:9090/-/healthy" > /dev/null; then
        log "ERROR" "Prometheus health check failed"
        failed=1
    fi

    # Verify Grafana endpoint
    if ! curl -s "http://localhost:3000/api/health" > /dev/null; then
        log "ERROR" "Grafana health check failed"
        failed=1
    fi

    # Verify Alertmanager endpoint
    if ! curl -s "http://localhost:9093/-/healthy" > /dev/null; then
        log "ERROR" "Alertmanager health check failed"
        failed=1
    fi

    if [[ $failed -eq 0 ]]; then
        log "INFO" "Monitoring stack verification completed successfully"
        return 0
    else
        log "ERROR" "Monitoring stack verification failed"
        return 1
    fi
}

# Main execution
main() {
    log "INFO" "Starting monitoring stack setup..."

    # Create Docker network if it doesn't exist
    docker network create ${MONITORING_NAMESPACE} 2>/dev/null

    # Execute setup steps
    check_prerequisites || exit 1
    setup_prometheus || exit 1
    setup_grafana || exit 1
    setup_fluentd || exit 1
    setup_alertmanager || exit 1
    verify_monitoring_stack || exit 1

    log "INFO" "Monitoring stack setup completed successfully"
    log "INFO" "Grafana UI: http://localhost:3000 (admin/admin)"
    log "INFO" "Prometheus UI: http://localhost:9090"
    log "INFO" "Alertmanager UI: http://localhost:9093"
}

# Execute main function
main